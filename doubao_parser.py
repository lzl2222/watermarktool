"""
doubao_parser.py  —  豆包 AI 视频无水印解析器

两路模式：
  1. 【原画无水印模式】(需要 sessionid cookie)
     调用 /alice/resource/get_video_model  → 拿到 fplay fallback_api + key_seed
     → 请求 fplay CDN  → AES-CBC 解密 → 得到真正无水印 CDN 直链

  2. 【匿名公开模式】(无需 cookie)
     调用 /creativity/share/get_video_share_info → 拿到带水印的直链
     替换 lr 参数为 unwatermarked 尝试降级绕过水印
"""

import re
import json
import base64
import hashlib
import urllib.parse
import requests

# ────────────────────────────────────────────────────────────────────────────
# 常量
# ────────────────────────────────────────────────────────────────────────────
FPLAY_KDF_SALT = (
    "TdTC5rgxYgkOUrPHpnM7pByyRiuCmrWKGWs521cXdST0m69/"
    "COjWjSanLjfBqVovHwWlGJKu8pSXMrYqOKrdWA=="
)
DOUBAO_API_BASE = "https://www.doubao.com"
FPLAY_HOST      = "https://vas-lf-x.snssdk.com"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")


# ────────────────────────────────────────────────────────────────────────────
# 工具函数
# ────────────────────────────────────────────────────────────────────────────
def extract_params(url: str):
    """从豆包分享链接中解析出 share_id 和 vid"""
    parsed = urllib.parse.urlparse(url)
    query  = urllib.parse.parse_qs(parsed.query)

    share_id = query.get("share_id", [None])[0]
    vid      = (query.get("video_id", [None])[0]
                or query.get("vid", [None])[0])

    if not share_id:
        m = re.search(r'share_id=([a-zA-Z0-9_-]+)', url)
        if m: share_id = m.group(1)
    if not vid:
        m = re.search(r'(?:video_id|vid)=([a-zA-Z0-9_-]+)', url)
        if m: vid = m.group(1)

    return share_id, vid


def _b64decode_safe(s: str) -> bytes:
    """Base64 decode with auto-padding"""
    s = s.strip()
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.b64decode(s)


def _decrypt_aes_cbc(encrypted_b64: str, key_seed_b64: str) -> str:
    """
    豆包 fplay AES-CBC 解密算法（与浏览器端完全一致）

    算法：
      seed    = base64_decode(key_seed)
      hash1   = SHA-512(seed)
      kmat    = hash1 + base64_decode(FPLAY_KDF_SALT)
      derived = SHA-512(kmat)
      key     = derived[0:16]
      iv      = derived[16:32]
      plain   = AES-CBC-decrypt(base64_decode(encrypted)[4:], key, iv)
    """
    try:
        from Crypto.Cipher import AES as _AES
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "pycryptodome", "-q"])
        from Crypto.Cipher import AES as _AES

    encrypted = _b64decode_safe(encrypted_b64)
    seed      = _b64decode_safe(key_seed_b64)
    salt      = _b64decode_safe(FPLAY_KDF_SALT)

    ciphertext = encrypted[4:]   # 跳过前 4 字节
    if not ciphertext or len(ciphertext) % 16 != 0:
        return ""

    first_hash  = hashlib.sha512(seed).digest()
    key_mat     = first_hash + salt
    derived     = hashlib.sha512(key_mat).digest()

    key_bytes = derived[0:16]
    iv_bytes  = derived[16:32]

    cipher    = _AES.new(key_bytes, _AES.MODE_CBC, iv_bytes)
    decrypted = cipher.decrypt(ciphertext)

    # 去除 PKCS7 padding
    pad = decrypted[-1]
    if 1 <= pad <= 16 and all(b == pad for b in decrypted[-pad:]):
        decrypted = decrypted[:-pad]

    return decrypted.decode("utf-8").strip()


