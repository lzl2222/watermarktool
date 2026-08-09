# -*- coding: utf-8 -*-
"""
theme.py — 苹果液态玻璃（Liquid Glass）主题

提供两套配色：浅色玻璃（Apple 经典） / 深色玻璃（Tahoe 深色模式）。
由于 tkinter 不支持真实的背景模糊，用「半透明白色面板 + 细描边 + 大圆角 +
渐变玻璃头部」来模拟液态玻璃质感。
"""

import customtkinter as ctk
from PIL import Image


# ────────────────────────────────────────────────────────────────────────────
# 主题定义
# ────────────────────────────────────────────────────────────────────────────
THEMES = {
    # ── 浅色液态玻璃（Apple Liquid Glass 经典）──────────────────────────────
    "glass_light": {
        "name":          "液态玻璃 · 浅色",
        "appearance":    "light",
        # 窗口背景（Apple 系统灰）
        "window_bg":     "#F2F2F7",
        # 玻璃面板
        "panel":         "#FFFFFF",
        "panel_alt":     "#F7F7FA",
        "panel_border":  "#E3E3EC",
        # 输入框
        "entry":         "#FFFFFF",
        "entry_border":  "#D8D8E3",
        # 文字
        "text":          "#1D1D1F",
        "text_sec":      "#6E6E73",
        "text_faint":    "#A2A2AC",
        "placeholder":   "#B8B8C4",
        # 强调色（Apple 蓝 / 紫）
        "accent":        "#007AFF",
        "accent_hover":  "#0060DF",
        "accent_soft":   "#EAF3FF",
        "accent2":       "#AF52DE",
        # 状态色
        "ok":            "#34C759",
        "err":           "#FF3B30",
        "warn":          "#FF9500",
        # 头部渐变（柔和的玻璃彩虹）
        "header_grad":   [(88, 138, 255), (130, 120, 255), (210, 120, 220), (255, 138, 178)],
        "header_text":   "#FFFFFF",
        # 视频播放器
        "player_bg":     "#0B0B10",
        "play_btn_bg":   "#FFFFFF",
        "play_btn_fg":   "#007AFF",
        # 卡片
        "card":          "#FFFFFF",
        "card_border":   "#E3E3EC",
        # 滚动条
        "scroll":        "#C7C7D1",
        "scroll_hover":  "#AEAEB8",
    },

    # ── 深色液态玻璃（Tahoe 深色）───────────────────────────────────────────
    "glass_dark": {
        "name":          "液态玻璃 · 深色",
        "appearance":    "dark",
        "window_bg":     "#000000",
        "panel":         "#1C1C1E",
        "panel_alt":     "#242426",
        "panel_border":  "#38383A",
        "entry":         "#1C1C1E",
        "entry_border":  "#48484A",
        "text":          "#F5F5F7",
        "text_sec":      "#98989D",
        "text_faint":    "#6E6E73",
        "placeholder":   "#5A5A60",
        "accent":        "#0A84FF",
        "accent_hover":  "#0071E3",
        "accent_soft":   "#0A2540",
        "accent2":       "#BF5AF2",
        "ok":            "#30D158",
        "err":           "#FF453A",
        "warn":          "#FF9F0A",
        "header_grad":   [(24, 52, 130), (56, 40, 140), (130, 38, 130), (190, 40, 110)],
        "header_text":   "#FFFFFF",
        "player_bg":     "#000000",
        "play_btn_bg":   "#FFFFFF",
        "play_btn_fg":   "#0A84FF",
        "card":          "#1C1C1E",
        "card_border":   "#38383A",
        "scroll":        "#48484A",
        "scroll_hover":  "#5A5A60",
    },
}

DEFAULT_THEME = "glass_light"


def get(theme_name: str) -> dict:
    return THEMES.get(theme_name, THEMES[DEFAULT_THEME])


# ────────────────────────────────────────────────────────────────────────────
# 渐变背景生成
# ────────────────────────────────────────────────────────────────────────────
def make_gradient(width: int, height: int, stops: list) -> Image.Image:
    """
    生成水平渐变图（stops 为 [(r,g,b), ...]，从左到右均匀分布）。
    用于玻璃头部等需要渐变质感的位置。
    """
    if len(stops) < 2:
        stops = stops + [(0, 0, 0)]
    w1 = max(len(stops), 2)
    img = Image.new("RGB", (w1, 1))
    for i, c in enumerate(stops[:w1]):
        img.putpixel((i, 0), c)
    return img.resize((width, height), Image.BICUBIC)


def gradient_image(width: int, height: int, stops: list) -> ctk.CTkImage:
    pil = make_gradient(width, height, stops)
    return ctk.CTkImage(pil, pil, (width, height))


# ────────────────────────────────────────────────────────────────────────────
# 便捷工厂：玻璃面板 / 玻璃按钮 / 玻璃输入框
# ────────────────────────────────────────────────────────────────────────────
def glass_frame(parent, T: dict, corner_radius: int = 18, **kw):
    """玻璃面板"""
    kw.setdefault("fg_color", T["panel"])
    kw.setdefault("border_width", 1)
    kw.setdefault("border_color", T["panel_border"])
    kw.setdefault("corner_radius", corner_radius)
    return ctk.CTkFrame(parent, **kw)


def glass_entry(parent, T: dict, **kw):
    """玻璃输入框"""
    kw.setdefault("fg_color", T["entry"])
    kw.setdefault("border_color", T["entry_border"])
    kw.setdefault("corner_radius", 12)
    kw.setdefault("text_color", T["text"])
    kw.setdefault("placeholder_text_color", T["placeholder"])
    return ctk.CTkEntry(parent, **kw)


def accent_button(parent, T: dict, text: str, **kw):
    """强调色（Apple 蓝）按钮"""
    kw.setdefault("fg_color", T["accent"])
    kw.setdefault("hover_color", T["accent_hover"])
    kw.setdefault("text_color", "#FFFFFF")
    kw.setdefault("corner_radius", 14)
    kw.setdefault("font", ctk.CTkFont("Microsoft YaHei", 13, "bold"))
    return ctk.CTkButton(parent, text=text, **kw)


def ghost_button(parent, T: dict, text: str, **kw):
    """玻璃透明按钮（面板色，细描边）"""
    kw.setdefault("fg_color", T["panel"])
    kw.setdefault("hover_color", T["panel_alt"])
    kw.setdefault("text_color", T["text_sec"])
    kw.setdefault("border_width", 1)
    kw.setdefault("border_color", T["panel_border"])
    kw.setdefault("corner_radius", 12)
    kw.setdefault("font", ctk.CTkFont("Microsoft YaHei", 11))
    return ctk.CTkButton(parent, text=text, **kw)
