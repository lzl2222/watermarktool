# -*- coding: utf-8 -*-
"""PIL 绘制矢量风格图标 -> Kivy 纹理（禁用 emoji，遵循设计文档图标规范）"""
from io import BytesIO
from PIL import Image, ImageDraw
from kivy.core.image import Image as KImage
from kivy.uix.image import Image as KivyImage

from theme import hex2rgba

_SS = 2  # 超采样倍数，保证清晰

def _base(size):
    s = size * _SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), s

def _rgb255(h):
    """#RRGGBB -> (r,g,b,255) 整数，供 PIL 绘制"""
    h = (h or "#000000").lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) + (255,)


def _tex(img, size):
    buf = BytesIO()
    img.save(buf, format="png")
    buf.seek(0)
    tex = KImage(buf, ext="png").texture
    return tex


def draw_icon(name, size, color):
    """返回 PIL 图像（绘制单个图标）"""
    img, d, s = _base(size)
    c = _rgb255(color)
    w = s * 0.12          # 线宽
    if name == "play":
        d.polygon([(s*0.36, s*0.18), (s*0.82, s*0.50), (s*0.36, s*0.82)], fill=c)
    elif name == "pause":
        d.rounded_rectangle([s*0.26, s*0.18, s*0.44, s*0.82], radius=s*0.04, fill=c)
        d.rounded_rectangle([s*0.56, s*0.18, s*0.74, s*0.82], radius=s*0.04, fill=c)
    elif name == "download":
        d.rounded_rectangle([s*0.30, s*0.14, s*0.70, s*0.20], radius=s*0.03, fill=c)          # 上横
        d.rounded_rectangle([s*0.46, s*0.20, s*0.54, s*0.62], radius=s*0.03, fill=c)          # 杆
        d.polygon([(s*0.24, s*0.50), (s*0.76, s*0.50), (s*0.50, s*0.80)], fill=c)            # 箭头
        d.rounded_rectangle([s*0.22, s*0.80, s*0.78, s*0.88], radius=s*0.03, fill=c)          # 托盘
    elif name == "check":
        d.line([(s*0.22, s*0.52), (s*0.42, s*0.72), (s*0.80, s*0.28)], fill=c, width=int(w), joint="round")
    elif name == "image":
        d.rounded_rectangle([s*0.14, s*0.22, s*0.86, s*0.78], radius=s*0.10, outline=c, width=int(w))
        d.ellipse([s*0.26, s*0.32, s*0.42, s*0.48], outline=c, width=int(w))
        d.polygon([(s*0.22, s*0.74), (s*0.46, s*0.50), (s*0.62, s*0.64), (s*0.74, s*0.50), (s*0.82, s*0.60), (s*0.82, s*0.74)], fill=c)
    elif name == "video":
        d.rounded_rectangle([s*0.12, s*0.22, s*0.88, s*0.78], radius=s*0.08, outline=c, width=int(w))
        d.polygon([(s*0.42, s*0.36), (s*0.66, s*0.50), (s*0.42, s*0.64)], fill=c)
    elif name == "live":
        d.ellipse([s*0.12, s*0.12, s*0.88, s*0.88], outline=c, width=int(w))
        d.polygon([(s*0.40, s*0.34), (s*0.66, s*0.50), (s*0.40, s*0.66)], fill=c)
    elif name == "history":
        d.ellipse([s*0.12, s*0.12, s*0.88, s*0.88], outline=c, width=int(w))
        d.line([(s*0.50, s*0.28), (s*0.50, s*0.52), (s*0.68, s*0.62)], fill=c, width=int(w), joint="round")
    elif name == "moon":
        d.ellipse([s*0.18, s*0.18, s*0.82, s*0.82], outline=c, width=int(w))
        d.ellipse([s*0.44, s*0.30, s*0.86, s*0.72], fill=(255, 255, 255, 0), outline=c, width=int(w))
    elif name == "sun":
        for ang in range(0, 360, 45):
            import math
            a = math.radians(ang)
            x0 = s*0.5 + math.cos(a)*s*0.30
            y0 = s*0.5 + math.sin(a)*s*0.30
            x1 = s*0.5 + math.cos(a)*s*0.42
            y1 = s*0.5 + math.sin(a)*s*0.42
            d.line([(x0, y0), (x1, y1)], fill=c, width=int(w))
        d.ellipse([s*0.30, s*0.30, s*0.70, s*0.70], outline=c, width=int(w))
    elif name == "link":
        d.ellipse([s*0.14, s*0.40, s*0.40, s*0.66], outline=c, width=int(w))
        d.ellipse([s*0.60, s*0.34, s*0.86, s*0.60], outline=c, width=int(w))
        d.line([(s*0.36, s*0.56), (s*0.62, s*0.44)], fill=c, width=int(w))
    elif name == "close":
        d.line([(s*0.26, s*0.26), (s*0.74, s*0.74)], fill=c, width=int(w))
        d.line([(s*0.74, s*0.26), (s*0.26, s*0.74)], fill=c, width=int(w))
    elif name == "arrow_right":
        d.polygon([(s*0.32, s*0.20), (s*0.74, s*0.50), (s*0.32, s*0.80)], fill=c)
    elif name == "chevron_up":
        d.line([(s*0.30, s*0.58), (s*0.50, s*0.38), (s*0.70, s*0.58)], fill=c, width=int(w), joint="round")
    elif name == "app":
        d.rounded_rectangle([s*0.10, s*0.10, s*0.90, s*0.90], radius=s*0.20, fill=c)
        d.ellipse([s*0.38, s*0.36, s*0.62, s*0.64], fill=(255, 255, 255, 255))
        d.polygon([(s*0.44, s*0.42), (s*0.56, s*0.50), (s*0.44, s*0.58)], fill=c)
    else:
        raise ValueError(f"未知图标: {name}")
    return img


def icon(name, size, color):
    """返回 Kivy Image 控件（带纹理）"""
    img = draw_icon(name, size, color)
    tex = _tex(img, size)
    iv = KivyImage(texture=tex, size=(size, size), size_hint=(None, None),
                   allow_stretch=True, keep_ratio=True)
    return iv


def icon_texture(name, size, color):
    img = draw_icon(name, size, color)
    return _tex(img, size)
