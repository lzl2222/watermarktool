# -*- coding: utf-8 -*-
"""
xiaohongshu_parser.py — 小红书笔记无水印解析器 v2

支持内容类型：
  image        — 纯静态图文笔记（多张图片）
  live_photo   — 含 Live Photo 动态图的图文笔记（动图 = 短视频 2-3 秒）
  video        — 视频笔记

技术方案（主 + 备双通道）：
  主方案：
    1. 自动识别分享文本中的链接（支持整段复制的小红书分享文案）
    2. 短链/长链解析 → 提取 note_id + xsec_token（token 是访问凭证，缺失会 404）
    3. 请求笔记 Web 页面（Chrome UA）
    4. 解析 window.__INITIAL_STATE__ JSON → noteDetailMap → 结构化数据
       - 图片：imageList[].infoList（WB_DFT 原图 CDN）
       - 原图：由 CDN URL 提取 token → sns-img-bd.xhscdn.com/{token} 得到无压缩原图
       - 动图：imageList[].livePhoto 视频流（masterUrl / backupUrls）
       - 视频：note.video.media.stream.h264/h265 → masterUrl + backupUrls
  备方案（INITIAL_STATE 解析失败时）：
    正则解析 og:image meta / livePhoto 字段 / masterUrl 字段

返回统一格式 dict：
  {
    "platform":     "xiaohongshu",
    "type":         "image"|"live_photo"|"video",
    "note_id":      str,
    "title":        str,
    "author":       str,
    "cover_url":    str,
    "media_items":  [ { type, url, thumb, fallback, index } ],
    "text":         str,
    "no_watermark": True,
    "width":        int,
    "height":       int,
  }
"""

import re
import json
import time
import random
import urllib.parse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ────────────────────────────────────────────────────────────────────────────
# 常量
# ────────────────────────────────────────────────────────────────────────────
UA_CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": UA_CHROME,
    "Accept-Language": "zh-CN,zh;q=0.9",
})
# 自动重试（小红书接口偶发超时/限流）
_RETRY = Retry(total=3, backoff_factor=0.5,
               status_forcelist=[429, 500, 502, 503, 504],
               allowed_methods=frozenset(["GET", "POST"]))
_ADAPTER = HTTPAdapter(max_retries=_RETRY)
_SESSION.mount("http://", _ADAPTER)
_SESSION.mount("https://", _ADAPTER)

# 图片原图 CDN（由 token 拼出，无压缩参数）
ORIGIN_IMG_HOST = "https://sns-img-bd.xhscdn.com"

# ────────────────────────────────────────────────────────────────────────────
# 工具：链接识别与参数提取
# ────────────────────────────────────────────────────────────────────────────
_URL_RE = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
# 链接末尾常见的中英文标点/括号（属于分享文案，不属于 URL）
_TRAILING = ".,;:!?)]}》】】。，；：！？、…"


def extract_url(text: str) -> str:
    """
    从分享文本中自动识别出链接。
    兼容：整段复制的小红书分享文案（标题+口令+链接混在一起）。
    若找不到链接则原样返回（保持向后兼容）。
    """
    text = (text or "").strip()
    m = _URL_RE.search(text)
    if not m:
        return text
    url = m.group(0)
    # 去掉末尾不属于 URL 的标点（保留 query 中的 ? & =）
    url = url.rstrip(_TRAILING)
    # 去掉可能被一起复制进来的尾部括号/引用
    while url and url[-1] in ")]}>」』】】":
        url = url[:-1]
    return url.strip()


def _extract_note_id(url: str) -> str:
    """从 URL 中提取 24 位 hex note_id"""
    m = re.search(r'/(?:explore|discovery/item|item)/([a-f0-9]{24})', url)
    return m.group(1) if m else ""


def _parse_query(url: str) -> dict:
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)


