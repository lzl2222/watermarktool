# -*- coding: utf-8 -*-
"""移动端玻璃组件库：玻璃按钮 / 加载旋转环 / 进度胶囊 / 玻璃卡片 / 胶囊徽章"""
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, StringProperty, BooleanProperty
from kivy.uix.button import ButtonBehavior
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse, PushMatrix, PopMatrix, Rotate

from theme import hex2rgba


def _rounded(widget, color, radius, border=None, border_w=0):
    """在 widget.canvas.before 绘制圆角底（刷新前先清空）"""
    widget.canvas.before.clear()
    with widget.canvas.before:
        if border:
            Color(*border)
            RoundedRectangle(pos=(widget.x-border_w, widget.y-border_w),
                             size=(widget.width+2*border_w, widget.height+2*border_w),
                             radius=radius)
        Color(*color)
        RoundedRectangle(pos=widget.pos, size=widget.size, radius=radius)


class GlassButton(ButtonBehavior, Widget):
    """玻璃按钮：圆角半透明底 + 描边 + 按压反馈动画"""
    text = StringProperty("")
    primary = BooleanProperty(False)

    def __init__(self, text="", on_click=None, primary=False, height=52,
                 font_size=16, T=None, **kw):
        super().__init__(**kw)
        self.text = text
        self.primary = primary
        self._T = T
        self._on_click = on_click
        self.size_hint = (None, None)
        self.width = dp(200)
        self.height = dp(height)
        self._label = Label(text=text, font_size=dp(font_size), bold=primary,
                            color=hex2rgba("#FFFFFF", 1.0) if primary else hex2rgba(T["text"], 1.0),
                            size_hint=(None, None))
        self.add_widget(self._label)
        self.bind(pos=self._redraw, size=self._redraw, text=self._set_text)
        self.bind(on_press=self._press, on_release=self._release)
        self._redraw()

    def _set_text(self, *a):
        self._label.text = self.text
        self._label.size = self._label.texture_size

    def _redraw(self, *a):
        self._label.center = self.center
        self._label.font_size = dp(16 if not self.primary else 17)
        T = self._T
        if self.primary:
            _rounded(self, hex2rgba(T["accent"]), [dp(16)], border=hex2rgba(T["accent_down"], 0.5), border_w=1)
        else:
            _rounded(self, T["glass"], [dp(16)], border=T["glass_border"], border_w=1)

    def _press(self, *a):
        self._label.y -= dp(1)
        self.opacity = 0.85
        if self.primary:
            T = self._T
            _rounded(self, hex2rgba(T["accent_down"]), [dp(16)], border=hex2rgba(T["accent_down"], 0.5), border_w=1)

    def _release(self, *a):
        self._label.y += dp(1)
        Animation(opacity=1.0, duration=0.15, t="out_quad").start(self)
        Clock.schedule_once(lambda dt: self._redraw(), 0.01)

    def on_touch_down(self, touch):
        if self.disabled:
            return False
        return super().on_touch_down(touch)


class LoadingSpinner(Widget):
    """旋转流光圆环（解析加载动画）"""
    angle = NumericProperty(0)

    def __init__(self, T=None, size=56, **kw):
        super().__init__(**kw)
        self._T = T
        self.size_hint = (None, None)
        self.size = (dp(size), dp(size))
        self._anim = None
        self.bind(pos=self._redraw, size=self._redraw, angle=self._redraw)
        self._redraw()

    def _redraw(self, *a):
        self.canvas.clear()
        with self.canvas:
            Color(*self._T["glass_border"])
            Line(circle=(self.center_x, self.center_y, self.width/2 - dp(3)),
                 width=dp(3))
            PushMatrix()
            Rotate(angle=self.angle, origin=self.center)
            Color(*hex2rgba(self._T["accent"]))
            Line(circle=(self.center_x, self.center_y, self.width/2 - dp(3)),
                 width=dp(3), angle_start=0, angle_end=120)
            PopMatrix()

    def start(self):
        self.stop()
        self._anim = Animation(angle=360, duration=0.8, t="linear")
        self._anim.repeat = True
        self._anim.start(self)

    def stop(self):
        if self._anim:
            self._anim.stop(self)
            self._anim = None


