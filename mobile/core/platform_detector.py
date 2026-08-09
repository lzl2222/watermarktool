# -*- coding: utf-8 -*-
"""
platform_detector.py — 自动识别分享链接所属平台

支持：
  doubao       豆包 AI 视频
  xiaohongshu  小红书（图文/动态图/视频）
  douyin       抖音
  unknown      未识别
"""

import re


# 通用 URL 识别（从整段分享文本中提取链接）
_URL_RE = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
_TRAILING = ".,;:!?)]}》】】。，；：！？、…"


def extract_url(text: str) -> str:
    """
    从粘贴的分享文本中自动提取链接（兼容整段复制的分享文案）。
    找不到链接时原样返回。
    """
    text = (text or "").strip()
    m = _URL_RE.search(text)
    if not m:
        return text
    url = m.group(0).rstrip(_TRAILING)
    while url and url[-1] in ")]}>」』】】":
        url = url[:-1]
    return url.strip()


def detect(url: str) -> str:
    """
    根据 URL 返回平台名称字符串。
    返回值: 'doubao' | 'xiaohongshu' | 'douyin' | 'unknown'
    """
    url = (url or "").strip().lower()

    # ── 豆包 ──────────────────────────────────────────────────────────────────
    if any(d in url for d in ["doubao.com", "doubao.cn"]):
        return "doubao"

    # ── 小红书 ────────────────────────────────────────────────────────────────
    if any(d in url for d in [
        "xhslink.com", "xhslink.cn", "xiaohongshu.com", "xhs.cn", "xhscdn.com",
    ]):
        return "xiaohongshu"

    # ── 抖音 ──────────────────────────────────────────────────────────────────
    if any(d in url for d in [
        "v.douyin.com", "www.douyin.com", "iesdouyin.com", "douyin.com",
    ]):
        return "douyin"

    return "unknown"


# 平台元数据（用于 UI 显示）
PLATFORM_META = {
    "doubao": {
        "name": "豆包 AI",
        "icon": "🤖",
        "color": "#1890ff",
        "badge_color": "#003a8c",
    },
    "xiaohongshu": {
        "name": "小红书",
        "icon": "📕",
        "color": "#ff2442",
        "badge_color": "#7b0a1e",
    },
    "douyin": {
        "name": "抖音",
        "icon": "🎵",
        "color": "#161823",
        "badge_color": "#010101",
    },
    "unknown": {
        "name": "未知平台",
        "icon": "❓",
        "color": "#666666",
        "badge_color": "#333333",
    },
}


def get_meta(platform: str) -> dict:
    return PLATFORM_META.get(platform, PLATFORM_META["unknown"])


if __name__ == "__main__":
    test_urls = [
        "https://www.doubao.com/video-sharing?share_id=xxx",
        "http://xhslink.com/o/S2vvPNXBTw",
        "https://www.xiaohongshu.com/explore/69d8853a000000001f00443b",
        "https://v.douyin.com/iBkepGkP/",
        "https://www.google.com/",
        "70 【胖墩墩…太空飞艇 - 言灵福克斯 | 小红书】 😆 By7Wzw5Q0UMaguy 😆 https://www.xiaohongshu.com/discovery/item/6a715c100000000033009d1b?xsec_token=abc=",
    ]
    for u in test_urls:
        p = detect(u)
        m = get_meta(p)
        print(f"{m['icon']} [{p}] {u[:50]}")
    print("\n-- extract_url 测试 --")
    print(extract_url("70 【标题】 😆 口令 😆 https://www.xiaohongshu.com/discovery/item/6a715c100000000033009d1b?xsec_token=abc=&xsec_source=pc_share"))
