# -*- coding: utf-8 -*-
"""去水印工具 · Android 手机版（Kivy）
液态玻璃 UI + 动效；解析/下载全部本地完成
"""
import os
import io
import re
import time
import queue
import threading
import tempfile

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from kivy.app import App
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.uix.button import ButtonBehavior
from kivy.graphics import Color, RoundedRectangle, Rectangle, Ellipse, Line
from PIL import Image as PILImage, ImageDraw
from kivy.core.image import Image as KImage

import theme as mtheme
import icons
from widgets import GlassButton, LoadingSpinner, ProgressCapsule, GlassCard, Pill
import storage
import history as history_db
from core import platform_detector, doubao_parser, xiaohongshu_parser, douyin_parser


# ── 全局 HTTP 会话（连接复用 + 自动重试） ────────────────────────────────────
_HTTP = requests.Session()
_HTTP.headers.update({"User-Agent": "Mozilla/5.0"})
_retry = Retry(total=3, backoff_factor=0.5,
               status_forcelist=[429, 500, 502, 503, 504],
               allowed_methods=frozenset(["GET", "POST"]))
_adapter = HTTPAdapter(max_retries=_retry)
_HTTP.mount("http://", _adapter)
_HTTP.mount("https://", _adapter)

_CT_EXT = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
           "image/webp": ".webp", "image/gif": ".gif",
           "video/mp4": ".mp4", "video/quicktime": ".mov"}
_MIME = {"image/jpeg": "image/jpeg", "image/jpg": "image/jpeg", "image/png": "image/png",
         "image/webp": "image/webp", "image/gif": "image/gif",
         "video/mp4": "video/mp4", "video/quicktime": "video/quicktime"}


def _setup_font():
    """注册中文字体为默认字体（Kivy 自带 Roboto 不含中文，必须指定 CJK 字体）。
    优先使用 APK 内置的思源黑体（OFL 许可），桌面调试与 Android 完全一致。"""
    from kivy.core.text import LabelBase
    bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "fonts", "SourceHanSansSC-Regular.otf")
    if os.path.exists(bundled):
        try:
            LabelBase.register("Roboto", fn_regular=bundled)
            return
        except Exception:
            pass
    # 兜底：桌面系统字体
    for f in ["C:/Windows/Fonts/Deng.ttf", "C:/Windows/Fonts/msyh.ttc",
              "C:/Windows/Fonts/simhei.ttf"]:
        if os.path.exists(f):
            try:
                LabelBase.register("Roboto", fn_regular=f)
                return
            except Exception:
                continue


def _gradient_texture(width, height, stops):
    """PIL 渐变 -> Kivy 纹理"""
    img = PILImage.new("RGB", (len(stops), 1))
    for i, c in enumerate(stops):
        img.putpixel((i, 0), c)
    img = img.resize((width, height), PILImage.BICUBIC)
    buf = io.BytesIO()
    img.save(buf, format="png")
    buf.seek(0)
    return KImage(buf, ext="png").texture


def _img_bytes_from_url(url, target_w, target_h):
    """线程内：下载图片 -> 缩放 -> PNG 字节（纹理创建必须回主线程）"""
    try:
        r = _HTTP.get(url, timeout=10)
        if r.status_code != 200:
            return None
        img = PILImage.open(io.BytesIO(r.content)).convert("RGB")
        img.thumbnail((max(int(target_w * 2), 64), max(int(target_h * 2), 64)), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="png")
        return buf.getvalue()
    except Exception:
        return None


def _download_item(item, dest_path):
    """下载单个媒体到 dest_path（含 403/404 回退 + Content-Type 扩展名修正），返回 (最终路径, mime)"""
    url = item["url"]
    headers = {"User-Agent": "Mozilla/5.0"}
    r = _HTTP.get(url, headers=headers, stream=True, timeout=30)
    if r.status_code in (403, 404) and item.get("fallback"):
        r.close()
        r = _HTTP.get(item["fallback"], headers=headers, stream=True, timeout=30)
    r.raise_for_status()
    ct = r.headers.get("Content-Type", "").lower().split(";")[0].strip()
    ext = _CT_EXT.get(ct, "")
    if ext and not dest_path.lower().endswith(ext):
        dest_path = os.path.splitext(dest_path)[0] + ext
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=512 * 1024):
            if chunk:
                f.write(chunk)
    r.close()
    return dest_path, _MIME.get(ct, "application/octet-stream")


