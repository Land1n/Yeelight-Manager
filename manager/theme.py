"""Цвета и мелкие помощники окна Flet: тот же стиль, что у сайта."""

from __future__ import annotations

import flet as ft

# Цвета и размеры повторяют server/frontend/src/app.css (тёмная тема сайта).
BG, SURFACE, SURFACE_2, SURFACE_3 = "#080b10", "#10151e", "#151c27", "#1b2431"
BORDER, TEXT, MUTED, MUTED_2 = "#3a4658", "#e9eef6", "#93a3b8", "#6f8098"
ACCENT, INK, DANGER, WARN, CYAN = "#b6f24a", "#0b1206", "#ff8080", "#f5c76a", "#5ad1e6"
RADIUS, CARD_RADIUS = 10, 14


def apply_theme(page):
    theme = ft.Theme(
        font_family="Segoe UI",
        color_scheme=ft.ColorScheme(primary=ACCENT, on_primary=INK, surface=SURFACE,
                                    on_surface=TEXT, outline=BORDER, error=DANGER),
    )
    page.theme = theme
    page.dark_theme = theme
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG


def btn(text, on_click, primary=False, danger=False, icon=None, width=None):
    color = ACCENT if primary else (DANGER if danger else SURFACE_3)
    ink = INK if primary else TEXT
    return ft.Button(text, icon=icon, on_click=on_click, width=width, bgcolor=color, color=ink,
                     style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=RADIUS)))


def field(label, **kwargs):
    return ft.TextField(label=label, border_radius=RADIUS, border_color=BORDER,
                        focused_border_color=ACCENT, bgcolor=SURFACE_2, filled=True,
                        label_style=ft.TextStyle(color=MUTED), **kwargs)


def card(content, bgcolor=SURFACE_2, padding=12):
    return ft.Container(content=content, padding=padding, border_radius=CARD_RADIUS,
                        bgcolor=bgcolor, border=ft.Border.all(1, BORDER))


def dot(color=MUTED, size=10):
    return ft.Container(width=size, height=size, border_radius=size, bgcolor=color)


def meter(color=ACCENT, value=0):
    return ft.ProgressBar(value=value, color=color, bgcolor=SURFACE_3, border_radius=999,
                          bar_height=6)


def slider(minimum, maximum, value, label, color=ACCENT, **kwargs):
    return ft.Slider(min=minimum, max=maximum, value=value, label=label, active_color=color,
                     inactive_color=SURFACE_3, thumb_color=color, **kwargs)


def caption(text, color=MUTED, size=12):
    return ft.Text(text, color=color, size=size)
