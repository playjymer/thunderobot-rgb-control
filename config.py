"""
Configuration and Profile Management for Thunderobot RGB Control.
"""

import os
import json
import winreg
import sys
import logging

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.expanduser("~/.thunderobot_rgb.json")

HOTKEY_ACTIONS = [
    ("open_gui", "🚀 Открыть / Развернуть программу"),
    ("toggle_power", "💡 Вкл / Выкл подсветку"),
    ("brightness_up", "🔆 Увеличить яркость (+10%)"),
    ("brightness_down", "🔅 Уменьшить яркость (-10%)"),
    ("next_mode", "➡️ Следующий режим подсветки"),
    ("prev_mode", "⬅️ Предыдущий режим подсветки"),
    ("mode_wallpaper_engine", "🖼️ Wallpaper Engine Sync"),
    ("mode_rainbow", "🌈 Радужная волна"),
    ("mode_audio_vis", "🎵 Музыкальный визуализатор"),
    ("mode_wpm", "⌨️ Спидометр скорости печати"),
    ("mode_cyberpunk", "🌆 Киберпанк (Neon 2077)"),
    ("mode_fire", "🔥 Живое пламя (Fire & Ember)"),
    ("mode_matrix", "🟢 Матрица (Matrix Rain)"),
    ("mode_police", "🚨 Проблесковые маячки"),
    ("mode_static", "💡 Статичный цвет"),
]

DEFAULT_CONFIG = {
    "power": True,
    "mode": "Rainbow Wave",
    "active_category": "🌈 Анимации",
    "brightness": 255,
    "speed": 1.0,
    "zone_mode": "single",
    "channel_mapping": "BRG",
    "gain_r": 1.0,
    "gain_g": 1.0,
    "gain_b": 1.0,
    "color_single": [0, 255, 255],
    "color_left": [255, 0, 128],
    "color_middle": [0, 255, 255],
    "color_right": [120, 0, 255],
    "color_secondary": [255, 0, 80],
    "autostart": False,
    "minimize_to_tray": True,
    "close_to_tray": True,
    "timeout_mins": 0,
    "battery_saver": True,
    "night_shift": False,
    "smart_idle_dim": False,
    "fn_redirect": True,
    "notification_flash": True,
    "wallpaper_sync_enabled": True,
    "app_notif_colors": {
        "telegram": [0, 180, 255],
        "discord": [120, 80, 255],
        "steam": [30, 150, 255],
        "whatsapp": [37, 211, 102],
        "vk": [0, 119, 255],
        "browser": [255, 180, 0],
        "windows": [0, 220, 255],
    },
    "fn_hotkeys": {
        "num_slash": {"name": "Fn + / (Numpad)", "action": "open_gui", "label": "🚀 Открыть / Развернуть программу"},
        "num_multiply": {"name": "Fn + * (Numpad)", "action": "next_mode", "label": "➡️ Следующий режим подсветки"},
        "num_minus": {"name": "Fn + - (Numpad)", "action": "brightness_down", "label": "🔅 Уменьшить яркость (-10%)"},
        "num_plus": {"name": "Fn + + (Numpad)", "action": "brightness_up", "label": "🔆 Увеличить яркость (+10%)"},
        "custom_wp": {"name": "Ctrl + Shift + W", "action": "mode_wallpaper_engine", "label": "🖼️ Wallpaper Engine Sync"},
        "custom_aud": {"name": "Ctrl + Shift + A", "action": "mode_audio_vis", "label": "🎵 Музыкальный визуализатор"},
        "custom_pwr": {"name": "Ctrl + Shift + Space", "action": "toggle_power", "label": "💡 Вкл / Выкл подсветку"},
    },
    "profiles": {
        "Cyberpunk": {
            "mode": "Cyberpunk Neon",
            "speed": 1.2,
            "brightness": 255,
            "zone_mode": "single",
            "color_left": [255, 0, 128],
            "color_middle": [0, 255, 255],
            "color_right": [255, 220, 0],
            "color_single": [0, 255, 255],
            "color_secondary": [255, 0, 128]
        },
        "Fire & Ice": {
            "mode": "Fire & Ember",
            "speed": 0.8,
            "brightness": 255,
            "zone_mode": "single",
            "color_left": [255, 50, 0],
            "color_middle": [255, 150, 0],
            "color_right": [0, 200, 255],
            "color_single": [255, 80, 0],
            "color_secondary": [0, 200, 255]
        },
        "Matrix": {
            "mode": "Matrix Rain",
            "speed": 1.5,
            "brightness": 255,
            "zone_mode": "single",
            "color_left": [0, 255, 40],
            "color_middle": [0, 255, 40],
            "color_right": [0, 255, 40],
            "color_single": [0, 255, 40],
            "color_secondary": [0, 80, 20]
        },
        "Deep Purple": {
            "mode": "Breathing",
            "speed": 0.6,
            "brightness": 255,
            "zone_mode": "single",
            "color_left": [140, 0, 255],
            "color_middle": [140, 0, 255],
            "color_right": [140, 0, 255],
            "color_single": [140, 0, 255],
            "color_secondary": [30, 0, 80]
        }
    }
}