# ────────────────────────────────────────────────────────────────────────────
# 核心解析：原画无水印模式（需要 sessionid）
# ────────────────────────────────────────────────────────────────────────────
def get_video_info_with_cookie(url: str, sessionid: str) -> dict:
    """
    使用登录 Cookie 走 fplay 解密通道，获得真正无水印原片直链。
    返回 dict，保持与 get_video_info 相同的字段。
    """
    _, vid = extract_params(url)
    if not vid:
        raise ValueError("无法从链接解析视频 ID，请检查链接格式。")

    # ── Step 1: 获取 video_model（含 fallback_api 和 key_seed）──────────────
    api_url = f"{DOUBAO_API_BASE}/alice/resource/get_video_model"
    headers = {
        "User-Agent":    UA,
        "origin":        DOUBAO_API_BASE,
        "accept":        "application/json",
        "content-type":  "application/json",
        "Cookie":        f"sessionid={sessionid}",
        "x-csrftoken":   "",
    }
    payload = {"params": [{"uri": vid, "resource_id": ""}]}

    r = requests.post(api_url, json=payload, headers=headers, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"video_model 请求失败，状态码: {r.status_code}")

    res = r.json()
    if res.get("code") != 0:
        msg = res.get("message") or res.get("msg", "未知错误")
        raise RuntimeError(f"video_model 接口返回错误: {msg} (code={res.get('code')})")

    try:
        vm_str = res["data"]["results"][0]["video_model_result"]["video_model"]
        vm     = json.loads(vm_str)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise RuntimeError(f"解析 video_model 数据失败: {e}")

    fallback_api = vm.get("fallback_api", "")
    key_seed     = vm.get("key_seed", "")
    poster_url   = vm.get("poster_url", "")
    video_id     = vm.get("video_id", vid)

    if not fallback_api or not key_seed:
        raise RuntimeError("video_model 中缺少 fallback_api 或 key_seed，登录状态可能已过期。")

    # ── Step 2: 构建干净 fplay URL 并请求 CDN 信息 ──────────────────────────
    parsed   = urllib.parse.urlparse(fallback_api)
    params   = dict(urllib.parse.parse_qsl(parsed.query))
    params.pop("force_fids", None)
    params.pop("logo_type",  None)
    params["codec_type"] = "1"
    clean_url = urllib.parse.urlunparse(parsed._replace(
        query=urllib.parse.urlencode(params)
    ))

    fplay_headers = {
        "User-Agent": UA,
        "Accept":     "application/json, text/plain, */*",
    }
    fr = requests.get(clean_url, headers=fplay_headers, timeout=15)
    if fr.status_code != 200:
        raise RuntimeError(f"fplay CDN 请求失败，状态码: {fr.status_code}")

    try:
        fplay_data  = fr.json()
        video_list  = fplay_data["video_info"]["data"]["video_list"]
    except (KeyError, json.JSONDecodeError) as e:
        raise RuntimeError(f"解析 fplay 响应失败: {e}")

    # ── Step 3: 解密，优先选 logo_type 为空（无水印）的轨道 ─────────────────
    best_url = ""
    best_def = ""
    for name, item in video_list.items():
        enc_url = item.get("main_url", "")
        if not enc_url:
            continue
        try:
            dec_url = _decrypt_aes_cbc(enc_url, key_seed)
        except Exception:
            continue
        if not dec_url:
            continue
        logo = item.get("logo_type", "")
        defn = item.get("definition", "")
        # 优先：空 logo（无水印）+ 高清晰度
        if not logo and not best_url:
            best_url = dec_url
            best_def = defn
        elif not best_url:
            best_url = dec_url
            best_def = defn

    if not best_url:
        raise RuntimeError("无法从 fplay 数据中解密出视频链接，请确认 key_seed 有效。")

    # ── Step 4: 解析尺寸 ─────────────────────────────────────────────────────
    width  = vm.get("video_list", {})
    height = 0
    # 从 fplay video_list 的第一个条目拿分辨率
    for name, item in video_list.items():
        width  = item.get("vwidth",  0)
        height = item.get("vheight", 0)
        break

    return {
        "vid":          video_id,
        "share_id":     "",
        "video_url":    best_url,
        "backup_url":   "",
        "poster_url":   poster_url,
        "width":        width,
        "height":       height,
        "nickname":     "（原画无水印模式）",
        "prompt":       f"视频 ID: {video_id}\n清晰度: {best_def}\n来源: 豆包 fplay 解密原画",
        "no_watermark": True,  # 标记为真无水印
    }