# ────────────────────────────────────────────────────────────────────────────
#  媒体选择卡片（图文/动图/视频网格）
# ────────────────────────────────────────────────────────────────────────────
class MediaCell(ButtonBehavior, Widget):
    def __init__(self, item, T, on_toggle, index=0, **kw):
        super().__init__(**kw)
        self.item = item
        self.T = T
        self._on_toggle = on_toggle
        self.index = index
        self.selected = True
        self.size_hint = (None, None)
        self._thumb = None
        self._thumb_loaded = False
        self._type_pill = Pill(
            text={"live_photo": "动图", "video": "视频", "image": "图"}.get(item.get("type"), ""),
            color=T["accent2"] if item.get("type") == "live_photo" else "#64748B",
            T=T)
        self._type_pill.size_hint = (None, None)
        self._type_pill.size = (dp(44), dp(22))
        self.add_widget(self._type_pill)
        # 加载占位图标（缩略图未就绪时显示，避免黑块）
        self._ph = icons.icon("video" if item.get("type") == "video" else "image", 44,
                              self.T["text_faint"])
        self._ph.size_hint = (None, None)
        self._ph.size = (dp(44), dp(44))
        self.add_widget(self._ph)
        self.bind(pos=self._layout, size=self._layout)
        self._load_thumb()

    def _layout(self, *a):
        self._type_pill.pos = (self.x + dp(4), self.y + dp(4))
        self._ph.center = (self.center_x, self.center_y)
        self._draw_bg()
        self._draw_check()

    def _draw_bg(self):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.T["glass"])
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
            Color(*self.T["glass_border"])
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(14)), width=1)

    def _draw_check(self):
        self.canvas.after.clear()
        with self.canvas.after:
            cx, cy = self.x + self.width - dp(14), self.y + self.height - dp(14)
            r = dp(11)
            Color(*(mtheme.hex2rgba(self.T["accent"]) if self.selected else (0, 0, 0, 0.35)))
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
            if self.selected:
                Color(1, 1, 1, 1)
                Line(points=[cx - dp(4), cy, cx - dp(1), cy + dp(4), cx + dp(5), cy - dp(4)],
                     width=dp(2), joint="round")

    def set_selected(self, val):
        self.selected = val
        self._draw_check()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.selected = not self.selected
            self._draw_check()
            self._on_toggle()
            return True
        return super().on_touch_down(touch)

    def _load_thumb(self):
        url = self.item.get("thumb") or self.item.get("url", "")
        tw = int(self.width or 160)
        th = int(self.height or 160)

        def _bg():
            data = _img_bytes_from_url(url, tw, th)
            if data:
                Clock.schedule_once(lambda dt: self._apply_thumb_data(data))

        threading.Thread(target=_bg, daemon=True).start()

    def _apply_thumb_data(self, data):
        try:
            self._thumb = KImage(io.BytesIO(data), ext="png").texture
            self._thumb_loaded = True
            self._apply_thumb()
        except Exception:
            pass

    def _apply_thumb(self):
        if not self._thumb_loaded:
            return
        try:
            self.remove_widget(self._ph)
        except Exception:
            pass
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(texture=self._thumb, pos=self.pos, size=self.size)
        self._draw_bg()
        self._draw_check()
        self._type_pill.canvas.before.clear()