class ConfigManager:
    def __init__(self, path: str = CONFIG_PATH):
        self.path = path
        self.data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
                    if "profiles" in loaded:
                        self.data["profiles"] = {**DEFAULT_CONFIG["profiles"], **loaded["profiles"]}
                    if "app_notif_colors" in loaded:
                        self.data["app_notif_colors"] = {**DEFAULT_CONFIG["app_notif_colors"], **loaded["app_notif_colors"]}
                    if "fn_hotkeys" in loaded:
                        self.data["fn_hotkeys"] = {**DEFAULT_CONFIG["fn_hotkeys"], **loaded["fn_hotkeys"]}
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
        self._check_autostart_registry()
        if self.data.get("fn_redirect", True):
            self.set_fn_redirect(True)

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value, save_to_disk=True):
        self.data[key] = value
        if save_to_disk:
            self.save()

    def _check_autostart_registry(self):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, "ThunderobotRGBControl")
                self.data["autostart"] = True
            except FileNotFoundError:
                self.data["autostart"] = False
            winreg.CloseKey(key)
        except Exception:
            pass

    def set_autostart(self, enable: bool) -> bool:
        self.data["autostart"] = enable
        self.save()
        app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))
        python_exe = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(python_exe):
            python_exe = sys.executable
        cmd = f'"{python_exe}" "{app_path}" --minimized'

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE | winreg.KEY_READ
            )
            if enable:
                winreg.SetValueEx(key, "ThunderobotRGBControl", 0, winreg.REG_SZ, cmd)
                logger.info("Autostart registry entry added.")
            else:
                try:
                    winreg.DeleteValue(key, "ThunderobotRGBControl")
                    logger.info("Autostart registry entry removed.")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            return True
        except Exception as e:
            logger.error(f"Failed to update autostart registry: {e}")
            return False

    def set_fn_redirect(self, enable: bool):
        self.data["fn_redirect"] = enable
        self.save()
        app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))
        python_exe = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(python_exe):
            python_exe = sys.executable
        cmd = f'"{python_exe}" "{app_path}"'

        for proto in ["clevokeyboard", "clevocc30"]:
            try:
                base_path = f"Software\\Classes\\{proto}"
                if enable:
                    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{base_path}\\shell\\open\\command")
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd)
                    winreg.CloseKey(key)
                else:
                    try:
                        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{base_path}\\shell\\open\\command")
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Could not set registry for {proto}: {e}")

    def save_profile(self, name: str):
        if not name:
            return
        if "profiles" not in self.data:
            self.data["profiles"] = {}
        self.data["profiles"][name] = {
            "mode": self.data["mode"],
            "speed": self.data["speed"],
            "brightness": self.data["brightness"],
            "zone_mode": self.data["zone_mode"],
            "color_single": list(self.data["color_single"]),
            "color_left": list(self.data["color_left"]),
            "color_middle": list(self.data["color_middle"]),
            "color_right": list(self.data["color_right"]),
            "color_secondary": list(self.data["color_secondary"]),
        }
        self.save()

    def load_profile(self, name: str, persist: bool = False) -> bool:
        if "profiles" in self.data and name in self.data["profiles"]:
            prof = self.data["profiles"][name]
            self.data.update(prof)
            if persist:
                self.save()
            return True
        return False

    def delete_profile(self, name: str):
        if "profiles" in self.data and name in self.data["profiles"]:
            del self.data["profiles"][name]
            self.save()


config = ConfigManager()