def _resolve_link(url: str):
    """
    解析分享链接，返回 (final_url, note_id, xsec_token)。
    - 若 URL 已含 note_id + xsec_token（discovery/explore 长链）→ 直接使用
    - 若是 xhslink 短链 → 跟随重定向，从最终 URL 提取 note_id + xsec_token
    """
    note_id = _extract_note_id(url)
    qs      = _parse_query(url)
    token   = qs.get("xsec_token", [""])[0]

    if note_id and token:
        return url, note_id, token
    if note_id and not token:
        # 已是笔记长链但缺少 xsec_token → 不再重定向（省请求），由后续流程给出清晰错误
        return url, note_id, ""

    # 跟随重定向（短链）
    try:
        r = _SESSION.get(
            url,
            headers={
                "User-Agent": UA_CHROME,
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            allow_redirects=True,
            timeout=12,
        )
    except requests.RequestException as e:
        raise ValueError(f"链接请求失败：{e}")

    final = r.url
    note_id = _extract_note_id(final) or note_id
    qs2 = _parse_query(final)
    token = qs2.get("xsec_token", [""])[0] or token

    return final, note_id, token


def _fetch_note_page(note_id: str, xsec_token: str) -> str:
    """请求笔记页面 HTML（带 xsec_token 访问凭证）"""
    url = f"https://www.xiaohongshu.com/explore/{note_id}"
    if xsec_token:
        # 注意：token 需整串转义，否则末尾的 = 会被当作 query 分隔符
        url += f"?xsec_token={urllib.parse.quote(xsec_token, safe='')}&xsec_source=pc_feed"

    r = _SESSION.get(
        url,
        headers={
            "User-Agent": UA_CHROME,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.xiaohongshu.com/",
        },
        timeout=15,
    )
    return r.text


# ────────────────────────────────────────────────────────────────────────────
# 工具：INITIAL_STATE JSON 提取
# ────────────────────────────────────────────────────────────────────────────
def _clean_js_json(raw: str) -> str:
    """把 JS 非 JSON 字面量清理为合法 JSON（undefined→null, !0→true, !1→false）"""
    raw = re.sub(r'([:,]\s*)undefined(\s*[,\]})])', r'\1null\2', raw)
    raw = re.sub(r'\[undefined\]', '[null]', raw)
    raw = re.sub(r':!0([,\]}])', r':true\1', raw)
    raw = re.sub(r':!1([,\]}])', r':false\1', raw)
    return raw


def _extract_init_state(html: str) -> dict:
    """从页面 HTML 中提取 window.__INITIAL_STATE__ JSON"""
    key = "__INITIAL_STATE__"
    idx = html.find(key)
    if idx == -1:
        return {}
    start = html.find("=", idx) + 1
    while start < len(html) and html[start] in " \t\r\n":
        start += 1
    end = html.find("</script>", start)
    if end == -1:
        return {}
    raw = html[start:end].rstrip().rstrip(";").strip()
    if not raw:
        return {}
    try:
        return json.loads(_clean_js_json(raw))
    except Exception:
        return {}


# ────────────────────────────────────────────────────────────────────────────
# 工具：图片 / 视频 URL 提取
# ────────────────────────────────────────────────────────────────────────────
def _image_token(url: str) -> str:
    """
    从 CDN 图片 URL 提取资源 token。
    例：http://sns-webpic-qc.xhscdn.com/日期/hash/notes_pre_post/xxx!nd_dft_wlteh_jpg_3
        → notes_pre_post/xxx
    """
    try:
        return "/".join(url.split("/")[5:]).split("!")[0]
    except Exception:
        m = re.search(r'/([^/]+/[^/]+)![^/]*$', url)
        return m.group(1) if m else ""


def _original_image_url(url: str) -> str:
    """由 CDN URL 生成无压缩原图 URL；失败则原样返回"""
    token = _image_token(url)
    if token and "://" not in token:
        return f"{ORIGIN_IMG_HOST}/{token}"
    return url


def _best_image_url(img: dict) -> str:
    """
    从 imageList 单个元素中挑选最佳展示图片 URL。
    优先 WB_DFT（默认清晰度），其次 infoList 靠后的高清场景，兜底 urlDefault。
    """
    info = img.get("infoList") or []
    if info:
        # 按清晰度优先级挑选
        for scene in ("WB_ORIGIN", "WB_HD", "WB_DFT"):
            for x in info:
                if x.get("imageScene") == scene and x.get("url"):
                    return x["url"]
        # 取最后一个非空 url（通常更清晰）
        urls = [x.get("url") for x in info if x.get("url")]
        if urls:
            return urls[-1]
    return img.get("urlDefault") or img.get("url") or ""


def _pick_stream_url(stream: dict) -> str:
    """从 stream（h264/h265/h266）中挑一个可用的视频 URL"""
    for codec in ("h264", "h265", "h266"):
        arr = stream.get(codec) or []
        for item in arr:
            if not isinstance(item, dict):
                continue
            if item.get("masterUrl"):
                return item["masterUrl"]
            bu = item.get("backupUrls") or []
            if bu and bu[0]:
                return bu[0]
    return ""


def _extract_live_video(img: dict) -> str:
    """
    从 imageList 单个元素中提取动图(Live Photo)视频 URL。
    兼容多种形态：
      - livePhoto: {video: {media: {stream: {h264: [...]}}}}
      - livePhoto: "https://..."（直接是 URL）
      - 元素自身带 stream: {h264: [...]}（API 风格）
    """
    lp = img.get("livePhoto")
    if isinstance(lp, str):
        return lp.strip()
    if isinstance(lp, dict):
        vv = lp.get("video") or {}
        media = vv.get("media") or {}
        url = _pick_stream_url(media.get("stream") or {})
        if url:
            return url
        for k in ("url", "videoUrl", "mainUrl"):
            if lp.get(k):
                return lp[k]
    # 元素自身带 stream（部分接口形态）
    stream = img.get("stream") or {}
    return _pick_stream_url(stream)


def _best_video_url(note: dict):
    """
    从 note.video 提取最佳视频 URL。
    返回 (url, backup_url, width, height, quality)
    """
    video = note.get("video") or {}
    media = video.get("media") or {}
    stream = media.get("stream") or {}

    candidates = []  # (rank, codec, item)
    rank_map = {"4k": 5, "fhd": 4, "hd": 3, "sd": 2}
    for codec in ("h264", "h265", "h266"):
        for item in stream.get(codec) or []:
            if not isinstance(item, dict):
                continue
            if not (item.get("masterUrl") or item.get("backupUrls")):
                continue
            q = str(item.get("qualityType") or "").lower()
            rank = rank_map.get(q, 1)
            candidates.append((rank, codec, item))

    if not candidates:
        return "", "", 0, 0, ""

    candidates.sort(key=lambda x: x[0], reverse=True)
    _, _, best = candidates[0]
    url = best.get("masterUrl") or ""
    bu  = best.get("backupUrls") or []
    backup = bu[0] if bu else ""
    return (
        url,
        backup,
        int(best.get("width") or 0),
        int(best.get("height") or 0),
        str(best.get("qualityType") or ""),
    )


# ────────────────────────────────────────────────────────────────────────────
# 主解析：INITIAL_STATE
# ────────────────────────────────────────────────────────────────────────────
def _parse_init_state(state: dict, note_id: str) -> dict:
    """从 __INITIAL_STATE__ 中解析笔记结构化数据"""
    note_map = (state.get("note") or {}).get("noteDetailMap") or {}
    note = None
    if note_id and note_id in note_map:
        note = note_map[note_id].get("note") or {}
    elif note_map:
        note = list(note_map.values())[0].get("note") or {}
    if not note:
        raise ValueError("页面中未找到笔记数据")

    nid = note.get("noteId") or note_id
    title = note.get("title") or ""
    desc  = note.get("desc") or ""
    user  = note.get("user") or {}
    author = user.get("nickname") or user.get("nickName") or "小红书用户"
    ntype = note.get("type") or "normal"   # video / normal

    image_list = note.get("imageList") or []

    # ── 视频笔记 ─────────────────────────────────────────────────────────────
    if ntype == "video":
        url, backup, w, h, quality = _best_video_url(note)
        if not url:
            raise ValueError("视频笔记中未找到视频播放地址")
        cover = _best_image_url(image_list[0]) if image_list else ""
        media_items = [{
            "type":     "video",
            "url":      url,
            "fallback": backup,
            "thumb":    cover,
            "index":    0,
            "quality":  quality,
        }]
        return {
            "platform":     "xiaohongshu",
            "type":         "video",
            "note_id":      nid,
            "title":        title,
            "author":       author,
            "cover_url":    cover,
            "media_items":  media_items,
            "text":         desc or title,
            "no_watermark": True,
            "width":        w,
            "height":       h,
        }

    # ── 图文笔记（静态图 / 动图）────────────────────────────────────────────
    media_items = []
    has_live = False
    for i, img in enumerate(image_list):
        display_url = _best_image_url(img)          # 压缩展示图（做缩略图）
        origin_url  = _original_image_url(display_url)  # 无压缩原图（下载）
        live_url    = _extract_live_video(img)      # 动图视频

        if live_url:
            has_live = True
            media_items.append({
                "type":     "live_photo",
                "url":      live_url,
                "fallback": "",
                "thumb":    display_url,
                "index":    i,
            })
        else:
            media_items.append({
                "type":     "image",
                "url":      origin_url,
                "fallback": display_url,
                "thumb":    display_url,
                "index":    i,
            })

    if not media_items:
        raise ValueError("页面中未找到任何图片或视频内容，可能该笔记需要登录才能查看。")

    cover = media_items[0]["thumb"]
    content_type = "live_photo" if has_live else "image"

    return {
        "platform":     "xiaohongshu",
        "type":         content_type,
        "note_id":      nid,
        "title":        title,
        "author":       author,
        "cover_url":    cover,
        "media_items":  media_items,
        "text":         desc or title,
        "no_watermark": True,
        "width":        0,
        "height":       0,
    }


# ────────────────────────────────────────────────────────────────────────────
# 备方案：正则解析（INITIAL_STATE 缺失时兜底）
# ────────────────────────────────────────────────────────────────────────────
def _parse_regex(html: str, note_id: str) -> dict:
    """INITIAL_STATE 解析失败时，用正则从 HTML 提取（兼容旧逻辑 + \u002F 转义修复）"""
    if len(html) < 1000:
        raise RuntimeError("页面返回内容异常，可能被风控拦截，请稍后再试。")

    # 先把 \u002F 等 unicode 转义还原，让视频 URL 可被正则匹配
    unescaped = html.encode("utf-8").decode("unicode_escape", errors="ignore")

    og_images = re.findall(
        r'<meta\s+(?:property|name)=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE)
    og_images = [
        u for u in og_images
        if ("sns-webpic-qc" in u or "xhscdn" in u or "ci.xiaohongshu.com" in u)
        and "picasso-static" not in u and "fe-platform" not in u
    ]

    # 动图 livePhoto（转义后匹配）
    live_photos = re.findall(r'"livePhoto"\s*:\s*"([^"]+)"', unescaped)
    live_photos = [u for u in live_photos if u.strip()]

    # 视频 masterUrl（转义后匹配）
    video_url = ""
    for key in ("masterUrl", "master_url", "backupUrl", "backup_url"):
        m = re.search(rf'"{key}"\s*:\s*"(https?://[^"]+\.mp4[^"]*)"', unescaped)
        if m:
            video_url = m.group(1)
            break
    if not video_url:
        m = re.search(r'"(https?://[^\s"\'<>]+\.mp4[^"\'<>\s]*)"', unescaped)
        if m:
            video_url = m.group(1)

    # 元数据
    title_m = re.search(
        r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE)
    title = title_m.group(1) if title_m else ""

    author = ""
    ld_m = re.search(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE)
    if ld_m:
        try:
            ld = json.loads(ld_m.group(1))
            author = ld.get("author", {}).get("name", "")
        except Exception:
            pass

    if video_url:
        cover = og_images[0] if og_images else ""
        return {
            "platform": "xiaohongshu", "type": "video", "note_id": note_id,
            "title": title, "author": author or "小红书用户",
            "cover_url": cover,
            "media_items": [{"type": "video", "url": video_url, "fallback": "", "thumb": cover, "index": 0}],
            "text": title, "no_watermark": True, "width": 0, "height": 0,
        }

    media_items = []
    has_live = False
    if live_photos:
        has_live = True
        for i, lp_url in enumerate(live_photos):
            thumb = og_images[i] if i < len(og_images) else (og_images[0] if og_images else "")
            media_items.append({
                "type": "live_photo", "url": lp_url, "fallback": "",
                "thumb": thumb, "index": i,
            })
        for i in range(len(live_photos), len(og_images)):
            media_items.append({
                "type": "image", "url": _original_image_url(og_images[i]),
                "fallback": og_images[i], "thumb": og_images[i], "index": i,
            })
    elif og_images:
        for i, u in enumerate(og_images):
            media_items.append({
                "type": "image", "url": _original_image_url(u),
                "fallback": u, "thumb": u, "index": i,
            })

    if not media_items:
        raise RuntimeError("页面中未找到任何图片或视频内容，可能该笔记需要登录才能查看。")

    return {
        "platform": "xiaohongshu", "type": "live_photo" if has_live else "image",
        "note_id": note_id, "title": title, "author": author or "小红书用户",
        "cover_url": og_images[0] if og_images else "",
        "media_items": media_items, "text": title,
        "no_watermark": True, "width": 0, "height": 0,
    }


# ────────────────────────────────────────────────────────────────────────────
# 风控 / 404 检测
# ────────────────────────────────────────────────────────────────────────────
_BLOCK_KEYWORDS = (
    "安全验证", "验证码", "滑块", "captcha", "sec_verify",
    "访问过于频繁", "请求过于频繁",
    "登录后查看", "登录后即可",
)


def _check_page(html: str, final_url: str):
    if "/404" in final_url or "笔记不存在" in html or len(html) < 1000:
        raise RuntimeError(
            "笔记不存在或链接缺少访问凭证（xsec_token）。\n"
            "请重新从小红书 App 复制分享链接（含完整 xsec_token）。"
        )
    for kw in _BLOCK_KEYWORDS:
        if kw in html:
            raise RuntimeError(f"触发小红书风控（{kw}），请稍后再试或更换网络。")
    if "登录" in html and "noteDetailMap" not in html and "__INITIAL_STATE__" not in html:
        raise RuntimeError("该笔记需要登录才能查看，请在配置中填入小红书 Cookie。")


# ────────────────────────────────────────────────────────────────────────────
# 主入口
# ────────────────────────────────────────────────────────────────────────────
def parse(text_or_url: str) -> dict:
    """
    主入口：解析小红书分享链接（支持整段分享文案自动识别链接）。
    支持 短链(xhslink) / 长链(discovery|explore) / 图文 / 动图 / 视频。
    """
    raw = (text_or_url or "").strip()
    if not raw:
        raise ValueError("请输入小红书分享链接。")

    url = extract_url(raw)
    if "xiaohongshu.com" not in url and "xhslink.com" not in url and "xhs.cn" not in url:
        raise ValueError("未识别到有效的小红书链接，请检查输入内容。")

    # 1. 解析链接 → note_id + xsec_token
    final_url, note_id, xsec_token = _resolve_link(url)
    if not note_id:
        raise ValueError("无法从链接中解析笔记 ID，请检查链接是否正确。")
    if not xsec_token:
        # 小红书笔记页必须携带 xsec_token，缺失会 404 —— 直接给出清晰提示，省去无效请求
        raise RuntimeError(
            "链接缺少访问凭证（xsec_token）。\n"
            "请重新从小红书 App 复制分享链接（含完整 xsec_token）。"
        )

    # 2. 获取页面
    html = _fetch_note_page(note_id, xsec_token)
    _check_page(html, final_url)

    # 3. 主方案：INITIAL_STATE
    state = _extract_init_state(html)
    if state:
        try:
            return _parse_init_state(state, note_id)
        except ValueError:
            raise
        except Exception:
            pass  # 结构变化 → 走兜底

    # 4. 备方案：正则解析
    return _parse_regex(html, note_id)


# ────────────────────────────────────────────────────────────────────────────
# 命令行测试
# ────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    test_input = sys.argv[1] if len(sys.argv) > 1 else "http://xhslink.com/o/S2vvPNXBTw"
    try:
        result = parse(test_input)
        print(f"平台: {result['platform']}")
        print(f"类型: {result['type']}")
        print(f"作者: {result['author']}")
        print(f"标题: {result['title'][:60]}")
        print(f"媒体数量: {len(result['media_items'])}")
        for item in result["media_items"]:
            print(f"  [{item['index']}] {item['type']}: {item['url'][:90]}...")
    except Exception as e:
        print(f"解析失败: {e}")
        import traceback; traceback.print_exc()
