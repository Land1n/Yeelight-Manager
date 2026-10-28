"""Карточка лампы и лента запросов в окне Flet."""

from __future__ import annotations

import time

import flet as ft

from manager.theme import (ACCENT, BORDER, CYAN, DANGER, MUTED, MUTED_2, RADIUS, SURFACE_2,
                           SURFACE_3, TEXT, btn, card, caption, dot, field, meter, slider)

CT_MIN, CT_MAX = 1700, 6500
CHANNELS = (("r", 255, "#ff6b6b"), ("g", 128, "#7cf29a"), ("b", 60, "#6bb8ff"))
FEED_LIMIT = 20
FEED_STATUS = {"run": (CYAN, "→"), "ok": (ACCENT, "✓"), "err": (DANGER, "✕")}

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


class RequestFeed:
    """Лента «запрос → ответ» над вкладками, как уведомления на сайте."""

    def __init__(self, limit=FEED_LIMIT):
        self.limit = limit
        self.rows = ft.ListView(height=112, spacing=6, auto_scroll=True)
        self.title = caption("запрошено: 0 · отвечено: 0", MUTED_2, 11)
        self.view = card(ft.Column([self.title, self.rows], spacing=4), padding=8)
        self.items = []
        self._seq = 0
        self._sent = self._answered = 0

    def start(self, label, ip=None):
        """Запрос ушёл: сразу виден в ленте со статусом «выполняется»."""
        self._seq += 1
        self._sent += 1
        item = {"id": self._seq, "label": label, "ip": ip, "time": time.strftime("%H:%M:%S"),
                "status": "run", "answer": "выполняется…"}
        self.items.append(item)
        del self.items[:-self.limit]
        self._draw()
        return item["id"]

    def finish(self, key, message, ok, seconds):
        """Ответ пришёл: та же строка ленты получает результат и время выполнения."""
        self._answered += 1
        for item in self.items:
            if item["id"] == key:
                item["status"] = "ok" if ok else "err"
                item["answer"] = f"{message} · {seconds} с"
        self._draw()

    def _draw(self):
        self.title.value = f"запрошено: {self._sent} · отвечено: {self._answered}"
        self.rows.controls = [self._row(item) for item in self.items]

    def _row(self, item):
        color, mark = FEED_STATUS[item["status"]]
        answer = MUTED if item["status"] != "err" else DANGER
        what = " · ".join(part for part in (item["label"], item["ip"]) if part)
        return ft.Container(
            content=ft.Row([
                ft.Text(mark, color=color, weight=ft.FontWeight.BOLD),
                ft.Column([ft.Text(what, color=TEXT, size=12.5),
                           ft.Text(item["answer"], color=answer, size=11.5)],
                          expand=True, spacing=1),
                ft.Text(item["time"], color=MUTED_2, size=11),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.START),
            padding=7, border_radius=RADIUS, bgcolor=SURFACE_2,
            border=ft.Border(left=ft.BorderSide(3, color), top=ft.BorderSide(1, BORDER),
                             right=ft.BorderSide(1, BORDER), bottom=ft.BorderSide(1, BORDER)),
        )
