"""Окно manager на Flet: лампы, режимы, настройка, журнал."""

from __future__ import annotations

import time

import flet as ft

from lamp.network import connect_to_wifi, enable_lan_control

from manager.core import Core
from manager.sync import Syncer
from manager.theme import (ACCENT, BORDER, DANGER, MUTED, MUTED_2, RADIUS, SURFACE_2, SURFACE_3,
                           TEXT, apply_theme, btn, card, caption, dot, field)
from manager.widgets import LampCard


def main(page: ft.Page):
    page.title = "Yeelight manager"
    page.window.width = 980
    page.window.height = 760
    page.padding = 12
    apply_theme(page)

    core = Core()
    core.start()
    syncer = Syncer(core)
    cards = {}
    last = {}
    busy = {"count": 0}

    # ---------- Индикаторы шапки и уведомления ----------
    head_dot = dot(MUTED)
    head_text = caption("менеджер запущен", MUTED, 12)
    lamps_count = caption("ламп: 0", MUTED, 12)
    busy_text = caption("ожидание", MUTED_2, 12)
    busy_ring = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ACCENT, visible=False)
    banner_text = ft.Text("готово", color=MUTED)
    banner = ft.Container(banner_text, padding=10, border_radius=RADIUS, bgcolor=SURFACE_2,
                          border=ft.Border.all(1, BORDER))
    header = ft.Row([head_dot, head_text, lamps_count, busy_text, busy_ring], spacing=12, wrap=True)

    def toast(text, ok=True):
        """Уведомление: строка внизу окна и всплывающее сообщение."""
        banner_text.value = text
        banner_text.color = ACCENT if ok else DANGER
        try:
            page.show_dialog(ft.SnackBar(ft.Text(text, color=TEXT), bgcolor=SURFACE_3,
                                         duration=3500))
        except Exception:
            pass
        page.update()

    def perform(action):
        kind, ip = action.get("type"), action.get("ip")
        if kind == "undo":
            return core.undo(ip)
        if kind == "remove":
            core.remove(ip)
            return f"лампа {ip} удалена"
        return core.command(action)

    def done(label, ip, message, ok):
        busy["count"] = max(0, busy["count"] - 1)
        busy_ring.visible = busy["count"] > 0
        busy_text.value = f"выполняется: {busy['count']}" if busy["count"] else "ожидание"
        if ip in cards:
            cards[ip].set_busy(False)
            cards[ip].report(f"{label}: {message}", ok)
        mark = "✓" if ok else "✕"
        toast(f"{mark} {label} · {ip}: {message}" if ip else f"{mark} {label}: {message}", ok)

    def submit(label, call, ip=None):
        """Фоновое действие: индикатор загрузки и уведомление о результате."""
        busy["count"] += 1
        busy_ring.visible = True
        busy_text.value = f"выполняется: {busy['count']}"
        if ip in cards:
            cards[ip].set_busy(True)
            cards[ip].report(f"→ {label}")
        toast(f"→ {label} · {ip}" if ip else f"→ {label}")
        page.run_thread(lambda: worker(label, call, ip))

    def worker(label, call, ip):
        try:
            done(label, ip, str(call() or "готово"), True)
        except Exception as ex:
            done(label, ip, str(ex), False)

    def run(label, action):
        submit(label, lambda: perform(action), action.get("ip"))

    # ---------- Подключение ----------
    server_url = field("Адрес сервера", value=core.config["server_url"], expand=True,
                       hint_text="http://127.0.0.1:8000")
    access_key = field("Ключ доступа", value=core.config["access_key"],
                       password=True, can_reveal_password=True, expand=True)
    sync_dot = dot(MUTED)
    sync_text = caption("отключено", MUTED, 12)

    def safe(fn):
        """Синхронный обработчик: ошибку показываем уведомлением, а не падением окна."""
        def handler(_=None):
            try:
                fn()
            except Exception as ex:
                toast(str(ex), ok=False)
        return handler

    def save_server():
        core.update_config(server_url=server_url.value.strip(),
                           access_key=access_key.value.strip())
        toast("настройки сервера сохранены")

    def toggle_sync():
        if syncer.running:
            syncer.stop()
            toast("синхронизация остановлена")
            return
        save_server()
        if not server_url.value.strip():
            toast("укажите адрес сервера, например http://127.0.0.1:8000", ok=False)
            return
        syncer.start()
        toast("синхронизация запущена")

    connection_tab = ft.Column([
        ft.Row([server_url]),
        ft.Row([access_key]),
        ft.Row([btn("Сохранить", safe(save_server), icon=ft.Icons.SAVE),
                btn("Запуск / стоп", safe(toggle_sync), primary=True, icon=ft.Icons.SYNC),
                sync_dot, sync_text]),
    ])

    # ---------- Лампы ----------
    lamps_list = ft.ListView(expand=True, spacing=10)
    add_ip = field("IP лампы", width=220)

    def refresh_lamps(state):
        lamps_count.value = (f"ламп: {len(state.lamps)} · в сети: "
                             f"{sum(1 for lamp in state.lamps if lamp.online)}")
        ips = [lamp.ip for lamp in state.lamps]
        if ips != last.get("ips"):
            last["ips"] = ips
            for ip in [ip for ip in cards if ip not in ips]:
                cards.pop(ip)
            lamps_list.controls.clear()
            for ip in ips:
                cards.setdefault(ip, LampCard(ip, run))
                lamps_list.controls.append(cards[ip].view)
        for lamp in state.lamps:
            cards[lamp.ip].update(lamp)

    def add_lamp():
        ip = (add_ip.value or "").strip()
        if not ip:
            toast("введите IP лампы", ok=False)
            return
        submit("добавление лампы", lambda: f"лампа {core.add(ip)} добавлена", ip)
        add_ip.value = ""

    def find_lamps():
        submit("поиск в сети", lambda: f"найдено: {len(core.discover())}")

    lamps_tab = ft.Column([
        ft.Row([add_ip, btn("Добавить", safe(add_lamp), primary=True),
                btn("Найти в сети", safe(find_lamps), icon=ft.Icons.SEARCH)]),
        lamps_list,
    ], expand=True)

    # ---------- Режимы ----------
    modes_list = ft.ListView(expand=True, spacing=6)
    mode_lamp = ft.Dropdown(label="Лампа", width=220, options=[], border_radius=RADIUS,
                            border_color=BORDER, bgcolor=SURFACE_2, filled=True)
    modes_ring = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ACCENT, visible=False)

    def refresh_modes(state):
        modes_ring.visible = any(mode["running"] for mode in state.modes)
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
                                  on_click=click(f"режим {name}",
                                                  lambda n=name: core.start_mode(n, mode_lamp.value))),
                    ft.IconButton(ft.Icons.STOP, tooltip="Стоп", icon_color=TEXT,
                                  on_click=click(f"стоп режима {name}",
                                                 lambda n=name: core.stop_mode(n))),
                    ft.IconButton(ft.Icons.DELETE, tooltip="Удалить", icon_color=DANGER,
                                  on_click=click(f"удаление режима {name}",
                                                 lambda n=name: core.delete_mode(n))),
                ])))
        if lamp_ips != last.get("mode_lamps"):
            last["mode_lamps"] = lamp_ips
            mode_lamp.options = [ft.DropdownOption(key=ip, text=ip) for ip in lamp_ips]

    def click(label, call):
        return lambda _=None: submit(label, call)

    modes_tab = ft.Column([ft.Row([mode_lamp, modes_ring]), modes_list], expand=True)

    # ---------- Настройка (Wi-Fi и LAN Control) ----------
    wifi_ip = field("IP лампы", width=220)
    ssid = field("Wi-Fi SSID", width=260)
    wifi_password = field("Пароль Wi-Fi", password=True, can_reveal_password=True, width=260)
    lan_check = ft.Checkbox(label="Включить LAN Control", value=True, active_color=ACCENT)
    lan_ip = field("IP лампы для LAN Control", width=220)
    token = field("Токен (необязательно)", width=260)

    def wifi_job():
        result = connect_to_wifi((wifi_ip.value or "").strip(), ssid.value or "",
                                 wifi_password.value or "",
                                 enable_lan_control=lan_check.value)
        core.log(f"Wi-Fi: {result}")
        return str(result)

    def lan_job():
        result = enable_lan_control((lan_ip.value or "").strip(), (token.value or "").strip() or None)
        core.log(f"LAN Control: {result}")
        return str(result)

    settings_tab = ft.Column([
        ft.Text("Подключение лампы к Wi-Fi", weight=ft.FontWeight.BOLD),
        ft.Row([wifi_ip, ssid]),
        ft.Row([wifi_password, lan_check]),
        btn("Подключить к Wi-Fi", click("Wi-Fi", wifi_job), primary=True),
        ft.Divider(color=BORDER),
        ft.Text("LAN Control", weight=ft.FontWeight.BOLD),
        ft.Row([lan_ip, token]),
        btn("Включить LAN Control", click("LAN Control", lan_job), primary=True),
    ], scroll=ft.ScrollMode.AUTO)

    # ---------- Журнал ----------
    log_view = ft.ListView(expand=True, spacing=2, auto_scroll=True)

    def refresh_log(state):
        if state.log == last.get("log"):
            return
        last["log"] = list(state.log)
        log_view.controls = [ft.Text(line, selectable=True, color=MUTED, size=12)
                             for line in state.log]

    logs_tab = ft.Column([caption("события ядра", MUTED_2, 11), card(log_view, expand=True)],
                         expand=True)

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
    )

    def refresh_all():
        connected = syncer.running and syncer.connected
        sync_dot.bgcolor = ACCENT if connected else (DANGER if syncer.running else MUTED)
        sync_text.value = ("подключено" if connected
                           else "нет связи" if syncer.running else "отключено")
        state = core.state()
        refresh_lamps(state)
        refresh_modes(state)
        refresh_log(state)
        page.update()

    page.add(header, tabs, banner)

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