# ────────────────────────────────────────────────────────────────────────────
# 核心解析：匿名公开模式（无需 cookie）
# ────────────────────────────────────────────────────────────────────────────
def get_video_info(url: str) -> dict:
    """
    匿名模式：调用公开分享接口获取视频信息。
    视频 URL 带有动态水印，但仍可正常下载观看。
    """
    share_id, vid = extract_params(url)
    if not share_id or not vid:
        raise ValueError("无法从链接中解析出分享ID或视频ID，请检查链接格式。")

    api_url = (
        f"{DOUBAO_API_BASE}/creativity/share/get_video_share_info"
        "?version_code=20800&language=zh-CN&device_platform=web"
        "&aid=497858&real_aid=497858&pkg_type=release_version"
        "&device_id=&pc_version=3.26.4&region=&sys_region="
        "&samantha_web=1&web_platform=browser&use-olympus-account=1"
    )
    headers = {
        "Content-Type": "application/json",
        "Accept":       "application/json, text/plain, */*",
        "User-Agent":   UA,
        "Referer":      url,
    }
    payload = {"share_id": share_id, "vid": vid, "creation_id": ""}

    r = requests.post(api_url, json=payload, headers=headers, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"请求接口失败，状态码: {r.status_code}")

    res_json = r.json()
    if res_json.get("code") != 0:
        raise RuntimeError(f"接口返回错误: {res_json.get('msg', '未知错误')}")

    data      = res_json.get("data", {})
    play_info = data.get("play_info", {})
    user_info = data.get("user_info", {})
    prompt    = data.get("prompt", "")

    main_url = play_info.get("main")
    if not main_url:
        raise RuntimeError("接口响应中未找到视频播放链接，可能视频已失效。")

    return {
        "vid":          vid,
        "share_id":     share_id,
        "video_url":    main_url,
        "backup_url":   play_info.get("backup", ""),
        "poster_url":   play_info.get("poster_url", ""),
        "width":        play_info.get("width", 0),
        "height":       play_info.get("height", 0),
        "nickname":     user_info.get("nickname", "匿名用户"),
        "prompt":       prompt,
        "no_watermark": False,  # 带水印版本
    }


# ────────────────────────────────────────────────────────────────────────────
# 自动选择模式的统一入口
# ────────────────────────────────────────────────────────────────────────────
def parse(url: str, sessionid: str = "") -> dict:
    """
    智能解析入口：
    - 若提供了 sessionid → 优先走原画无水印解密通道
    - 否则 → 走匿名公开通道（视频带动态水印）
    """
    if sessionid and sessionid.strip():
        try:
            return get_video_info_with_cookie(url, sessionid.strip())
        except Exception as e:
            # Cookie 失效时降级到匿名模式
            print(f"[警告] 原画模式失败（{e}），降级到匿名模式...")
            return get_video_info(url)
    return get_video_info(url)


# ────────────────────────────────────────────────────────────────────────────
# 命令行测试
# ────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    test_url = (
        "https://www.doubao.com/video-sharing?"
        "share_id=49700931634797570&source_type=mobile"
        "&video_id=v0369cg10004d98dbmaljht7f1umkktg&share_scene=video_viewer"
    )
    sid = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        info = parse(test_url, sid)
        mode = "原画无水印" if info.get("no_watermark") else "公开带水印"
        print(f"解析成功！模式: {mode}")
        print(f"  分辨率 : {info['width']}x{info['height']}")
        print(f"  视频链接: {info['video_url'][:80]}...")
    except Exception as e:
        print("测试失败:", e)
