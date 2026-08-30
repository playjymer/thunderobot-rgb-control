"""
System Tray Integration for Thunderobot RGB Control.
"""

import threading
import logging
from PIL import Image, ImageDraw
import pystray

logger = logging.getLogger(__name__)


def create_tray_image(rgb=(0, 255, 255)):
    size = (64, 64)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([4, 16, 60, 48], radius=8, fill=(30, 32, 40), outline=(60, 65, 80), width=2)
    
    r, g, b = rgb
    glow_color = (r, g, b, 230)
    
    draw.rounded_rectangle([10, 24, 22, 40], radius=3, fill=glow_color)
    draw.rounded_rectangle([26, 24, 38, 40], radius=3, fill=glow_color)
    draw.rounded_rectangle([42, 24, 54, 40], radius=3, fill=glow_color)
    
    return img


class TrayIcon:
    def __init__(self, app_callbacks):
        self.callbacks = app_callbacks
        self.icon = None
        self._thread = None

    def start(self):
        menu_items = [
            pystray.MenuItem("Показать панель управления", self._on_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Вкл / Выкл подсветку", self._on_toggle_power),
            pystray.MenuItem("🌈 Анимации", pystray.Menu(
                pystray.MenuItem("Радужная волна", lambda: self.callbacks["set_mode"]("Rainbow Wave")),
                pystray.MenuItem("Двухцветная волна", lambda: self.callbacks["set_mode"]("Dual-Color Wave")),
                pystray.MenuItem("Дыхание", lambda: self.callbacks["set_mode"]("Breathing")),
                pystray.MenuItem("Спектральный цикл", lambda: self.callbacks["set_mode"]("Spectrum Cycle")),
                pystray.MenuItem("Стробоскоп", lambda: self.callbacks["set_mode"]("Strobe / Flash")),
            )),
            pystray.MenuItem("🎵 Интерактив", pystray.Menu(
                pystray.MenuItem("Wallpaper Engine Sync", lambda: self.callbacks["set_mode"]("Wallpaper Engine Sync")),
                pystray.MenuItem("Музыкальный визуализатор", lambda: self.callbacks["set_mode"]("Audio Visualizer")),
                pystray.MenuItem("Спидометр печати (WPM)", lambda: self.callbacks["set_mode"]("WPM Typing Speed")),
                pystray.MenuItem("Реактивный ввод", lambda: self.callbacks["set_mode"]("Reactive Typing")),
                pystray.MenuItem("Эмбиент экрана", lambda: self.callbacks["set_mode"]("Ambient Screen")),
            )),
            pystray.MenuItem("🎮 Темы", pystray.Menu(
                pystray.MenuItem("Киберпанк", lambda: self.callbacks["set_mode"]("Cyberpunk Neon")),
                pystray.MenuItem("Живое пламя", lambda: self.callbacks["set_mode"]("Fire & Ember")),
                pystray.MenuItem("Матрица", lambda: self.callbacks["set_mode"]("Matrix Rain")),
                pystray.MenuItem("Полиция", lambda: self.callbacks["set_mode"]("Police Siren")),
            )),
            pystray.MenuItem("📊 Мониторы", pystray.Menu(
                pystray.MenuItem("Монитор CPU", lambda: self.callbacks["set_mode"]("CPU Temp Monitor")),
                pystray.MenuItem("Занятость RAM", lambda: self.callbacks["set_mode"]("RAM Usage Meter")),
                pystray.MenuItem("Индикатор батареи", lambda: self.callbacks["set_mode"]("Battery Gauge")),
                pystray.MenuItem("Таймер Pomodoro", lambda: self.callbacks["set_mode"]("Pomodoro Timer")),
            )),
            pystray.MenuItem("💡 Статичный цвет", lambda: self.callbacks["set_mode"]("Static")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Яркость", pystray.Menu(
                pystray.MenuItem("100%", lambda: self.callbacks["set_brightness"](255)),
                pystray.MenuItem("75%", lambda: self.callbacks["set_brightness"](191)),
                pystray.MenuItem("50%", lambda: self.callbacks["set_brightness"](128)),
                pystray.MenuItem("25%", lambda: self.callbacks["set_brightness"](64)),
                pystray.MenuItem("Выключить (0%)", lambda: self.callbacks["set_brightness"](0)),
            )),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self._on_exit),
        ]

        self.icon = pystray.Icon(
            "ThunderobotRGB",
            create_tray_image((0, 255, 255)),
            "Thunderobot 911s RGB Control Pro",
            pystray.Menu(*menu_items)
        )

        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()
        logger.info("System tray initialized.")

    def _on_show(self, icon, item):
        if "show_window" in self.callbacks:
            self.callbacks["show_window"]()

    def _on_toggle_power(self, icon, item):
        if "toggle_power" in self.callbacks:
            self.callbacks["toggle_power"]()

    def _on_exit(self, icon, item):
        if "exit_app" in self.callbacks:
            self.callbacks["exit_app"]()
        if self.icon:
            self.icon.stop()

    def update_icon_color(self, rgb):
        if self.icon:
            self.icon.icon = create_tray_image(rgb)

    def stop(self):
        if self.icon:
            self.icon.stop()
