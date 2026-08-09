# -*- coding: utf-8 -*-
"""移动端主题：液态玻璃（浅色/深色），配色遵循 ui-ux-pro-max 设计文档"""

THEMES = {
    "glass_dark": {
        "name": "深色",
        "bg": "#0F172A",
        "grad": [(30, 58, 138), (76, 29, 149), (131, 24, 67)],   # 头部渐变
        "header_text": "#FFFFFF",
        "primary": "#EC4899",      # 视频粉（品牌）
        "accent": "#2563EB",       # 时序蓝（主操作）
        "accent_down": "#1D4ED8",
        "panel": "#1B2536",
        "panel_border": "#33415A",
        "text": "#F1F5F9",
        "text_sec": "#A7B1C4",
        "text_faint": "#6E7B91",
        "placeholder": "#5A6780",
        "ok": "#34D399",
        "err": "#F87171",
        "warn": "#FBBF24",
        "glass": (1, 1, 1, 0.08),     # 半透明面板填充（rgba 0-1）
        "glass_border": (1, 1, 1, 0.16),
    },
    "glass_light": {
        "name": "浅色",
        "bg": "#F2F2F7",
        "grad": [(59, 108, 245), (124, 92, 245), (210, 90, 170)],
        "header_text": "#0F172A",
        "primary": "#7C3AED",
        "accent": "#2563EB",
        "accent_down": "#1D4ED8",
        "panel": "#FFFFFF",
        "panel_border": "#E3E3EC",
        "text": "#1D1D1F",
        "text_sec": "#5B5B68",
        "text_faint": "#8E8E9B",
        "placeholder": "#B7B7C3",
        "ok": "#16A34A",
        "err": "#DC2626",
        "warn": "#D97706",
        "glass": (1, 1, 1, 0.75),
        "glass_border": (1, 1, 1, 0.9),
    },
}

DEFAULT = "glass_dark"


def get(name=None):
    return THEMES.get(name, THEMES[DEFAULT])


def hex2rgba(h, a=1.0):
    """#RRGGBB -> (r,g,b,a) 0-1"""
    h = (h or "#000000").lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4)) + (a,)
