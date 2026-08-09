"""
douyin_parser.py — 抖音视频无水印解析器

技术方案（双重保障）：
  主方案：使用公共解析接口 api.douyin.wtf（免费、无需登录）
  备方案：跟随短链→提取 video_id→iesdouyin share 页→解析 meta 标签

返回统一格式 dict：
  {
    "platform":    "douyin",
    "type":        "video",
    "video_id":    str,
    "author":      str,
    "cover_url":   str,
    "media_items": [ { type, url, thumb } ],
    "text":        str,
    "no_watermark": True,
    "width":       int,
    "height":      int,
  }
"""

import re
import json
import urllib.parse
import requests

UA_CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)

# ─────────────────────────── 工具函数 ───────────────────────────────────────

def _resolve_video_id(url: str) -> tuple[str, str]:
    """
    跟随重定向解析出 video_id 和最终 URL。
    返回 (video_id, final_url)
    """
    sess = requests.Session()
    r = sess.get(
        url,
        headers={"User-Agent": UA_CHROME},
        allow_redirects=True,
        timeout=12,
    )
    final_url = r.url

    # 从 URL 路径提取 video_id
    # 格式: /video/{id}/ 或 /share/video/{id}/
    for pat in [
        r'/video/(\d+)',
        r'/share/video/(\d+)',
        r'aweme_id=(\d+)',
    ]:
        m = re.search(pat, final_url)
        if m:
            return m.group(1), final_url

    # 备用：从原始 URL 提取（v.douyin.com 不会在 URL 中含 ID，但有时 UA 不同会跳转）
    for pat in [r'/video/(\d+)', r'/share/video/(\d+)', r'aweme_id=(\d+)']:
        m = re.search(pat, url)
        if m:
            return m.group(1), final_url

    return "", final_url


# ─────────────────────────── 主方案：公共 API ────────────────────────────────

def _parse_via_public_api(share_url: str) -> dict:
    """
    使用 api.douyin.wtf 公共接口解析抖音分享链接。
    """
    api_endpoints = [
        f"https://api.douyin.wtf/api?url={urllib.parse.quote(share_url)}&minimal=false",
        f"https://api.douyin.wtf/api/hybrid/video_data?url={urllib.parse.quote(share_url)}",
    ]

    for api_url in api_endpoints:
        try:
            r = requests.get(
                api_url,
                headers={
                    "User-Agent": UA_CHROME,
                    "Accept": "application/json",
                    "Referer": "https://www.douyin.com/",
                },
                timeout=12,
            )
            if r.status_code != 200:
                continue

            data = r.json()

            # 检查是否成功
            if data.get("code", data.get("status_code", -1)) not in (0, 200, "200"):
                continue

            # 提取视频 URL（无水印）
            video_url = (
                data.get("video_url_no_watermark")
                or data.get("video_url")
                or data.get("url")
                or ""
            )

            # 适配不同接口响应结构
            if not video_url:
                # 尝试从 aweme_detail 路径提取
                detail = data.get("aweme_detail") or data.get("data", {})
                video  = detail.get("video", {})
                addr   = video.get("play_addr", video.get("download_addr", {}))
                urls   = addr.get("url_list", [])
                video_url = urls[0] if urls else ""

            if not video_url:
                continue

            # 封面图
            cover_url = data.get("cover") or data.get("origin_cover") or ""
            if not cover_url:
                detail   = data.get("aweme_detail") or data.get("data", {})
                cover    = detail.get("video", {}).get("cover", {})
                url_list = cover.get("url_list", [])
                cover_url = url_list[0] if url_list else ""

            # 作者
            author = (
                data.get("author")
                or data.get("nickname")
                or (data.get("aweme_detail") or {}).get("author", {}).get("nickname", "")
                or "抖音用户"
            )

            # 标题/描述
            desc = data.get("desc") or data.get("title") or ""

            # 尺寸
            width  = data.get("video_width",  0)
            height = data.get("video_height", 0)

            # 无水印处理：去掉 URL 中的水印标记
            video_url = _remove_wm_from_url(video_url)

            return {
                "platform":    "douyin",
                "type":        "video",
                "video_id":    data.get("aweme_id", ""),
                "author":      str(author),
                "cover_url":   cover_url,
                "media_items": [{
                    "type":  "video",
                    "url":   video_url,
                    "thumb": cover_url,
                }],
                "text":        desc,
                "no_watermark": True,
                "width":       width,
                "height":      height,
            }

        except Exception:
            continue

    raise RuntimeError("公共 API 解析失败，请稍后再试或检查链接是否有效。")


