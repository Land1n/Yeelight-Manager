"""Окно Flet собирается без реального окна: карточки, ползунки, уведомления."""

import flet as ft
import pytest

import manager.app as app_module
from manager.core import Core
from manager.widgets import LampCard


class FakeLamp:
    """Лампа для интерфейсных тестов: состояние живёт в словаре."""

    def __init__(self, ip):
        self.ip = ip
        self.props = {"power": "on", "bright": 40, "ct": 2700, "rgb": 0x3366CC, "color_mode": 1,
                      "name": ""}

    def state(self):
        return dict(self.props)

    def turn_on(self):
        self.props["power"] = "on"

    def turn_off(self):
        self.props["power"] = "off"

    def toggle(self):
        self.props["power"] = "off" if self.props["power"] == "on" else "on"

    def set_brightness(self, value):
        self.props["bright"] = value

    def set_rgb(self, r, g, b):
        self.props["rgb"] = (r << 16) | (g << 8) | b

    def set_hex(self, value):
        self.props["rgb"] = int(value, 16)

    def set_color_temp(self, kelvin):
        self.props["ct"] = kelvin


class StubPage:
    """Минимум страницы Flet: сборка виджетов, фоновые задачи, уведомления."""

    def __init__(self):
        self.window = type("Window", (), {"width": 0, "height": 0})()
        self.controls = []
        self.threads = []
        self.toasts = []

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        pass

    def run_thread(self, target, *args):
        self.threads.append(target)

    def show_dialog(self, dialog):
        assert isinstance(dialog, ft.SnackBar)
        self.toasts.append(dialog.content.value)

    def run_jobs(self):
        for target in self.threads:
            if target.__name__ != "ticker":
                target()
        self.threads.clear()


@pytest.fixture
def ui(tmp_path, monkeypatch):
    monkeypatch.setattr("manager.core.PACE_SECONDS", 0)
    core = Core(data_dir=tmp_path, lamp_factory=FakeLamp, discover_fn=lambda timeout: [])
    core.add("10.0.0.1")
    monkeypatch.setattr(app_module, "Core", lambda: core)
    captured = {}

    class SpyCard(LampCard):
        def __init__(self, ip, run):
            captured["run"] = run
            super().__init__(ip, run)

    monkeypatch.setattr(app_module, "LampCard", SpyCard)
    page = StubPage()
    app_module.main(page)
    return page, core, captured["run"]


def test_window_builds_lamp_card(ui):
    page, core, _ = ui
    assert page.controls, "окно не собрало виджеты"
    assert len(core.state().lamps) == 1


def test_slider_command_reports_result(ui):
    page, core, run = ui
    run("яркость", {"type": "set_brightness", "ip": "10.0.0.1", "value": 90})
    page.run_jobs()
    assert any(text.startswith("→ яркость") for text in page.toasts)
    assert any("✓ яркость" in text and "set_brightness" in text for text in page.toasts)


def test_failed_action_notifies_error(ui):
    page, _, run = ui
    run("переключение", {"type": "toggle", "ip": "10.9.9.9"})
    page.run_jobs()
    assert any(text.startswith("✕") for text in page.toasts)


def test_card_sliders_send_commands():
    calls = []
    card = LampCard("10.0.0.1", lambda label, action: calls.append(action))
    card.update(type("L", (), {"props": {"bright": 30, "ct": 3000, "rgb": 0x102030},
                               "online": True})())
    card.channels["r"].value = 7
    card._end_rgb()
    card._end_temp()
    card._apply_hex()
    assert calls[0] == {"type": "set_rgb", "ip": "10.0.0.1", "r": 7, "g": 0x20, "b": 0x30}
    assert calls[1]["type"] == "set_color_temp"
    assert calls[2] == {"type": "set_hex", "ip": "10.0.0.1", "value": "ffffff"}