# ────────────────────────────────────────────────────────────────────────────
#  App
# ────────────────────────────────────────────────────────────────────────────
class WatermarkApp(App):
    def build(self):
        _setup_font()
        self.title = "去水印"
        self.T = mtheme.get()
        self._meta = None
        self._selected = set()
        self._parsing = False
        self._downloading = False
        self._history_open = False
        self._thumb_sem = threading.BoundedSemaphore(4)
        Window.clearcolor = mtheme.hex2rgba(self.T["bg"])
        self._build_root()
        return self.root

    def _build_root(self):
        root = BoxLayout(orientation="vertical", spacing=dp(2))
        root.add_widget(self._build_header())
        root.add_widget(self._build_input_panel())
        root.add_widget(self._build_content())
        root.add_widget(self._build_bottom())
        self.root = root


    # ── 构建：头部 ──────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = FloatLayout(size_hint_y=None, height=dp(64))
        self._hdr_tex = _gradient_texture(max(int(Window.width), 320), int(dp(64) * 2), self.T["grad"])
        self._hdr_rect = Rectangle(texture=self._hdr_tex)
        hdr.canvas.add(Color(1, 1, 1, 1))
        hdr.canvas.add(self._hdr_rect)

        def _update_hdr(*a):
            self._hdr_rect.pos = hdr.pos
            self._hdr_rect.size = hdr.size
        hdr.bind(pos=_update_hdr, size=_update_hdr)
        Clock.schedule_once(lambda dt: _update_hdr(), 0)

        title = Label(text="去水印", font_size=dp(20), bold=True,
                      color=mtheme.hex2rgba(self.T["header_text"]),
                      pos_hint={"x": 0.05, "center_y": 0.5}, size_hint=(None, None))
        sub = Label(text="豆包 / 小红书 / 抖音", font_size=dp(11),
                    color=mtheme.hex2rgba(self.T["header_text"], 0.75),
                    pos_hint={"x": 0.05, "y": 0.12}, size_hint=(None, None))
        hdr.add_widget(title)
        hdr.add_widget(sub)

        self._theme_btn = GlassButton(
            text="深色" if self.T["name"] == "浅色" else "浅色",
            height=32, font_size=13, T=self.T,
            on_click=self._toggle_theme)
        self._theme_btn.size = (dp(72), dp(32))
        self._theme_btn.pos_hint = {"right": 0.97, "center_y": 0.5}
        hdr.add_widget(self._theme_btn)
        return hdr

    # ── 构建：输入区 ────────────────────────────────────────────────────────
    def _build_input_panel(self):
        panel = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10),
                          size_hint_y=None, height=dp(150))
        self._url_input = TextInput(
            hint_text="粘贴 豆包/小红书/抖音 分享链接（支持整段文案）",
            multiline=True, size_hint_y=None, height=dp(58),
            padding=(dp(12), dp(12)),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_active="",
            foreground_color=mtheme.hex2rgba(self.T["text"]),
            hint_text_color=mtheme.hex2rgba(self.T["placeholder"]),
            cursor_color=mtheme.hex2rgba(self.T["accent"]),
            font_size=dp(15))
        self._url_input.bind(text=self._on_url_change)
        with self._url_input.canvas.before:
            Color(*self.T["glass"])
            self._input_rect = RoundedRectangle(pos=self._url_input.pos, size=self._url_input.size,
                                                radius=[dp(14)])
        self._url_input.bind(pos=lambda *a: setattr(self._input_rect, "pos", self._url_input.pos),
                             size=lambda *a: setattr(self._input_rect, "size", self._url_input.size))

        row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(52))
        self._badge = Pill(text="", color="#334155", T=self.T)
        self._badge.size = (dp(72), dp(30))
        self._badge.pos_hint = {"center_y": 0.5}
        row.add_widget(self._badge)

        self._parse_btn = GlassButton(text="解析", primary=True, height=52, font_size=17,
                                      T=self.T, on_click=self._start_parse)
        self._parse_btn.size_hint_x = 1.0
        row.add_widget(self._parse_btn)
        panel.add_widget(self._url_input)
        panel.add_widget(row)

        self._status = Label(text="支持 豆包 / 小红书 / 抖音，粘贴链接自动识别",
                             font_size=dp(12), color=mtheme.hex2rgba(self.T["text_faint"]),
                             size_hint_y=None, height=dp(20), halign="left")
        self._status.bind(size=lambda *a: setattr(self._status, "text_size", (self._status.width, None)))
        panel.add_widget(self._status)
        return panel

    # ── 构建：内容区 ────────────────────────────────────────────────────────
    def _build_content(self):
        scroll = ScrollView(do_scroll_x=False)
        self._content = BoxLayout(orientation="vertical", size_hint_y=None, padding=(dp(16), dp(8)))
        self._content.bind(minimum_height=self._content.setter("height"))
        scroll.add_widget(self._content)
        return scroll

    # ── 构建：底部 ──────────────────────────────────────────────────────────
    def _build_bottom(self):
        bar = BoxLayout(orientation="horizontal", padding=dp(16), spacing=dp(10),
                        size_hint_y=None, height=dp(64))
        self._progress = ProgressCapsule(T=self.T, height=54)
        self._progress.size_hint = (None, None)
        self._progress.width = dp(100)
        self._progress.opacity = 0
        bar.add_widget(self._progress)

        self._dl_btn = GlassButton(text="解析后即可下载", primary=True, height=54, font_size=17,
                                   T=self.T, on_click=self._start_download)
        self._dl_btn.size_hint_x = 1.0
        self._dl_btn.disabled = True
        self._dl_btn.opacity = 0.6
        bar.add_widget(self._dl_btn)

        self._history_btn = GlassButton(text="", height=54, T=self.T, on_click=self._toggle_history)
        self._history_btn.size = (dp(54), dp(54))
        self._history_btn.clear_widgets()
        hist_icon = icons.icon("history", 26, self.T["text_sec"])
        hist_icon.pos_hint = {"center_x": 0.5, "center_y": 0.5}
        self._history_btn.add_widget(hist_icon)
        bar.add_widget(self._history_btn)
        return bar


    # ── 内容渲染 ────────────────────────────────────────────────────────────
    def _clear_content(self):
        self._content.clear_widgets()

    def show_empty(self):
        self._clear_content()
        box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(300),
                        spacing=dp(12))
        icon = icons.icon("download", 64, self.T["text_faint"])
        icon.pos_hint = {"center_x": 0.5, "center_y": 0.5}
        box.add_widget(icon)
        l1 = Label(text="粘贴链接即可解析", font_size=dp(17), bold=True,
                   color=mtheme.hex2rgba(self.T["text_sec"]), size_hint_y=None, height=dp(28))
        l2 = Label(text="支持 图文 / 动图 / 视频", font_size=dp(13),
                   color=mtheme.hex2rgba(self.T["text_faint"]), size_hint_y=None, height=dp(22))
        box.add_widget(l1)
        box.add_widget(l2)
        self._content.add_widget(box)
        self._fade_in(box)

    def show_loading(self, platform):
        self._clear_content()
        box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(240), spacing=dp(14))
        self._spinner = LoadingSpinner(T=self.T, size=56)
        self._spinner.pos_hint = {"center_x": 0.5, "center_y": 0.5}
        box.add_widget(self._spinner)
        lbl = Label(text=f"正在解析 {platform} 链接…", font_size=dp(15),
                    color=mtheme.hex2rgba(self.T["text_sec"]), size_hint_y=None, height=dp(26))
        box.add_widget(lbl)
        self._content.add_widget(box)
        self._spinner.start()

    def show_error(self, msg):
        self._clear_content()
        if hasattr(self, "_spinner"):
            self._spinner.stop()
        box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(200), spacing=dp(10))
        l = Label(text=f"解析失败\n{msg}", font_size=dp(14),
                  color=mtheme.hex2rgba(self.T["err"]), size_hint_y=None, height=dp(80))
        box.add_widget(l)
        self._content.add_widget(box)
        self._fade_in(box)

    def _fade_in(self, widget, dy=8):
        widget.opacity = 0
        anim = Animation(opacity=1, duration=0.25, t="out_cubic")
        anim.start(widget)

    def show_video(self, meta):
        self._clear_content()
        box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10))
        box.bind(minimum_height=box.setter("height"))
        T = self.T

        pm = platform_detector.get_meta(meta["platform"])
        head = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(30))
        p = Pill(text=pm["name"], color=pm["badge_color"], T=T)
        p.size = (dp(80), dp(26))
        head.add_widget(p)
        if meta.get("no_watermark"):
            w = Pill(text="无水印", color=T["ok"], T=T)
            w.size = (dp(70), dp(26))
            head.add_widget(w)
        head.add_widget(Widget())
        box.add_widget(head)

        item = meta["media_items"][0]
        cover = meta.get("cover_url") or item.get("thumb", "")
        # 封面 + 系统播放器预览（不依赖 ffpyplayer，Android 构建更稳）
        prev = FloatLayout(size_hint=(None, None), size=(dp(200), dp(356)))
        prev.pos_hint = {"center_x": 0.5}
        if cover:
            def _load_cover():
                data = _img_bytes_from_url(cover, 400, 712)
                if data:
                    Clock.schedule_once(lambda dt: _apply_cover(data))
            def _apply_cover(data):
                try:
                    tex = KImage(io.BytesIO(data), ext="png").texture
                    prev.canvas.clear()
                    with prev.canvas:
                        Color(1, 1, 1, 1)
                        Rectangle(texture=tex, pos=prev.pos, size=prev.size)
                except Exception:
                    pass
            threading.Thread(target=_load_cover, daemon=True).start()
        pb = GlassButton(text="播放预览", primary=True, height=44, font_size=14, T=T)
        pb.size = (dp(150), dp(44))
        pb.pos_hint = {"center_x": 0.5, "center_y": 0.5}
        pb.bind(on_release=lambda *a: self._preview_video(item["url"]))
        prev.add_widget(pb)
        box.add_widget(prev)

        info = f"作者 {meta.get('author','')}"
        if meta.get("width") and meta.get("height"):
            info += f"  {meta['width']}x{meta['height']}"
        l = Label(text=info, font_size=dp(13), color=mtheme.hex2rgba(T["text_sec"]),
                  size_hint_y=None, height=dp(22), halign="center")
        box.add_widget(l)
        if meta.get("text"):
            t = Label(text=meta["text"][:120], font_size=dp(13),
                      color=mtheme.hex2rgba(T["text_sec"]),
                      size_hint_y=None, height=dp(44), halign="left")
            t.bind(size=lambda *a: setattr(t, "text_size", (t.width, None)))
            box.add_widget(t)
        self._content.add_widget(box)
        self._fade_in(box)

    def show_grid(self, meta):
        self._clear_content()
        T = self.T
        pm = platform_detector.get_meta(meta["platform"])
        items = meta["media_items"]
        self._selected = set(range(len(items)))

        head = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(30))
        p = Pill(text=pm["name"], color=pm["badge_color"], T=T)
        p.size = (dp(80), dp(26))
        head.add_widget(p)
        from collections import Counter
        cnt = Counter(it["type"] for it in items)
        parts = []
        if cnt.get("image"): parts.append(f"图 {cnt['image']}")
        if cnt.get("live_photo"): parts.append(f"动图 {cnt['live_photo']}")
        if cnt.get("video"): parts.append(f"视频 {cnt['video']}")
        summary = Label(text="  ".join(parts) + f"  共 {len(items)} 项",
                        font_size=dp(13), color=mtheme.hex2rgba(T["text_sec"]))
        head.add_widget(summary)
        head.add_widget(Widget())
        self._content.add_widget(head)

        grid = GridLayout(cols=3, spacing=dp(10), size_hint_y=None, padding=(0, dp(6)))
        grid.bind(minimum_height=grid.setter("height"))
        cell_w = (min(Window.width, 720) - dp(32) - dp(20)) / 3
        for i, it in enumerate(items):
            cell = MediaCell(it, T, self._refresh_dl_text, index=i)
            cell.size = (cell_w, cell_w)
            grid.add_widget(cell)
        self._content.add_widget(grid)
        self._refresh_dl_text()
        self._fade_in(grid)
        # 历史入库
        history_db.add(meta["platform"], meta.get("title", ""), meta.get("_url", ""),
                       meta.get("type", ""), len(items))

    def _refresh_dl_text(self, *a):
        n = len(self._selected)
        self._dl_btn.text = f"下载所选 ({n})" if n else "请选择要下载的内容"
        self._dl_btn.disabled = n == 0
        self._dl_btn.opacity = 0.6 if n == 0 else 1.0

    # ── 解析流程 ────────────────────────────────────────────────────────────
    def _on_url_change(self, *a):
        url = self._url_input.text or ""
        plat = platform_detector.detect(url)
        pm = platform_detector.get_meta(plat)
        if plat != "unknown":
            self._badge.text = pm["name"]
            self._badge.color = list(mtheme.hex2rgba(pm["badge_color"]))
        else:
            self._badge.text = ""

    def _start_parse(self, *a):
        if self._parsing or self._downloading:
            return
        text = (self._url_input.text or "").strip()
        if not text:
            self._set_status("请先粘贴分享链接", self.T["warn"])
            return
        plat = platform_detector.detect(text)
        if plat == "unknown":
            self._set_status("暂不支持该平台，目前支持：豆包/小红书/抖音", self.T["warn"])
            return
        self._parsing = True
        self._parse_btn.disabled = True
        self._parse_btn.opacity = 0.6
        self._set_status("解析中…", self.T["accent"])
        self.show_loading(platform_detector.get_meta(plat)["name"])
        threading.Thread(target=self._bg_parse, args=(text, plat), daemon=True).start()

    def _bg_parse(self, text, plat):
        try:
            url = platform_detector.extract_url(text)
            if plat == "doubao":
                meta = doubao_parser.parse(url)
                meta["platform"] = "doubao"
                meta["type"] = "video"
                meta["media_items"] = [{"type": "video", "url": meta["video_url"],
                                        "thumb": meta.get("poster_url", "")}]
                meta.setdefault("author", meta.get("nickname", "豆包用户"))
                meta.setdefault("text", meta.get("prompt", ""))
                meta.setdefault("cover_url", meta.get("poster_url", ""))
            elif plat == "xiaohongshu":
                meta = xiaohongshu_parser.parse(url)
            elif plat == "douyin":
                meta = douyin_parser.parse(url)
            else:
                raise ValueError("不支持的平台")
            meta["_url"] = url
            Clock.schedule_once(lambda dt: self._on_parse_ok(meta))
        except Exception as e:
            Clock.schedule_once(lambda dt: self._on_parse_fail(str(e)))

    def _on_parse_ok(self, meta):
        self._parsing = False
        self._parse_btn.disabled = False
        self._parse_btn.opacity = 1.0
        self._meta = meta
        if meta["type"] == "video" or (meta["type"] == "live_photo" and len(meta["media_items"]) == 1):
            self.show_video(meta)
            self._dl_btn.text = "下载视频（无水印）"
            self._dl_btn.disabled = False
            self._dl_btn.opacity = 1.0
        else:
            self.show_grid(meta)
        pm = platform_detector.get_meta(meta["platform"])
        self._set_status(f"解析成功 | {pm['name']} | 无水印", self.T["ok"])

    def _on_parse_fail(self, msg):
        self._parsing = False
        self._parse_btn.disabled = False
        self._parse_btn.opacity = 1.0
        self.show_error(msg)
        self._set_status("解析失败", self.T["err"])

    def _set_status(self, text, color):
        self._status.text = text
        self._status.color = mtheme.hex2rgba(color)


    # ── 下载流程 ────────────────────────────────────────────────────────────
    def _start_download(self, *a):
        if not self._meta or self._downloading or self._parsing:
            return
        meta = self._meta
        if meta["type"] in ("video", "live_photo") and len(meta["media_items"]) == 1:
            items = [meta["media_items"][0]]
            base = meta.get("note_id") or meta.get("video_id") or meta.get("vid") or "media"
            names = [f"{meta['platform']}_{base}.mp4"]
        else:
            items = [meta["media_items"][i] for i in sorted(self._selected)]
            base = meta.get("note_id") or meta.get("video_id") or "xhs"
            names = []
            for i, it in enumerate(items):
                names.append(f"{meta['platform']}_{base}_{i+1}{'.mp4' if it['type']=='live_photo' else ''}")
        if not items:
            self._set_status("请先选择内容", self.T["warn"])
            return

        self._downloading = True
        self._dl_btn.opacity = 0
        self._progress.opacity = 1
        self._progress.start_download()
        threading.Thread(target=self._bg_download, args=(items, names), daemon=True).start()

    def _bg_download(self, items, names):
        total = len(items)
        for i, (item, name) in enumerate(zip(items, names)):
            try:
                tmp = os.path.join(tempfile.gettempdir(), "wt_" + str(int(time.time()*1000)) + "_" + name)
                final, mime = _download_item(item, tmp)
                saved = storage.save_media(final, name, mime)
                try:
                    os.remove(final)
                except Exception:
                    pass
                Clock.schedule_once(lambda dt, p=(i + 1) / total: self._progress.update(p))
                Clock.schedule_once(lambda dt, n=name: self._set_status(f"已保存 {n}", self.T["ok"]))
            except Exception as e:
                Clock.schedule_once(lambda dt, m=str(e): self._on_dl_fail(m))
                return
        Clock.schedule_once(lambda dt: self._on_dl_done(total))

    def _on_dl_done(self, total):
        self._downloading = False
        self._progress.finish()
        self._set_status(f"下载完成，共 {total} 个文件已保存到相册", self.T["ok"])
        Clock.schedule_once(self._reset_bottom, 3.0)

    def _on_dl_fail(self, msg):
        self._downloading = False
        self._progress.fail()
        self._set_status(f"下载失败：{msg[:40]}", self.T["err"])
        Clock.schedule_once(self._reset_bottom, 2.5)

    def _preview_video(self, url):
        """用 Android 系统播放器预览视频（无需 ffpyplayer）"""
        if storage.IS_ANDROID:
            try:
                from jnius import autoclass
                Intent = autoclass("android.content.Intent")
                Uri = autoclass("android.net.Uri")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                intent = Intent(Intent.ACTION_VIEW)
                intent.setDataAndType(Uri.parse(url), "video/mp4")
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                PythonActivity.mActivity.startActivity(intent)
                return
            except Exception:
                pass
        import webbrowser
        webbrowser.open(url)

    def _reset_bottom(self, dt=None):
        self._progress.opacity = 0
        self._dl_btn.opacity = 1.0
        self._refresh_dl_text() if self._meta and self._meta["type"] not in ("video",) else None

    # ── 历史 ────────────────────────────────────────────────────────────────
    def _toggle_history(self, *a):
        if self._history_open:
            self._history_close()
        else:
            self._history_open_drawer()

    def _history_open_drawer(self):
        recs = history_db.recent(10)
        if not recs:
            self._set_status("暂无历史记录", self.T["text_faint"])
            return
        self._clear_content()
        box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        box.bind(minimum_height=box.setter("height"))
        t = Label(text="解析历史", font_size=dp(16), bold=True,
                  color=mtheme.hex2rgba(self.T["text"]), size_hint_y=None, height=dp(30))
        box.add_widget(t)
        for r in recs:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8))
            pm = platform_detector.get_meta(r["platform"])
            p = Pill(text=pm["name"], color=pm["badge_color"], T=self.T)
            p.size = (dp(64), dp(26))
            p.pos_hint = {"center_y": 0.5}
            row.add_widget(p)
            title = Label(text=r["title"][:24] or "（无标题）", font_size=dp(13),
                          color=mtheme.hex2rgba(self.T["text_sec"]), halign="left")
            title.bind(size=lambda *a: setattr(title, "text_size", (title.width, None)))
            row.add_widget(title)
            row.add_widget(Widget())
            btn = GlassButton(text="", height=36, T=self.T)
            btn.size = (dp(44), dp(36))
            btn.clear_widgets()
            go = icons.icon("arrow_right", 20, self.T["text_sec"])
            go.pos_hint = {"center_x": 0.5, "center_y": 0.5}
            btn.add_widget(go)
            btn.bind(on_release=lambda *a, u=r["url"]: self._restore_history(u))
            row.add_widget(btn)
            box.add_widget(row)
        self._content.add_widget(box)
        self._history_open = True

    def _history_close(self):
        self._history_open = False
        if self._meta:
            self._render_meta(self._meta)
        else:
            self.show_empty()

    def _restore_history(self, url):
        self._url_input.text = url
        self._history_open = False
        self._start_parse()

    def _render_meta(self, meta):
        if meta["type"] == "video" or (meta["type"] == "live_photo" and len(meta["media_items"]) == 1):
            self.show_video(meta)
        else:
            self.show_grid(meta)

    # ── 主题切换 ────────────────────────────────────────────────────────────
    def _toggle_theme(self, *a):
        self.T = mtheme.get("glass_light" if self.T["name"] == "深色" else "glass_dark")
        Window.clearcolor = mtheme.hex2rgba(self.T["bg"])
        url_text = self._url_input.text
        meta = self._meta
        self._build_root()
        self._url_input.text = url_text
        self._on_url_change()
        if meta:
            self._render_meta(meta)
        else:
            self.show_empty()
        self._theme_btn.text = "深色" if self.T["name"] == "浅色" else "浅色"


if __name__ == "__main__":
    WatermarkApp().run()