class ProgressCapsule(Widget):
    """下载进度胶囊：进度填充 + 百分比 + 完成对勾/失败抖动"""
    progress = NumericProperty(0.0)
    state = StringProperty("idle")   # idle | downloading | success | error

    def __init__(self, T=None, height=54, **kw):
        super().__init__(**kw)
        self._T = T
        self.size_hint = (None, None)
        self.height = dp(height)
        self._label = Label(text="下载所选", font_size=dp(16), bold=True,
                            color=hex2rgba("#FFFFFF", 1.0), size_hint=(None, None))
        self.add_widget(self._label)
        self.bind(pos=self._redraw, size=self._redraw, progress=self._redraw,
                  state=self._redraw, text=self._set_text)
        self._redraw()

    def _set_text(self, *a):
        self._label.text = self.text
        self._label.center = self.center

    @property
    def text(self):
        st = self.state
        if st == "downloading":
            return f"{int(self.progress*100)}%"
        if st == "success":
            return "已保存到相册"
        if st == "error":
            return "下载失败"
        return "下载所选"

    def _redraw(self, *a):
        self._label.center = self.center
        T = self._T
        self.canvas.before.clear()
        with self.canvas.before:
            # 轨道
            Color(*hex2rgba(T["accent"], 0.25) if self.state != "error" else hex2rgba(T["err"], 0.25))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])
            # 进度填充
            if self.progress > 0:
                w = max(self.width * self.progress, dp(20))
                if self.state == "error":
                    Color(*hex2rgba(T["err"], 0.9))
                elif self.state == "success":
                    Color(*hex2rgba(T["ok"], 0.9))
                else:
                    Color(*hex2rgba(T["accent"], 0.9))
                RoundedRectangle(pos=self.pos, size=(w, self.height), radius=[dp(16)])

    def start_download(self):
        self.state = "downloading"
        self.progress = 0.0

    def update(self, pct):
        Animation(progress=pct, duration=0.4, t="out_quad").start(self)

    def finish(self):
        self.progress = 1.0
        self.state = "success"
        # 对勾弹跳
        anim = Animation(opacity=1.0, duration=0.0) + \
               Animation(size=(self.width*1.06, self.height*1.06), duration=0.15, t="out_back") + \
               Animation(size=(self.width, self.height), duration=0.15, t="out_back")
        anim.start(self)

    def fail(self):
        self.state = "error"
        self.progress = 0.0
        # 抖动
        a = Animation(x=self.x-6, duration=0.05) + Animation(x=self.x+6, duration=0.05) + \
            Animation(x=self.x-6, duration=0.05) + Animation(x=self.x+6, duration=0.05) + \
            Animation(x=self.x, duration=0.05)
        a.start(self)


class GlassCard(Widget):
    """玻璃卡片：半透明圆角面板 + 细描边，可放子控件"""
    def __init__(self, T=None, radius=20, **kw):
        super().__init__(**kw)
        self._T = T
        self._radius = radius
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *a):
        _rounded(self, self._T["glass"], [dp(self._radius)], border=self._T["glass_border"], border_w=1)


class Pill(Widget):
    """胶囊徽章（平台/无水印/类型角标）"""
    text = StringProperty("")
    color = ListProperty([0, 0, 0, 1])

    def __init__(self, text="", color="#2563EB", text_color="#FFFFFF", T=None, **kw):
        super().__init__(**kw)
        self.text = text
        self.color = list(hex2rgba(color))
        self._text_color = hex2rgba(text_color)
        self._label = Label(text=text, font_size=dp(12), bold=True,
                            color=self._text_color, size_hint=(None, None))
        self.add_widget(self._label)
        self.size_hint = (None, None)
        self.bind(pos=self._redraw, size=self._redraw, text=self._set_text, color=self._redraw)
        self._redraw()

    def _set_text(self, *a):
        self._label.text = self.text
        self._label.size = self._label.texture_size
        self.width = self._label.width + dp(16)
        self.height = dp(26)

    def _redraw(self, *a):
        self._label.center = self.center
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(13)])
