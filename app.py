"""
app.py  —  多平台去水印下载器（豆包 / 小红书 / 抖音）
         —— 苹果液态玻璃（Liquid Glass）主题 UI

内容类型自适应 UI：
  video      → 内嵌视频播放器（9:16）
  image      → 2列图片网格 + 多选下载
  live_photo → 动态图预览播放器 + 下载
"""

import os, time, threading, io, json
import requests, customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import platform_detector
import doubao_parser
import xiaohongshu_parser
import douyin_parser
import theme as ui_theme

# ─── 主题 ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ─── 配置持久化 ───────────────────────────────────────────────────────────────
_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def _load_cfg():
    try:
        return json.load(open(_CFG, encoding="utf-8"))
    except Exception:
        return {}

def _save_cfg(d):
    try:
        json.dump(d, open(_CFG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass


# ─── 全局 HTTP 会话（连接复用 + 自动重试，提升解析/下载流畅度） ──────────────
def _make_session(retries=3):
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    retry = Retry(total=retries, backoff_factor=0.5,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=frozenset(["GET", "POST"]))
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


_HTTP = _make_session()

# 缩略图并发上限（避免大量图片笔记时线程爆炸）
_THUMB_SEM = threading.BoundedSemaphore(4)


# ═════════════════════════════════════════════════════════════════════════════
#  内嵌视频播放器（用于视频 / live_photo 预览）
#  修复：播放时中央按钮移入右下角小尺寸暂停键，避免黑块遮挡画面
# ═════════════════════════════════════════════════════════════════════════════
class InlineVideoPlayer:
    W, H = 234, 416   # 9:16

    def __init__(self, parent, width=None, height=None, T=None):
        self.T = T or ui_theme.get(ui_theme.DEFAULT_THEME)
        self.W = width  or self.W
        self.H = height or self.H
        self._url     = None
        self._playing = False
        self._paused  = False
        self._thread  = None
        self._lock    = threading.Lock()
        self._cur_img = None
        self._poster  = None

        self.frame = ctk.CTkFrame(parent, width=self.W, height=self.H,
                                   fg_color=self.T["player_bg"], corner_radius=18,
                                   border_width=1, border_color=self.T["panel_border"])
        self.frame.pack_propagate(False)

        self.lbl = ctk.CTkLabel(self.frame, text="", width=self.W, height=self.H)
        self.lbl.pack(fill="both", expand=True)

        # 中央播放键（未播放时显示；播放后移到右下角变成暂停键）
        self.btn = ctk.CTkButton(self.frame, text="", width=58, height=58,
                                  corner_radius=29, fg_color=self.T["play_btn_bg"],
                                  hover_color="#E4E4F0",
                                  image=ui_theme.icon_play(26, self.T["play_btn_fg"]),
                                  command=self._toggle)
        self.btn.place(relx=0.5, rely=0.5, anchor="center")
        self._show_placeholder()

    # ── 公开接口 ──────────────────────────────────────────────────────────────
    def load_poster(self, poster_url: str):
        def _bg():
            try:
                r = _HTTP.get(poster_url, timeout=10)
                if r.status_code == 200:
                    img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                    img = img.resize((self.W, self.H), Image.LANCZOS)
                    self._poster = img
                    self.lbl.after(0, self._render_poster)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def set_url(self, url: str):
        self._url = url
        self._to_center()

    def stop(self):
        with self._lock:
            self._playing = False
            self._paused  = False
        try:
            self._to_center()
        except Exception:
            pass

    # ── 内部 ──────────────────────────────────────────────────────────────────
    def _show_placeholder(self):
        img = Image.new("RGB", (self.W, self.H), (16, 16, 24))
        d = ImageDraw.Draw(img)
        cx, cy, r = self.W//2, self.H//2, 40
        d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(255, 255, 255, 26))
        d.polygon([(cx-12, cy-15), (cx-12, cy+15), (cx+20, cy)], fill=(200, 205, 230))
        self._set_pil(img)

    def _render_poster(self):
        if not self._poster:
            return
        self._set_pil(self._poster.convert("RGB"))

    def _set_pil(self, pil_img):
        cimg = ctk.CTkImage(pil_img, pil_img, (self.W, self.H))
        self._cur_img = cimg
        self.lbl.configure(image=cimg)

    # 按钮位置：中央播放键 ↔ 右下角小暂停键
    def _to_center(self):
        self.btn.configure(text="", width=58, height=58, corner_radius=29,
                           fg_color=self.T["play_btn_bg"],
                           image=ui_theme.icon_play(26, self.T["play_btn_fg"]))
        self.btn.place(relx=0.5, rely=0.5, anchor="center")

    def _to_corner(self):
        self.btn.configure(text="", width=36, height=36, corner_radius=18,
                           fg_color="#000000", hover_color="#333333",
                           image=ui_theme.icon_pause(22, "#FFFFFF"))
        self.btn.place(relx=1.0, rely=1.0, x=-14, y=-14, anchor="se")

    def _toggle(self):
        if not self._url:
            return
        if not self._playing:
            self._playing, self._paused = True, False
            self._to_corner()
            self._thread = threading.Thread(target=self._stream, daemon=True)
            self._thread.start()
        elif self._paused:
            self._paused = False
            self._to_corner()
        else:
            self._paused = True
            self._to_center()

    def _stream(self):
        try:
            import cv2 as _cv
        except ImportError:
            return
        cap = _cv.VideoCapture(self._url)
        if not cap.isOpened():
            self.lbl.after(0, self._show_placeholder)
            return
        fps = cap.get(_cv.CAP_PROP_FPS) or 24
        gap = 1.0 / fps
        while True:
            with self._lock:
                if not self._playing:
                    break
            if self._paused:
                time.sleep(0.08)
                continue
            t0 = time.time()
            ret, frame = cap.read()
            if not ret:
                cap.set(_cv.CAP_PROP_POS_FRAMES, 0)
                continue
            pil = Image.fromarray(_cv.cvtColor(frame, _cv.COLOR_BGR2RGB)).resize(
                (self.W, self.H), Image.BILINEAR)
            self.lbl.after(0, lambda p=pil: self._set_pil(p))
            elapsed = time.time() - t0
            sl = gap - elapsed
            if sl > 0:
                time.sleep(sl)
        cap.release()
        self.lbl.after(0, self._render_poster)
        self.btn.after(0, self._to_center)


# ═════════════════════════════════════════════════════════════════════════════
#  图片卡片（小红书图文 / live_photo 缩略图）—— 玻璃卡片
# ═════════════════════════════════════════════════════════════════════════════
class MediaCard:
    CARD_W, CARD_H = 168, 168

    def __init__(self, parent, item: dict, index: int, on_click, T=None):
        self.T        = T or ui_theme.get(ui_theme.DEFAULT_THEME)
        self._item     = item
        self._selected = ctk.BooleanVar(value=True)
        self._on_click = on_click

        self.outer = ctk.CTkFrame(parent, fg_color=self.T["card"], corner_radius=14,
                                   border_width=1, border_color=self.T["card_border"],
                                   width=self.CARD_W, height=self.CARD_H)
        self.outer.pack_propagate(False)

        # 缩略图标签
        self.img_lbl = ctk.CTkLabel(self.outer, text="", width=self.CARD_W, height=self.CARD_H-30,
                                    fg_color=self.T["panel_alt"])
        self.img_lbl.pack()
        self.img_lbl.bind("<Button-1>", lambda e: on_click(item))

        # 底部行：类型徽章 + 序号 + 勾选框
        bar = ctk.CTkFrame(self.outer, fg_color=self.T["panel_alt"], height=30, corner_radius=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        type_map = {"live_photo": "动图", "video": "视频", "image": "图"}
        tname = type_map.get(item["type"], "")
        ctk.CTkLabel(bar, text=f"{tname} {index+1}", font=ctk.CTkFont(size=11),
                     text_color=self.T["text_sec"]).pack(side="left", padx=8)

        ctk.CTkCheckBox(bar, text="", variable=self._selected,
                        width=20, height=20, checkbox_width=16, checkbox_height=16,
                        fg_color=self.T["accent"], hover_color=self.T["accent_hover"],
                        border_color=self.T["entry_border"], checkmark_color="#FFFFFF"
                        ).pack(side="right", padx=8)

        # 异步加载缩略图
        self._load_thumb(item.get("thumb") or item.get("url", ""))

    def _load_thumb(self, url):
        def _bg():
            with _THUMB_SEM:
                try:
                    r = _HTTP.get(url, timeout=10)
                    if r.status_code == 200:
                        img = Image.open(io.BytesIO(r.content)).convert("RGB")
                        img = img.resize((self.CARD_W, self.CARD_H-30), Image.LANCZOS)
                        # Live Photo 加播放图标
                        if self._item["type"] == "live_photo":
                            img_rgba = img.convert("RGBA")
                            ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
                            d  = ImageDraw.Draw(ov)
                            cx, cy, r2 = img.width//2, img.height//2, 22
                            d.ellipse([cx-r2, cy-r2, cx+r2, cy+r2], fill=(0, 0, 0, 140))
                            d.polygon([(cx-6, cy-9), (cx-6, cy+9), (cx+11, cy)], fill=(255, 255, 255, 230))
                            img = Image.alpha_composite(img_rgba, ov).convert("RGB")
                        cimg = ctk.CTkImage(img, img, (self.CARD_W, self.CARD_H-30))
                        self.img_lbl.after(0, lambda: self.img_lbl.configure(image=cimg))
                        self.img_lbl._img_ref = cimg  # 防止GC
                except Exception:
                    pass
        threading.Thread(target=_bg, daemon=True).start()

    @property
    def is_selected(self):
        return self._selected.get()

    @property
    def item(self):
        return self._item


# ═════════════════════════════════════════════════════════════════════════════
#  主应用
# ═════════════════════════════════════════════════════════════════════════════
class App(ctk.CTk):
    WIN_W, WIN_H = 460, 940

    def __init__(self):
        super().__init__()
        self.title("多平台去水印下载器")
        self.geometry(f"{self.WIN_W}x{self.WIN_H}")
        self.resizable(False, False)

        self._meta       = None      # 解析结果
        self._cards      = []        # MediaCard 列表
        self._cur_platform = ""

        # 主题（从配置读取，支持浅色/深色液态玻璃）
        cfg = _load_cfg()
        self.theme_name = cfg.get("theme", ui_theme.DEFAULT_THEME)
        self.T          = ui_theme.get(self.theme_name)
        ctk.set_appearance_mode(self.T["appearance"])
        self.configure(fg_color=self.T["window_bg"])

        self.save_dir     = ctk.StringVar(value=cfg.get("save_dir", os.path.join(os.path.expanduser("~"), "Desktop")))
        self.sessionid    = ctk.StringVar(value=cfg.get("sessionid", ""))
        self._sid_visible = False

        self._build_ui()

    # ─────────────────────────── 界面构建 ────────────────────────────────────
    def _build_ui(self):
        T   = self.T
        PAD = 16

        # ── 顶部标题栏（液态玻璃渐变） ────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0, height=74)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        grad = ui_theme.gradient_image(self.WIN_W, 74, T["header_grad"])
        hdr_bg = ctk.CTkLabel(hdr, text="", image=grad, width=self.WIN_W, height=74)
        hdr_bg.place(x=0, y=0, relwidth=1, relheight=1)
        hdr_bg._img_ref = grad

        ctk.CTkLabel(hdr, text="去水印 · 多平台下载器",
                     font=ctk.CTkFont("Microsoft YaHei", 19, "bold"),
                     text_color=T["header_text"]).place(x=PAD, y=12)
        ctk.CTkLabel(hdr, text="豆包 / 小红书 / 抖音  无水印一键下载",
                     font=ctk.CTkFont("Microsoft YaHei", 11),
                     text_color=T["header_sub"]).place(x=PAD, y=46)

        self._theme_btn = ctk.CTkButton(
            hdr, text="深色" if self.theme_name == "glass_light" else "浅色",
            width=64, height=30, corner_radius=15,
            fg_color="#FFFFFF", hover_color="#E8E8F5", text_color="#3A3A4A",
            font=ctk.CTkFont("Microsoft YaHei", 11, "bold"),
            command=self._toggle_theme)
        self._theme_btn.place(relx=1.0, x=-PAD, y=22, anchor="ne")

        # ── 豆包 Session ID（可折叠玻璃条） ───────────────────────────────────
        sid_bar = ui_theme.glass_frame(self, T, corner_radius=14, height=40)
        sid_bar.pack(fill="x", padx=PAD, pady=(10, 0))
        sid_bar.pack_propagate(False)

        ctk.CTkLabel(sid_bar, text="豆包 ID", font=ctk.CTkFont("Microsoft YaHei", 11, "bold"),
                     text_color=T["text_sec"]).pack(side="left", padx=(12, 6), pady=9)

        self._sid_entry = ui_theme.glass_entry(sid_bar, T, textvariable=self.sessionid,
                                                height=26, show="*",
                                                font=ctk.CTkFont("Consolas", 10),
                                                placeholder_text="sessionid（可选，不填则公开模式）")
        self._sid_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=7)

        ui_theme.ghost_button(sid_bar, T, "显示", width=44, height=26, corner_radius=10,
                              font=ctk.CTkFont(size=11), command=self._toggle_sid
                              ).pack(side="left", padx=(0, 4), pady=7)

        ctk.CTkButton(sid_bar, text="保存", width=46, height=26, corner_radius=10,
                      fg_color=T["accent"], hover_color=T["accent_hover"], text_color="#FFFFFF",
                      font=ctk.CTkFont("Microsoft YaHei", 10, "bold"),
                      command=self._save_sid).pack(side="right", padx=(0, 10), pady=7)

        # ── URL 输入（玻璃面板） ──────────────────────────────────────────────
        url_row = ui_theme.glass_frame(self, T, corner_radius=16, height=56)
        url_row.pack(fill="x", padx=PAD, pady=(10, 0))
        url_row.pack_propagate(False)

        self._badge = ctk.CTkLabel(url_row, text="", width=58, height=36, corner_radius=9,
                                   fg_color="transparent", font=ctk.CTkFont("Microsoft YaHei", 10, "bold"))
        self._badge.pack(side="left", padx=(10, 8))

        self._url_entry = ui_theme.glass_entry(url_row, T,
                                                placeholder_text="粘贴 豆包/小红书/抖音 分享链接...",
                                                height=38, font=ctk.CTkFont("Microsoft YaHei", 12))
        self._url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._url_entry.bind("<FocusIn>",   self._auto_paste)
        self._url_entry.bind("<KeyRelease>", self._on_url_change)

        self._parse_btn = ctk.CTkButton(url_row, text="解析", width=70, height=38, corner_radius=13,
                                          fg_color=T["accent"], hover_color=T["accent_hover"], text_color="#FFFFFF",
                                          font=ctk.CTkFont("Microsoft YaHei", 13, "bold"),
                                          command=self._start_parse)
        self._parse_btn.pack(side="right", padx=(0, 8))

        # ── 保存目录（玻璃面板） ──────────────────────────────────────────────
        dir_row = ui_theme.glass_frame(self, T, corner_radius=14, height=40)
        dir_row.pack(fill="x", padx=PAD, pady=(10, 0))
        dir_row.pack_propagate(False)

        ctk.CTkLabel(dir_row, text="保存至:", font=ctk.CTkFont("Microsoft YaHei", 11),
                     text_color=T["text_sec"]).pack(side="left", padx=(12, 6), pady=9)

        self._save_entry = ui_theme.glass_entry(dir_row, T, textvariable=self.save_dir,
                                                 height=26, font=ctk.CTkFont("Microsoft YaHei", 10))
        self._save_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=7)

        ui_theme.ghost_button(dir_row, T, "浏览", width=46, height=26, corner_radius=10,
                              font=ctk.CTkFont(size=12), command=self._pick_dir
                              ).pack(side="right", padx=(0, 8), pady=7)

        # ── 状态提示行 ────────────────────────────────────────────────────────
        self._status_lbl = ctk.CTkLabel(self, text="支持 豆包 / 小红书 / 抖音 三平台，粘贴链接自动识别",
                                         font=ctk.CTkFont("Microsoft YaHei", 10),
                                         text_color=T["text_faint"])
        self._status_lbl.pack(anchor="w", padx=PAD+4, pady=(10, 0))

        # ── ★ 内容区（动态） ★ ───────────────────────────────────────────────
        self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._content_frame.pack(fill="both", expand=True, padx=PAD, pady=(8, 0))
        self._show_empty_content()

        # ── 进度条 ────────────────────────────────────────────────────────────
        self._progress = ctk.CTkProgressBar(self, height=6, corner_radius=3,
                                             fg_color=T["panel_border"], progress_color=T["accent"])
        self._progress.pack(fill="x", padx=PAD, pady=(8, 0))
        self._progress.set(0)

        # ── 操作按钮行 ────────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=PAD, pady=(10, 12))

        self._dl_btn = ctk.CTkButton(btn_row, text="解析后即可下载", height=48, corner_radius=16,
                                      fg_color=T["accent"], hover_color=T["accent_hover"],
                                      text_color="#FFFFFF",
                                      font=ctk.CTkFont("Microsoft YaHei", 13, "bold"),
                                      state="disabled", command=self._start_download)
        self._dl_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ui_theme.ghost_button(btn_row, T, "打开", width=48, height=48, corner_radius=16,
                              font=ctk.CTkFont(size=18), command=self._open_folder
                              ).pack(side="right")


    # ─────────────────────────── 内容区管理 ──────────────────────────────────
    def _clear_content(self):
        """清空内容区所有子控件"""
        if hasattr(self, "_video_player") and self._video_player:
            self._video_player.stop()
            self._video_player = None
        for w in self._content_frame.winfo_children():
            w.destroy()
        self._cards = []

    def _show_empty_content(self):
        self._clear_content()
        ctk.CTkLabel(self._content_frame,
                     text="解析成功后在此展示内容\n\n支持：图文 / 动态图 / 视频",
                     font=ctk.CTkFont("Microsoft YaHei", 13),
                     text_color=self.T["text_faint"]).pack(expand=True)
        self._video_player = None

    def _show_video_content(self, meta: dict):
        """显示视频播放器内容区"""
        self._clear_content()
        T = self.T

        item = meta["media_items"][0]

        # 平台 + 无水印徽章
        badge_row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        badge_row.pack(fill="x", pady=(0, 8))
        pm = platform_detector.get_meta(meta["platform"])
        ctk.CTkLabel(badge_row, text=f"{pm['icon']} {pm['name']}",
                     fg_color=pm["badge_color"], corner_radius=8,
                     font=ctk.CTkFont("Microsoft YaHei", 10, "bold"),
                     text_color="#FFFFFF", padx=8, pady=2).pack(side="left")
        if meta.get("no_watermark"):
            ctk.CTkLabel(badge_row, text="无水印",
                         fg_color=T["ok"], corner_radius=8,
                         font=ctk.CTkFont("Microsoft YaHei", 10, "bold"),
                         text_color="#FFFFFF", padx=8, pady=2).pack(side="left", padx=6)

        # 作者/分辨率
        w, h = meta.get("width", 0), meta.get("height", 0)
        res_txt = f"  {w}×{h}" if w and h else ""
        ctk.CTkLabel(badge_row,
                     text=f"作者 {meta.get('author','')}{res_txt}",
                     font=ctk.CTkFont("Microsoft YaHei", 11),
                     text_color=T["text_sec"]).pack(side="right")

        # 播放器（玻璃卡片）
        player_wrap = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        player_wrap.pack()
        self._video_player = InlineVideoPlayer(player_wrap, T=T)
        self._video_player.frame.pack()

        cover = meta.get("cover_url") or item.get("thumb", "")
        if cover:
            self._video_player.load_poster(cover)
        self._video_player.set_url(item["url"])

        # 提示词/描述
        if meta.get("text"):
            txt_box = ctk.CTkTextbox(self._content_frame,
                                      font=ctk.CTkFont("Microsoft YaHei", 10),
                                      fg_color=T["panel_alt"], border_color=T["panel_border"],
                                      border_width=1, corner_radius=12, height=64,
                                      text_color=T["text_sec"])
            txt_box.pack(fill="x", pady=(10, 0))
            txt_box.insert("0.0", meta["text"])
            txt_box.configure(state="disabled")

    def _show_image_grid(self, meta: dict):
        """显示图片/动图网格内容区"""
        self._clear_content()
        T = self.T
        self._video_player = None

        pm = platform_detector.get_meta(meta["platform"])

        # 顶部信息行
        info_row = ctk.CTkFrame(self._content_frame, fg_color="transparent", height=28)
        info_row.pack(fill="x", pady=(0, 8))
        info_row.pack_propagate(False)

        ctk.CTkLabel(info_row, text=f"{pm['icon']} {pm['name']}",
                     fg_color=pm["badge_color"], corner_radius=8,
                     font=ctk.CTkFont("Microsoft YaHei", 10, "bold"),
                     text_color="#FFFFFF", padx=8, pady=2).pack(side="left")

        from collections import Counter
        cnt = Counter(it["type"] for it in meta["media_items"])
        parts = []
        if cnt.get("image"):      parts.append(f"图 {cnt['image']}")
        if cnt.get("live_photo"): parts.append(f"动图 {cnt['live_photo']}")
        if cnt.get("video"):      parts.append(f"视频 {cnt['video']}")
        ctk.CTkLabel(info_row,
                     text="  ".join(parts) + f"　共 {len(meta['media_items'])} 项",
                     font=ctk.CTkFont("Microsoft YaHei", 11),
                     text_color=T["text_sec"]).pack(side="right")

        ctk.CTkLabel(info_row, text=f"作者 {meta.get('author','')}",
                     font=ctk.CTkFont("Microsoft YaHei", 11),
                     text_color=T["text_faint"]).pack(side="right", padx=10)

        # 全选 / 取消全选
        ctrl_row = ctk.CTkFrame(self._content_frame, fg_color="transparent", height=26)
        ctrl_row.pack(fill="x", pady=(0, 6))
        ctrl_row.pack_propagate(False)
        ui_theme.ghost_button(ctrl_row, T, "全选", width=56, height=22, corner_radius=10,
                              font=ctk.CTkFont("Microsoft YaHei", 10),
                              command=lambda: [c._selected.set(True) for c in self._cards]
                              ).pack(side="left", padx=(0, 6))
        ui_theme.ghost_button(ctrl_row, T, "取消全选", width=72, height=22, corner_radius=10,
                              font=ctk.CTkFont("Microsoft YaHei", 10),
                              command=lambda: [c._selected.set(False) for c in self._cards]
                              ).pack(side="left")

        # 滚动区域
        scroll = ctk.CTkScrollableFrame(self._content_frame, fg_color="transparent",
                                         height=430,
                                         scrollbar_button_color=T["scroll"],
                                         scrollbar_button_hover_color=T["scroll_hover"])
        scroll.pack(fill="both", expand=True)

        # 2列网格
        items = meta["media_items"]
        for i in range(0, len(items), 2):
            row_f = ctk.CTkFrame(scroll, fg_color="transparent")
            row_f.pack(fill="x", pady=4)
            for j in range(2):
                if i + j < len(items):
                    card = MediaCard(row_f, items[i+j], i+j,
                                     on_click=lambda it: self._preview_item(it),
                                     T=T)
                    card.outer.pack(side="left", padx=4)
                    self._cards.append(card)

    def _preview_item(self, item: dict):
        """点击缩略图预览（弹出内嵌迷你播放器或大图）"""
        url = item.get("url", "")
        if not url:
            return
        if item["type"] == "live_photo":
            # 弹窗播放动态图
            self._popup_video(url, item.get("thumb", ""), title="动态图预览")
        elif item["type"] == "image":
            # 浏览器打开原图
            import webbrowser
            webbrowser.open(url)

    def _popup_video(self, video_url, thumb_url="", title="视频预览"):
        """弹出小窗口播放视频"""
        T = self.T
        popup = ctk.CTkToplevel(self)
        popup.title(title)
        popup.geometry("268x520")
        popup.resizable(False, False)
        popup.configure(fg_color=T["window_bg"])
        popup.grab_set()

        player = InlineVideoPlayer(popup, width=240, height=427, T=T)
        player.frame.pack(padx=10, pady=(10, 6))
        if thumb_url:
            player.load_poster(thumb_url)
        player.set_url(video_url)

        ui_theme.ghost_button(popup, T, "关闭", width=90, height=30,
                              command=lambda: (player.stop(), popup.destroy())
                              ).pack(pady=(0, 10))

    # ─────────────────────────── 辅助操作 ────────────────────────────────────
    def _toggle_sid(self):
        self._sid_visible = not self._sid_visible
        self._sid_entry.configure(show="" if self._sid_visible else "*")

    def _save_sid(self):
        cfg = _load_cfg()
        cfg["sessionid"] = self.sessionid.get().strip()
        cfg["save_dir"]  = self.save_dir.get()
        _save_cfg(cfg)
        self._set_status("Session ID 已保存", self.T["ok"])

    def _pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.save_dir.get())
        if d:
            self.save_dir.set(d)
            cfg = _load_cfg()
            cfg["save_dir"] = d
            _save_cfg(cfg)

    def _open_folder(self):
        import webbrowser
        p = self.save_dir.get()
        if os.path.exists(p):
            webbrowser.open(f"file:///{p}")
        else:
            messagebox.showerror("错误", "文件夹不存在！")

    def _set_status(self, text, color=None):
        if color is None:
            color = self.T["text_faint"]
        self._status_lbl.configure(text=text, text_color=color)

    def _toggle_theme(self):
        """切换 浅色/深色 液态玻璃主题，并保留当前解析结果"""
        self.theme_name = "glass_dark" if self.theme_name == "glass_light" else "glass_light"
        self.T = ui_theme.get(self.theme_name)
        cfg = _load_cfg()
        cfg["theme"] = self.theme_name
        _save_cfg(cfg)
        ctk.set_appearance_mode(self.T["appearance"])
        self.configure(fg_color=self.T["window_bg"])
        meta = self._meta
        # 关键：先销毁窗口内全部旧控件，否则重建时会与新控件叠加重复
        self._video_player = None
        self._cards = []
        for w in self.winfo_children():
            w.destroy()
        self._build_ui()
        if meta:
            self._render_meta(meta)
            self._progress.set(0.1)

    def _auto_paste(self, event=None):
        try:
            clip = self.clipboard_get()
            cur  = self._url_entry.get().strip()
            if not cur and any(d in clip for d in ["doubao.com","xhslink","xiaohongshu","douyin.com"]):
                self._url_entry.delete(0, "end")
                self._url_entry.insert(0, clip)
                self._on_url_change()
        except Exception:
            pass

    def _on_url_change(self, event=None):
        """URL 变化时实时更新平台徽章"""
        url = self._url_entry.get().strip()
        if not url:
            self._badge.configure(text="", fg_color="transparent")
            return
        plat = platform_detector.detect(url)
        pm   = platform_detector.get_meta(plat)
        if plat != "unknown":
            self._badge.configure(
                text=pm["name"],
                fg_color=pm["badge_color"],
                text_color="#FFFFFF")
        else:
            self._badge.configure(text="", fg_color="transparent")


    # ─────────────────────────── 解析流程 ────────────────────────────────────
    def _start_parse(self):
        url = self._url_entry.get().strip()
        if not url:
            messagebox.showwarning("提示", "请先输入分享链接。")
            return
        plat = platform_detector.detect(url)
        if plat == "unknown":
            messagebox.showwarning("提示", "暂不支持该平台，目前支持：豆包、小红书、抖音。")
            return

        self._parse_btn.configure(state="disabled", text="解析中...")
        self._dl_btn.configure(state="disabled")
        self._set_status(f"正在解析 {platform_detector.get_meta(plat)['name']} 链接...", self.T["accent"])
        self._progress.set(0)

        if hasattr(self, "_video_player") and self._video_player:
            self._video_player.stop()

        threading.Thread(target=self._bg_parse, args=(url, plat), daemon=True).start()

    def _bg_parse(self, url, plat):
        try:
            # 自动识别分享文本中的链接（兼容整段复制的小红书/抖音分享文案）
            url = platform_detector.extract_url(url)
            if plat == "doubao":
                sid  = self.sessionid.get().strip()
                meta = doubao_parser.parse(url, sessionid=sid)
                # 统一格式转换
                meta["platform"]    = "doubao"
                meta["type"]        = "video"
                meta["media_items"] = [{
                    "type":  "video",
                    "url":   meta["video_url"],
                    "thumb": meta.get("poster_url", ""),
                }]
                meta.setdefault("author", meta.get("nickname", "豆包用户"))
                meta.setdefault("text",   meta.get("prompt", ""))
                meta.setdefault("cover_url", meta.get("poster_url", ""))
            elif plat == "xiaohongshu":
                meta = xiaohongshu_parser.parse(url)
            elif plat == "douyin":
                meta = douyin_parser.parse(url)
            else:
                raise ValueError("不支持的平台")

            self._meta = meta
            self.after(0, self._on_parse_ok)
        except Exception as e:
            self.after(0, self._on_parse_fail, str(e))

    def _on_parse_ok(self):
        self._parse_btn.configure(state="normal", text="解析")
        self._render_meta(self._meta)

    def _render_meta(self, meta: dict):
        """按内容类型渲染内容区（解析成功 / 主题切换后复用）"""
        pm = platform_detector.get_meta(meta["platform"])

        if meta["type"] in ("video", "live_photo") and len(meta["media_items"]) == 1:
            self._show_video_content(meta)
            dl_text = "下载视频（无水印）"
        elif meta["type"] == "live_photo":
            # 多动图 → 网格
            self._show_image_grid(meta)
            dl_text = "下载所选动图视频"
        else:
            # image
            self._show_image_grid(meta)
            dl_text = f"下载所选图片（共 {len(meta['media_items'])} 张）"

        self._dl_btn.configure(state="normal", text=dl_text)
        self._set_status(
            f"解析成功 | {pm['name']} | "
            f"{'无水印' if meta.get('no_watermark') else '含水印'}",
            self.T["ok"])
        self._progress.set(0.1)

    def _on_parse_fail(self, msg):
        self._parse_btn.configure(state="normal", text="解析")
        self._set_status(f"解析失败: {msg[:60]}", self.T["err"])
        messagebox.showerror("解析失败", f"链接解析失败：\n{msg}")

    # ─────────────────────────── 下载流程 ────────────────────────────────────
    def _start_download(self):
        if not self._meta:
            return
        self._dl_btn.configure(state="disabled", text="下载中...")
        self._parse_btn.configure(state="disabled")
        threading.Thread(target=self._bg_download, daemon=True).start()

    def _bg_download(self):
        meta     = self._meta
        save_dir = self.save_dir.get()
        os.makedirs(save_dir, exist_ok=True)

        try:
            if meta["type"] == "video" or (
                meta["type"] == "live_photo" and len(meta["media_items"]) == 1
            ):
                # 单视频下载
                item  = meta["media_items"][0]
                fname = f"{meta['platform']}_{meta.get('note_id') or meta.get('video_id') or meta.get('vid','')}.mp4"
                path  = os.path.join(save_dir, fname)
                path  = self._dl_one(item, path, total=1, index=0)
                self.after(0, self._on_dl_ok, [path])

            else:
                # 多文件下载（图片 / 动图）
                selected = [c.item for c in self._cards if c.is_selected]
                if not selected:
                    self.after(0, lambda: messagebox.showwarning("提示", "请至少勾选一个文件！"))
                    self.after(0, self._reset_btn)
                    return

                base_id = meta.get("note_id") or meta.get("video_id") or "xhs"
                saved = []
                for i, item in enumerate(selected):
                    ext   = ".mp4" if item["type"] == "live_photo" else ""
                    fname = f"{meta['platform']}_{base_id}_{i+1}{ext}"
                    path  = os.path.join(save_dir, fname)
                    path  = self._dl_one(item, path, total=len(selected), index=i)
                    saved.append(path)

                self.after(0, self._on_dl_ok, saved)

        except Exception as e:
            self.after(0, self._on_dl_fail, str(e))

    _CT_EXT = {
        "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
        "image/webp": ".webp", "image/gif": ".gif",
        "video/mp4": ".mp4", "video/quicktime": ".mov",
    }

    def _dl_one(self, item, path, total=1, index=0):
        """下载单个文件（item 含 url/fallback），按 Content-Type 修正扩展名，更新进度条"""
        url = item["url"]
        headers = {"User-Agent": "Mozilla/5.0"}
        r = _HTTP.get(url, headers=headers, stream=True, timeout=30)
        # 主链接 403/404 时自动回退到备用链接（如原图失败 → 用压缩图）
        if r.status_code in (403, 404) and item.get("fallback"):
            r.close()
            r = _HTTP.get(item["fallback"], headers=headers, stream=True, timeout=30)
        r.raise_for_status()

        # 根据 Content-Type 修正扩展名（原图可能是 png/webp，不能一律存 .jpg）
        ct = r.headers.get("Content-Type", "").lower().split(";")[0].strip()
        ext = self._CT_EXT.get(ct, "")
        if ext and not path.lower().endswith(ext):
            path = os.path.splitext(path)[0] + ext

        total_size = int(r.headers.get("Content-Length", 0))
        downloaded = 0
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=512*1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    file_pct  = downloaded / total_size
                    total_pct = (index + file_pct) / total
                    self.after(0, lambda p=total_pct: self._progress.set(p))
                    self.after(0, lambda p=int(file_pct*100):
                               self._set_status(f"下载中 {index+1}/{total}  {p}%...", self.T["accent"]))
        return path

    def _on_dl_ok(self, paths):
        self._progress.set(1.0)
        self._reset_btn()
        if len(paths) == 1:
            self._set_status(f"下载完成：{os.path.basename(paths[0])}", self.T["ok"])
        else:
            self._set_status(f"下载完成，共 {len(paths)} 个文件", self.T["ok"])
        if messagebox.askyesno("下载成功",
                               f"已保存 {len(paths)} 个文件到：\n{self.save_dir.get()}\n\n是否打开文件夹？"):
            import webbrowser
            webbrowser.open(f"file:///{self.save_dir.get()}")

    def _on_dl_fail(self, msg):
        self._progress.set(0)
        self._reset_btn()
        self._set_status(f"下载失败: {msg[:60]}", self.T["err"])
        messagebox.showerror("下载失败", msg)

    def _reset_btn(self):
        self._parse_btn.configure(state="normal")
        meta = self._meta
        if meta:
            t = meta.get("type", "")
            if t == "video":
                txt = "下载视频（无水印）"
            elif t == "live_photo":
                txt = "下载所选动图视频"
            else:
                txt = f"下载所选图片（共 {len(meta['media_items'])} 张）"
        else:
            txt = "解析后即可下载"
        self._dl_btn.configure(state="normal" if meta else "disabled", text=txt)


# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()
