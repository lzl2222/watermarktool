# -*- coding: utf-8 -*-
"""
theme.py — 液态玻璃（Liquid Glass / Glassmorphism）主题系统
设计依据：ui-ux-pro-max skill 设计系统（玻璃质感 + OLED 深色 / 清新浅色）

设计要点：
- 玻璃面板：半透明白 + 细描边（1px rgba white 0.08~0.2）+ 大圆角 + 悬浮阴影感
- 文字对比度 ≥ 4.5:1（浅色主题头部用深色文字，深色主题用白色文字）
- 强调色：浅色=蓝(#2563EB)/紫(#7C3AED)，深色=粉(#EC4899)/蓝(#2563EB)
- 圆角：面板 18~24px，按钮 14~16px，输入框 12px
"""

import customtkinter as ctk
from PIL import Image, ImageDraw


# ────────────────────────────────────────────────────────────────────────────
# 主题定义（每套主题自带全部语义色，切主题即全局生效）
# ────────────────────────────────────────────────────────────────────────────
THEMES = {
    # ── 浅色液态玻璃（Glassmorphism Light）──────────────────────────────────
    "glass_light": {
        "name":        "液态玻璃 · 浅色",
        "appearance":  "light",

        # 窗口 / 背景
        "window_bg":   "#F2F2F7",

        # 玻璃面板
        "panel":         "#FFFFFF",
        "panel_alt":     "#F4F4F8",
        "panel_border":  "#E3E3EC",
        "panel_shadow":  "#D8D8E2",   # 模拟悬浮阴影（进度条底等）

        # 输入框
        "entry":         "#FFFFFF",
        "entry_border":  "#D9D9E4",

        # 文字（浅色主题用深色文字保证对比度）
        "text":          "#1D1D1F",
        "text_sec":      "#5B5B68",
        "text_faint":    "#8E8E9B",
        "placeholder":   "#B7B7C3",

        # 强调色
        "accent":        "#2563EB",   # 主操作（解析/下载）
        "accent_hover":  "#1D4ED8",
        "accent_soft":   "#EAF1FF",
        "accent2":       "#7C3AED",   # 次级高亮（紫）
        "accent2_hover": "#6D28D9",

        # 状态色
        "ok":            "#16A34A",
        "err":           "#DC2626",
        "warn":          "#D97706",

        # 头部渐变（中饱和蓝→紫→粉，配深色文字保证 4.5:1）
        "header_grad":   [(59, 108, 245), (124, 92, 245), (210, 90, 170)],
        "header_text":   "#0F172A",
        "header_sub":    "#334155",

        # 视频播放器
        "player_bg":     "#0B0B10",
        "play_btn_bg":   "#FFFFFF",
        "play_btn_fg":   "#2563EB",

        # 卡片
        "card":          "#FFFFFF",
        "card_border":   "#E3E3EC",

        # 滚动条
        "scroll":        "#C9C9D4",
        "scroll_hover":  "#B0B0BD",
    },

    # ── 深色液态玻璃（Glassmorphism Dark / OLED）────────────────────────────
    "glass_dark": {
        "name":        "液态玻璃 · 深色",
        "appearance":  "dark",

        "window_bg":   "#0F172A",    # 深空蓝黑（OLED 友好）

        "panel":         "#1B2536",
        "panel_alt":     "#232F44",
        "panel_border":  "#33415A",
        "panel_shadow":  "#0A0F1E",

        "entry":         "#1B2536",
        "entry_border":  "#3D4B68",

        "text":          "#F1F5F9",
        "text_sec":      "#A7B1C4",
        "text_faint":    "#6E7B91",
        "placeholder":   "#5A6780",

        "accent":        "#EC4899",   # 主操作（视频粉）
        "accent_hover":  "#DB2777",
        "accent_soft":   "#3B1A33",
        "accent2":       "#2563EB",   # 次级（时序蓝）
        "accent2_hover": "#1D4ED8",

        "ok":            "#34D399",
        "err":           "#F87171",
        "warn":          "#FBBF24",

        "header_grad":   [(30, 58, 138), (76, 29, 149), (131, 24, 67)],
        "header_text":   "#FFFFFF",
        "header_sub":    "#D3D9E6",

        "player_bg":     "#000000",
        "play_btn_bg":   "#FFFFFF",
        "play_btn_fg":   "#EC4899",

        "card":          "#1B2536",
        "card_border":   "#33415A",

        "scroll":        "#3D4B68",
        "scroll_hover":  "#526183",
    },
}

DEFAULT_THEME = "glass_light"


def get(theme_name: str) -> dict:
    return THEMES.get(theme_name, THEMES[DEFAULT_THEME])


# ────────────────────────────────────────────────────────────────────────────
# 渐变背景
# ────────────────────────────────────────────────────────────────────────────
def make_gradient(width: int, height: int, stops: list) -> Image.Image:
    """水平渐变图（stops 为 [(r,g,b),...]，从左到右）"""
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
# 便捷工厂
# ────────────────────────────────────────────────────────────────────────────
def glass_frame(parent, T: dict, corner_radius: int = 18, **kw):
    """玻璃面板：面板色 + 细描边 + 大圆角"""
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
    """主强调色按钮（随主题：浅色=蓝 / 深色=粉）"""
    kw.setdefault("fg_color", T["accent"])
    kw.setdefault("hover_color", T["accent_hover"])
    kw.setdefault("text_color", "#FFFFFF")
    kw.setdefault("corner_radius", 14)
    kw.setdefault("font", ctk.CTkFont("Microsoft YaHei", 13, "bold"))
    return ctk.CTkButton(parent, text=text, **kw)


def ghost_button(parent, T: dict, text: str, **kw):
    """玻璃幽灵按钮：面板色 + 细描边"""
    kw.setdefault("fg_color", T["panel"])
    kw.setdefault("hover_color", T["panel_alt"])
    kw.setdefault("text_color", T["text_sec"])
    kw.setdefault("border_width", 1)
    kw.setdefault("border_color", T["panel_border"])
    kw.setdefault("corner_radius", 12)
    kw.setdefault("font", ctk.CTkFont("Microsoft YaHei", 11))
    return ctk.CTkButton(parent, text=text, **kw)


# ────────────────────────────────────────────────────────────────────────────
# 图标生成（PIL 绘制，避免 emoji 在 Windows 下渲染成黑方块）
# ────────────────────────────────────────────────────────────────────────────
def _hex2rgb(h: str):
    h = (h or "#000000").lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def icon_play(size: int, color: str) -> ctk.CTkImage:
    """右向播放三角"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = _hex2rgb(color)
    d.polygon([(size*0.32, size*0.16), (size*0.80, size*0.50), (size*0.32, size*0.84)],
              fill=c + (255,))
    return ctk.CTkImage(img, img, (size, size))


def icon_pause(size: int, color: str) -> ctk.CTkImage:
    """双竖条暂停"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = _hex2rgb(color)
    w = size * 0.20
    r = max(1, size // 20)
    d.rounded_rectangle([size*0.24, size*0.16, size*0.24+w, size*0.84], radius=r, fill=c + (255,))
    d.rounded_rectangle([size*0.56, size*0.16, size*0.56+w, size*0.84], radius=r, fill=c + (255,))
    return ctk.CTkImage(img, img, (size, size))

