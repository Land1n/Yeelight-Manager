"""Окно manager на Flet: лампы, режимы, настройка, журнал."""

from __future__ import annotations

import time

import flet as ft

from lamp.network import connect_to_wifi, enable_lan_control

from manager.core import Core
from manager.sync import Syncer

# Цвета и размеры совпадают с server/frontend/src/app.css (тёмная тема сайта).
BG, SURFACE, SURFACE_2, SURFACE_3 = "#080b10", "#10151e", "#151c27", "#1b2431"
BORDER, TEXT, MUTED = "#3a4658", "#e9eef6", "#93a3b8"
ACCENT, INK, DANGER, CONSOLE_BG = "#b6f24a", "#0b1206", "#ff8080", "#070a0f"
RADIUS = 10


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


def btn(text, on_click, primary=False, icon=None):
    return ft.Button(text, icon=icon, on_click=on_click,
                     bgcolor=ACCENT if primary else SURFACE_3,
                     color=INK if primary else TEXT,
                     style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=RADIUS)))


def field(label, **kwargs):
    return ft.TextField(label=label, border_radius=RADIUS, border_color=BORDER,
                        focused_border_color=ACCENT, bgcolor=SURFACE_2, filled=True,
                        label_style=ft.TextStyle(color=MUTED), **kwargs)


def card(content):
    return ft.Container(content=content, padding=12, border_radius=14, bgcolor=SURFACE_2,
                        border=ft.Border.all(1, BORDER))


