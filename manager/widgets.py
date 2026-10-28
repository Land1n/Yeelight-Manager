"""Карточка лампы в окне Flet: индикаторы состояния, ползунки, откат."""

from __future__ import annotations

import flet as ft

from manager.theme import (ACCENT, BORDER, CYAN, DANGER, MUTED, MUTED_2, SURFACE_3, TEXT, btn,
                           card, caption, dot, field, meter, slider)

CT_MIN, CT_MAX = 1700, 6500
CHANNELS = (("r", 255, "#ff6b6b"), ("g", 128, "#7cf29a"), ("b", 60, "#6bb8ff"))

class LampCard:
    """Одна лампа. Значения ползунков подтягиваются с лампы, пока их не двигают."""

    def __init__(self, ip, run):
        self.ip = ip
        self.run = run  # run(label, action) — фоновое выполнение с индикатором загрузки
        self.dragging = False
        self.rgb = (255, 255, 255)

        self.dot = dot(MUTED)
        self.power_text = ft.Text("нет данных", size=13, weight=ft.FontWeight.BOLD, color=MUTED)
        self.last_text = caption("ожидание команд", MUTED_2, 11)
        self.bright_text = caption("яркость —", MUTED)
        self.ct_text = caption("температура —", MUTED)
        self.swatch = ft.Container(width=30, height=30, border_radius=8, bgcolor=SURFACE_3,
                                   border=ft.Border.all(1, BORDER))
        self.busy = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ACCENT, visible=False)
        self.bright_meter = meter(ACCENT, 0, expand=True)
        self.ct_meter = meter(CYAN, 0, expand=True)
        # expand у ползунков работает только внутри Row: Column в ListView высоты не имеет.
        self.bright = slider(1, 100, 50, "яркость {value}%", expand=True)
        self.ct = slider(CT_MIN, CT_MAX, 4000, "{value} K", color=CYAN, expand=True)
        self.hex_field = field("Цвет (#rrggbb)", width=170, value="#ffffff")
        self.channels = {}
        for name, value, color in CHANNELS:
            control = slider(0, 255, value, f"{name.upper()}: {{value}}", color=color, expand=True)
            control.on_change_start = self._drag_start
            control.on_change_end = self._end_rgb
            self.channels[name] = control
        self.bright.on_change_start = self._drag_start
        self.bright.on_change_end = self._end_brightness
        self.ct.on_change_start = self._drag_start
        self.ct.on_change_end = self._end_temp

        rows = ft.Column([
            ft.Row([self.bright_text, self.busy], spacing=8),
            ft.Row([self.bright_meter]),
            ft.Row([self.bright]),
            ft.Row([self.ct_text]),
            ft.Row([self.ct_meter]),
            ft.Row([self.ct]),
            ft.Row(list(self.channels.values()), spacing=14),
            ft.Row([self.hex_field,
                    btn("Применить цвет", self._apply_hex, primary=True, icon=ft.Icons.COLORIZE)]),
        ], spacing=6)

        buttons = ft.Row([
            btn("Вкл", self._send("turn_on"), primary=True, icon=ft.Icons.POWER_SETTINGS_NEW),
            btn("Выкл", self._send("turn_off"), icon=ft.Icons.POWER_OFF),
            btn("Переключить", self._send("toggle"), icon=ft.Icons.REFRESH),
            btn("Откатить", self._send("undo"), icon=ft.Icons.UNDO),
            btn("Удалить", self._send("remove"), danger=True, icon=ft.Icons.DELETE),
        ], wrap=True, spacing=8)

        head = ft.Row([self.dot, ft.Text(ip, expand=True, weight=ft.FontWeight.BOLD, color=TEXT),
                       self.power_text, self.swatch], spacing=10)
        self.view = card(ft.Column([head, self.last_text, rows, buttons], spacing=10))

    # ---------- действия ----------
    def _send(self, kind):
        """Кнопка: отправить действие ядру (разбирает его app.perform)."""
        def handler(_=None):
            self.run(kind, {"type": kind, "ip": self.ip})
        return handler

    def _apply_hex(self, _=None):
        value = (self.hex_field.value or "").strip().lstrip("#")
        self.run("цвет", {"type": "set_hex", "ip": self.ip, "value": value})

    def _drag_start(self, _=None):
        self.dragging = True

    def _end_brightness(self, _=None):
        self.dragging = False
        self.run("яркость", {"type": "set_brightness", "ip": self.ip,
                             "value": int(self.bright.value)})

    def _end_temp(self, _=None):
        self.dragging = False
        self.run("температура", {"type": "set_color_temp", "ip": self.ip,
                                 "kelvin": int(self.ct.value)})

    def _end_rgb(self, _=None):
        self.dragging = False
        values = {name: int(control.value) for name, control in self.channels.items()}
        self.run("цвет RGB", {"type": "set_rgb", "ip": self.ip, **values})

    def report(self, text, ok=True):
        self.last_text.value = ("✓ " if ok else "✕ ") + text
        self.last_text.color = ACCENT if ok else DANGER

    def set_busy(self, visible):
        self.busy.visible = visible

    # ---------- обновление из состояния ядра ----------
    def update(self, lamp):
        props = lamp.props or {}
        self.dot.bgcolor = ACCENT if lamp.online else (DANGER if lamp.online is False else MUTED)
        power = props.get("power")
        self.power_text.value = {"on": "включена", "off": "выключена"}.get(power, "нет данных")
        self.power_text.color = ACCENT if power == "on" else MUTED
        bright, ct, rgb = props.get("bright"), props.get("ct"), props.get("rgb")
        self.bright_text.value = f"яркость {bright if bright is not None else '—'}%"
        self.ct_text.value = f"температура {ct if ct is not None else '—'} K"
        self.bright_meter.value = (bright or 0) / 100
        self.ct_meter.value = ((ct or CT_MIN) - CT_MIN) / (CT_MAX - CT_MIN)
        if isinstance(rgb, int):
            self.rgb = ((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255)
        self.swatch.bgcolor = f"#{self.rgb[0]:02x}{self.rgb[1]:02x}{self.rgb[2]:02x}"
        if self.dragging:
            return
        if bright is not None:
            self.bright.value = bright
        if ct is not None:
            self.ct.value = ct
        if isinstance(rgb, int):
            for name, channel in zip(("r", "g", "b"), self.rgb):
                self.channels[name].value = channel