# ─────────────────────────── 备方案：iesdouyin share 页 ─────────────────────

def _parse_via_share_page(share_url: str) -> dict:
    """
    备用方案：请求 iesdouyin share 页，从 meta 标签提取视频信息。
    """
    video_id, final_url = _resolve_video_id(share_url)
    if not video_id:
        raise RuntimeError("无法从链接解析 video_id，请检查链接格式。")

    share_page_url = f"https://www.iesdouyin.com/share/video/{video_id}/"

    # 先获取 ttwid cookie
    sess = requests.Session()
    try:
        sess.get(
            "https://www.iesdouyin.com",
            headers={"User-Agent": UA_MOBILE},
            timeout=8,
        )
    except Exception:
        pass

    r = sess.get(
        share_page_url,
        headers={
            "User-Agent": UA_CHROME,
            "Referer": "https://www.douyin.com/",
        },
        timeout=12,
    )
    html = r.text

    # 从 og:video meta 提取视频 URL
    video_url = ""
    for pat in [
        r'<meta\s+property="og:video(?::url)?"\s+content="([^"]+)"',
        r'<meta\s+name="og:video"\s+content="([^"]+)"',
        r'"video_url"\s*:\s*"([^"]+)"',
    ]:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            video_url = m.group(1)
            break

    # 封面图
    cover_url = ""
    m = re.search(
        r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.IGNORECASE
    )
    if m:
        cover_url = m.group(1)

    # 标题
    title = ""
    m = re.search(
        r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.IGNORECASE
    )
    if m:
        title = m.group(1)

    if not video_url:
        raise RuntimeError(
            "Share 页解析失败，页面未找到视频链接（可能受反爬保护）。"
        )

    video_url = _remove_wm_from_url(video_url)

    return {
        "platform":    "douyin",
        "type":        "video",
        "video_id":    video_id,
        "author":      "抖音用户",
        "cover_url":   cover_url,
        "media_items": [{
            "type":  "video",
            "url":   video_url,
            "thumb": cover_url,
        }],
        "text":        title,
        "no_watermark": True,
        "width":       0,
        "height":      0,
    }


def _remove_wm_from_url(url: str) -> str:
    """
    尝试将抖音 CDN URL 中的水印标记去除。
    playwm → play
    """
    url = url.replace("playwm", "play")
    # 移除 watermark 相关参数
    url = re.sub(r'[?&]wm=[^&]*', '', url)
    return url


# ─────────────────────────── 主入口 ─────────────────────────────────────────

def parse(url: str) -> dict:
    """
    主入口：自动尝试公共 API → 备方案 share 页解析。
    """
    # 主方案：公共 API
    try:
        return _parse_via_public_api(url)
    except Exception as e1:
        pass

    # 备方案：share 页解析
    try:
        return _parse_via_share_page(url)
    except Exception as e2:
        raise RuntimeError(
            f"抖音视频解析失败。\n"
            f"公共API失败，Share页也失败：{e2}\n"
            f"请确认链接是否有效，或稍后再试。"
        )


# ─────────────────────────── 命令行测试 ─────────────────────────────────────

if __name__ == "__main__":
    import sys
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://v.douyin.com/iBkepGkP/"
    try:
        result = parse(test_url)
        print(f"平台: {result['platform']}")
        print(f"类型: {result['type']}")
        print(f"作者: {result['author']}")
        print(f"描述: {result['text'][:60]}")
        print(f"无水印: {result['no_watermark']}")
        for item in result["media_items"]:
            print(f"  视频URL: {item['url'][:80]}...")
    except Exception as e:
        print(f"解析失败: {e}")