def main(page: ft.Page):
    page.title = "Yeelight manager"
    page.window.width = 900
    page.window.height = 680
    page.padding = 12
    apply_theme(page)

    core = Core()
    core.start()
    syncer = Syncer(core)
    msg = ft.Text("")

    def notify(text):
        msg.value = text
        page.update()

    def guarded(fn):
        """Запуск операции с сообщением об ошибке вместо падения UI."""
        def run(*_):
            try:
                notify(fn() or "готово")
            except Exception as ex:
                notify(f"ошибка: {ex}")
        return run

    def in_background(fn):
        def run(*_):
            def job():
                try:
                    notify(fn() or "готово")
                except Exception as ex:
                    notify(f"ошибка: {ex}")
            page.run_thread(job)
        return run

    # Сигнатуры последней отрисовки: список перестраивается только при изменении данных,
    # иначе тикер каждую секунду заменяет кнопки и клики теряются.
    last = {}

    # ---------- Подключение ----------
    server_url = field("Адрес сервера", value=core.config["server_url"], expand=True)
    access_key = field("Ключ доступа", value=core.config["access_key"],
                       password=True, can_reveal_password=True, expand=True)
    sync_status = ft.Text("отключено", color=MUTED)

    def save_server(*_):
        core.update_config(server_url=server_url.value.strip(), access_key=access_key.value.strip())
        return "настройки сервера сохранены"

    def toggle_sync(*_):
        if syncer.running:
            syncer.stop()
            return "синхронизация остановлена"
        save_server()
        syncer.start()
        return "синхронизация запущена"

    connection_tab = ft.Column([
        ft.Row([server_url]),
        ft.Row([access_key]),
        ft.Row([btn("Сохранить", guarded(save_server), icon=ft.Icons.SAVE),
                btn("Запуск / стоп", guarded(toggle_sync), primary=True, icon=ft.Icons.SYNC),
                sync_status]),
    ])

    # ---------- Лампы ----------
    lamps_list = ft.ListView(expand=True, spacing=6)
    add_ip = field("IP лампы", width=220)

    def refresh_lamps(state):
        sig = [(lamp.ip, lamp.online) for lamp in state.lamps]
        if sig == last.get("lamps"):
            return
        last["lamps"] = sig
        lamps_list.controls.clear()
        for lamp in state.lamps:
            status = "онлайн" if lamp.online else "офлайн" if lamp.online is False else "нет данных"
            lamps_list.controls.append(card(ft.Row([
                ft.Text(f"{lamp.ip} — {status}", expand=True),
                ft.IconButton(ft.Icons.POWER_SETTINGS_NEW, tooltip="Вкл/выкл", icon_color=ACCENT,
                              on_click=guarded(lambda ip=lamp.ip: core.command(
                                  {"type": "toggle", "ip": ip}))),
                ft.IconButton(ft.Icons.UNDO, tooltip="Отменить", icon_color=TEXT,
                              on_click=guarded(lambda ip=lamp.ip: core.undo(ip))),
                ft.IconButton(ft.Icons.DELETE, tooltip="Удалить", icon_color=DANGER,
                              on_click=guarded(lambda ip=lamp.ip: core.remove(ip))),
            ])))

    def add_lamp(*_):
        core.add(add_ip.value)
        add_ip.value = ""
        return "лампа добавлена"

    lamps_tab = ft.Column([
        ft.Row([add_ip, btn("Добавить", guarded(add_lamp), primary=True),
                btn("Найти в сети", in_background(lambda: f"найдено: {len(core.discover())}"),
                    icon=ft.Icons.SEARCH)]),
        lamps_list,
    ], expand=True)

    # ---------- Режимы ----------
    modes_list = ft.ListView(expand=True, spacing=6)
    mode_lamp = ft.Dropdown(label="Лампа", width=220, options=[], border_radius=RADIUS,
                            border_color=BORDER, bgcolor=SURFACE_2, filled=True)

    def refresh_modes(state):
        sig = [(m["name"], m["running"], m["running_ip"], m["last_error"]) for m in state.modes]
        lamp_ips = [lamp.ip for lamp in state.lamps]
        if sig != last.get("modes"):
            last["modes"] = sig
            modes_list.controls.clear()
            for mode in state.modes:
                run_text = f"запущен на {mode['running_ip']}" if mode["running"] else "остановлен"
                error = f" · ошибка: {mode['last_error']}" if mode["last_error"] else ""
                name = mode["name"]
                modes_list.controls.append(card(ft.Row([
                    ft.Text(f"{name} — {run_text}{error}", expand=True),
                    ft.IconButton(ft.Icons.PLAY_ARROW, tooltip="Запуск", icon_color=ACCENT,
                                  on_click=guarded(lambda n=name: core.start_mode(n, mode_lamp.value))),
                    ft.IconButton(ft.Icons.STOP, tooltip="Стоп", icon_color=TEXT,
                                  on_click=guarded(lambda n=name: core.stop_mode(n))),
                    ft.IconButton(ft.Icons.DELETE, tooltip="Удалить", icon_color=DANGER,
                                  on_click=guarded(lambda n=name: core.delete_mode(n))),
                ])))
        if lamp_ips != last.get("mode_lamps"):
            last["mode_lamps"] = lamp_ips
            mode_lamp.options = [ft.DropdownOption(key=ip, text=ip) for ip in lamp_ips]

    modes_tab = ft.Column([ft.Row([mode_lamp]), modes_list], expand=True)

    # ---------- Настройка (Wi-Fi и LAN Control) ----------
    wifi_ip = field("IP лампы", width=220)
    ssid = field("Wi-Fi SSID", width=260)
    wifi_password = field("Пароль Wi-Fi", password=True, can_reveal_password=True, width=260)
    lan_check = ft.Checkbox(label="Включить LAN Control", value=True, active_color=ACCENT)
    lan_ip = field("IP лампы для LAN Control", width=220)
    token = field("Токен (необязательно)", width=260)

    def wifi_job():
        result = connect_to_wifi(wifi_ip.value.strip(), ssid.value, wifi_password.value,
                                 enable_lan_control=lan_check.value)
        core.log(f"Wi-Fi: {result}")
        return str(result)

    def lan_job():
        result = enable_lan_control(lan_ip.value.strip(), token.value.strip() or None)
        core.log(f"LAN Control: {result}")
        return str(result)

    settings_tab = ft.Column([
        ft.Text("Подключение лампы к Wi-Fi", weight=ft.FontWeight.BOLD),
        ft.Row([wifi_ip, ssid]),
        ft.Row([wifi_password, lan_check]),
        btn("Подключить к Wi-Fi", in_background(wifi_job), primary=True),
        ft.Divider(color=BORDER),
        ft.Text("LAN Control", weight=ft.FontWeight.BOLD),
        ft.Row([lan_ip, token]),
        btn("Включить LAN Control", in_background(lan_job), primary=True),
    ], scroll=ft.ScrollMode.AUTO)

    # ---------- Журнал ----------
    log_view = ft.ListView(expand=True, spacing=2, auto_scroll=True)

    def refresh_log(state):
        if state.log == last.get("log"):
            return
        last["log"] = list(state.log)
        log_view.controls = [ft.Text(line, selectable=True, color=MUTED) for line in state.log]

    logs_tab = ft.Column([card(log_view)], expand=True)

    tabs = ft.Tabs(
        selected_index=0,
        length=5,
        expand=True,
        content=ft.Column([
            ft.TabBar(tabs=[
                ft.Tab(label="Подключение"),
                ft.Tab(label="Лампы"),
                ft.Tab(label="Режимы"),
                ft.Tab(label="Настройка"),
                ft.Tab(label="Журнал"),
            ], label_color=ACCENT, unselected_label_color=MUTED, indicator_color=ACCENT,
               divider_color=BORDER),
            ft.TabBarView(expand=True, controls=[
                connection_tab, lamps_tab, modes_tab, settings_tab, logs_tab,
            ]),
        ], expand=True),
        on_change=lambda e: refresh_all(),
    )

    def refresh_all():
        sync_status.value = ("подключено" if syncer.connected else "нет связи") if syncer.running \
            else "отключено"
        state = core.state()
        refresh_lamps(state)
        refresh_modes(state)
        refresh_log(state)
        page.update()

    page.add(tabs, msg)

    def ticker():
        while True:
            time.sleep(1)
            try:
                refresh_all()
            except Exception:
                return

    page.run_thread(ticker)
    refresh_all()


def run():
    ft.run(main)
