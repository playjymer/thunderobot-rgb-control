"""
Lighting Effects Engine for Thunderobot RGB Keyboard.
Features:
- Wallpaper Engine Sync (Razer Chroma REST Server + Live Desktop Capture)
- Fn Key Action Dispatcher (Next/Prev Mode, Brightness +/-, Power toggle, Direct Mode switch)
- Buttery-Smooth Temporal Anti-Aliasing & Fluid Notification Waves
"""

import time
import math
import colorsys
import threading
import logging
import random
import psutil
import ctypes
from ctypes import wintypes
from datetime import datetime
from PIL import ImageGrab

from driver import driver, ZONE_ALL, ZONE_LEFT, ZONE_MIDDLE, ZONE_RIGHT
from wallpaper_sync import wallpaper_sync

logger = logging.getLogger(__name__)

# Pynput for reactive keypress & WPM tracking & Idle detection
try:
    from pynput import keyboard as pk_keyboard, mouse as pk_mouse
    PYNPUT_AVAILABLE = True
except Exception:
    PYNPUT_AVAILABLE = False

# Pycaw for WASAPI audio meter
try:
    from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
    from comtypes import CLSCTX_ALL
    PYCAW_AVAILABLE = True
except Exception:
    PYCAW_AVAILABLE = False


def clamp(val, low=0, high=255):
    return max(low, min(high, int(val)))


def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, float(t)))
    return (
        clamp(c1[0] + (c2[0] - c1[0]) * t),
        clamp(c1[1] + (c2[1] - c1[1]) * t),
        clamp(c1[2] + (c2[2] - c1[2]) * t),
    )


def apply_brightness(rgb, brightness_0_to_255):
    factor = brightness_0_to_255 / 255.0
    return (
        clamp(rgb[0] * factor),
        clamp(rgb[1] * factor),
        clamp(rgb[2] * factor),
    )


DEFAULT_APP_NOTIFICATION_COLORS = {
    "telegram": (0, 180, 255),
    "discord": (120, 80, 255),
    "steam": (30, 150, 255),
    "whatsapp": (37, 211, 102),
    "vk": (0, 119, 255),
    "browser": (255, 180, 0),
    "windows": (0, 220, 255),
}

MODE_CATEGORIES = {
    "🌈 Анимации": [
        ("Rainbow Wave", "🌈 Радужная волна", "Плавная радужная волна, переливающаяся по всему спектру 16.8M цветов."),
        ("Dual-Color Wave", "🌊 Двухцветная волна", "Мягкий градиентный перелив между основным и дополнительным цветом."),
        ("Breathing", "💨 Дыхание", "Эффект плавной пульсации на выбранном цвете или между двумя оттенками."),
        ("Spectrum Cycle", "🔄 Спектральный цикл", "Синхронная плавная смена всех оттенков радужного спектра."),
        ("Strobe / Flash", "⚡ Стробоскоп", "Энергичные импульсные вспышки с регулируемой частотой."),
    ],
    "🎵 Интерактив": [
        ("Wallpaper Engine Sync", "🖼️ Wallpaper Engine Sync", "Синхронизация подсветки клавиатуры с динамическими обоями Wallpaper Engine (Chroma SDK / Live Desktop)."),
        ("Audio Visualizer", "🎵 Музыкальный визуализатор", "Клавиатура вспыхивает и пульсирует в такт басам и звуку из Windows (WASAPI)."),
        ("WPM Typing Speed", "⌨️ Спидометр скорости печати", "Цвет плавно разгоняется от синего до огненно-красного по скорости набора (WPM)."),
        ("Reactive Typing", "✨ Реактивный ввод", "Клавиатура вспыхивает ярким цветом при каждом нажатии клавиши и плавно гаснет."),
        ("Ambient Screen", "🖥️ Эмбиент экрана", "Анализирует изображение на мониторе и проецирует преобладающие цвета на клавиатуру."),
    ],
    "🎮 Темы": [
        ("Cyberpunk Neon", "🌆 Киберпанк", "Атмосферный неоновый градиент в стиле Cyberpunk 2077 (Hot Pink / Cyan / Gold)."),
        ("Fire & Ember", "🔥 Живое пламя", "Мерцающие и пульсирующие языки пламени костра (Огненно-красный / Оранжевый / Золотой)."),
        ("Matrix Rain", "🟢 Матрица", "Культовый зеленый цифровой дождь в стиле Матрицы."),
        ("Police Siren", "🚨 Проблесковые маячки", "Динамическая сине-красная сирена спецслужб."),
    ],
    "📊 Мониторы": [
        ("CPU Temp Monitor", "🔥 Монитор CPU", "Цвет отражает температуру и нагрузку процессора (Зеленый → Желтый → Оранжевый → Красный)."),
        ("RAM Usage Meter", "🧠 Занятость ОЗУ (RAM)", "Цвет показывает объем занятой оперативной памяти: Мятный (<50%) → Синий → Янтарный → Красный."),
        ("Battery Gauge", "🔋 Индикатор батареи", "Цвет показывает заряд: Зеленый (>70%) → Желтый → Оранжевый → Мигающий красный (<15%)."),
        ("Pomodoro Timer", "⏱️ Таймер Pomodoro", "25 минут продуктивного фокуса (голубой) + 5 минут золотистого отдыха."),
    ],
    "💡 Статика": [
        ("Static", "💡 Статичный цвет", "Постоянное свечение заданным цветом из палитры 16.8 млн оттенков."),
    ]
}


class LightingEngine:
    EFFECT_MODES = [item[0] for cat in MODE_CATEGORIES.values() for item in cat]

    def __init__(self):
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        # Core Parameters
        self.mode = "Rainbow Wave"
        self.power = True
        self.brightness = 255
        self.speed = 1.0
        self.zone_mode = "single"
        self.color_single = (0, 255, 255)
        self.color_left = (255, 0, 128)
        self.color_middle = (0, 255, 255)
        self.color_right = (120, 0, 255)
        self.color_secondary = (255, 0, 80)

        # Smart features
        self.battery_saver = False
        self.night_shift = False
        self.smart_idle_dim = False
        self.temp_alert = False
        self.notification_flash_enabled = True

        # App-specific notification colors
        self.app_notif_colors = dict(DEFAULT_APP_NOTIFICATION_COLORS)

        # Fluid Notification state
        self._notification_duration = 1.8
        self._notification_until = 0.0
        self._notification_start = 0.0
        self._notification_color = (0, 180, 255)
        self._last_notif_app = ""
        self._last_notif_time = 0.0

        # Temporal smoothing state (50 FPS glide)
        self._smooth_left = [0.0, 0.0, 0.0]
        self._smooth_mid = [0.0, 0.0, 0.0]
        self._smooth_right = [0.0, 0.0, 0.0]

        # Output state
        self.current_left = (0, 0, 0)
        self.current_middle = (0, 0, 0)
        self.current_right = (0, 0, 0)

        # Reactive & WPM Tracker & Idle
        self._key_energy = 0.0
        self._key_zone_focus = 1
        self._keystroke_times = []
        self._current_wpm = 0.0
        self._last_user_activity = time.time()
        self._key_listener = None
        self._mouse_listener = None
        if PYNPUT_AVAILABLE:
            self._start_listeners()

        # Audio Meter state
        self._audio_meter = None
        self._audio_level = 0.0
        if PYCAW_AVAILABLE:
            self._init_audio_meter()

        # Hardware Caches
        self._last_cpu_percent = 0
        self._last_ram_percent = 0
        self._last_cpu_poll = 0
        self._last_battery_poll = 0
        self._battery_info = None

        # Ambient Screen Cache
        self._ambient_cache = [(0, 0, 0), (0, 0, 0), (0, 0, 0)]
        self._last_ambient_grab = 0

        # Pomodoro Timer state
        self._pomodoro_start = time.time()

        self.on_frame_rendered = None
        self.on_mode_changed_externally = None
        self.on_gui_requested = None

        # Start background watchers
        self._start_notification_watchers()

    def start(self):
        if self._running:
            return
        self._running = True
        wallpaper_sync.start()
        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()
        logger.info("Lighting engine started.")

    def stop(self):
        self._running = False
        wallpaper_sync.stop()
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info("Lighting engine stopped.")

    def update_params(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)

    def execute_action(self, action: str):
        """Executes a hotkey action (Next mode, Brightness +/-, Toggle Power, etc.)."""
        logger.info(f"Executing action: {action}")
        
        if action == "open_gui":
            if self.on_gui_requested:
                self.on_gui_requested()
        elif action == "toggle_power":
            new_pwr = not self.power
            self.update_params(power=new_pwr)
            driver.set_power(new_pwr)
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()
        elif action == "brightness_up":
            new_b = min(255, self.brightness + 26)
            self.update_params(brightness=new_b)
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()
        elif action == "brightness_down":
            new_b = max(0, self.brightness - 26)
            self.update_params(brightness=new_b)
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()
        elif action == "next_mode":
            try:
                curr_idx = self.EFFECT_MODES.index(self.mode)
                next_m = self.EFFECT_MODES[(curr_idx + 1) % len(self.EFFECT_MODES)]
            except ValueError:
                next_m = self.EFFECT_MODES[0]
            self.update_params(mode=next_m)
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()
        elif action == "prev_mode":
            try:
                curr_idx = self.EFFECT_MODES.index(self.mode)
                prev_m = self.EFFECT_MODES[(curr_idx - 1) % len(self.EFFECT_MODES)]
            except ValueError:
                prev_m = self.EFFECT_MODES[-1]
            self.update_params(mode=prev_m)
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()
        elif action == "mode_wallpaper_engine":
            self.update_params(mode="Wallpaper Engine Sync")
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()
        elif action == "mode_rainbow":
            self.update_params(mode="Rainbow Wave")
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()
        elif action == "mode_audio_vis":
            self.update_params(mode="Audio Visualizer")
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()
        elif action == "mode_wpm":
            self.update_params(mode="WPM Typing Speed")
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()
        elif action == "mode_cyberpunk":
            self.update_params(mode="Cyberpunk Neon")
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()
        elif action == "mode_fire":
            self.update_params(mode="Fire & Ember")
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()
        elif action == "mode_matrix":
            self.update_params(mode="Matrix Rain")
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()
        elif action == "mode_police":
            self.update_params(mode="Police Siren")
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()
        elif action == "mode_static":
            self.update_params(mode="Static")
            if self.on_mode_changed_externally:
                self.on_mode_changed_externally()

    def trigger_notification_flash(self, app_name="telegram", color=None, duration=1.8):
        now = time.time()
        with self._lock:
            if app_name == self._last_notif_app and (now - self._last_notif_time < 0.8):
                return
            self._last_notif_app = app_name
            self._last_notif_time = now

            if color:
                notif_c = color
            else:
                app_key = app_name.lower()
                matched_key = "windows"
                for k in ["telegram", "discord", "steam", "whatsapp", "vk", "browser"]:
                    if k in app_key:
                        matched_key = k
                        break
                notif_c = self.app_notif_colors.get(matched_key, (0, 180, 255))

            self._notification_color = notif_c
            self._notification_duration = duration
            self._notification_start = now
            self._notification_until = now + duration
            logger.info(f"Smooth notification wave triggered for {app_name}: {notif_c}")

    def _start_notification_watchers(self):
        def window_titles_watcher():
            user32 = ctypes.windll.user32
            user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            user32.OpenInputDesktop.restype = wintypes.HANDLE
            user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
            user32.SetThreadDesktop.restype = wintypes.BOOL

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumDesktopWindows.argtypes = [wintypes.HANDLE, WNDENUMPROC, wintypes.LPARAM]
            user32.EnumDesktopWindows.restype = wintypes.BOOL

            hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)

            last_titles = {}
            first_run = True

            while True:
                time.sleep(0.12)
                if not self.notification_flash_enabled or not self.power:
                    continue

                try:
                    current_titles = {}

                    def enum_cb(hwnd, lparam):
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        if pid.value:
                            try:
                                pname = psutil.Process(pid.value).name().lower()
                                for app in ["telegram", "discord", "steam", "whatsapp", "vk"]:
                                    if app in pname:
                                        buf = ctypes.create_unicode_buffer(512)
                                        user32.GetWindowTextW(hwnd, buf, 512)
                                        txt = buf.value.strip()
                                        if txt:
                                            current_titles[hwnd] = (app, txt)
                                        break
                            except Exception:
                                pass
                        return True

                    cb = WNDENUMPROC(enum_cb)
                    user32.EnumDesktopWindows(hdesk, cb, 0)

                    if not first_run:
                        for hwnd, (app, title) in current_titles.items():
                            old_info = last_titles.get(hwnd)
                            if old_info:
                                old_app, old_title = old_info
                                if title != old_title:
                                    if not any(skip in title.lower() for skip in ["default ime", "input trap", "dde server"]):
                                        self.trigger_notification_flash(app_name=app)
                            else:
                                if not any(skip in title.lower() for skip in ["default ime", "input trap", "dde server"]):
                                    self.trigger_notification_flash(app_name=app)

                    last_titles = current_titles
                    first_run = False
                except Exception as e:
                    pass

        t_win = threading.Thread(target=window_titles_watcher, daemon=True)
        t_win.start()

        def audio_session_monitor():
            ole32 = ctypes.windll.ole32
            ole32.CoInitialize(None)
            target_apps = ["telegram", "discord", "steam", "whatsapp", "vk"]
            while True:
                time.sleep(0.08)
                if not self.notification_flash_enabled or not self.power or not PYCAW_AVAILABLE:
                    continue
                try:
                    sessions = AudioUtilities.GetAllSessions()
                    for s in sessions:
                        if not s.Process:
                            continue
                        try:
                            pname = s.Process.name().lower()
                            for app in target_apps:
                                if app in pname:
                                    meter = s._ctl.QueryInterface(IAudioMeterInformation)
                                    if meter.GetPeakValue() > 0.002:
                                        self.trigger_notification_flash(app_name=app)
                                        break
                        except Exception:
                            pass
                except Exception:
                    pass

        t_aud = threading.Thread(target=audio_session_monitor, daemon=True)
        t_aud.start()

    def _init_audio_meter(self):
        try:
            device = AudioUtilities.GetSpeakers()
            if device and hasattr(device, "_dev"):
                interface = device._dev.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
                self._audio_meter = interface.QueryInterface(IAudioMeterInformation)
        except Exception as e:
            logger.warning(f"Could not initialize WASAPI audio meter: {e}")

    def _start_listeners(self):
        try:
            # Track modifiers
            active_mods = set()

            def on_press(key):
                now = time.time()
                with self._lock:
                    self._key_energy = 1.0
                    self._key_zone_focus = random.choice([0, 1, 2])
                    self._keystroke_times.append(now)
                    self._last_user_activity = now

                # Catch hotkey combos
                from config import config
                hotkeys = config.get("fn_hotkeys", {})

                # Check modifier keys
                if key in (pk_keyboard.Key.ctrl, pk_keyboard.Key.ctrl_l, pk_keyboard.Key.ctrl_r):
                    active_mods.add("ctrl")
                elif key in (pk_keyboard.Key.shift, pk_keyboard.Key.shift_l, pk_keyboard.Key.shift_r):
                    active_mods.add("shift")
                elif key in (pk_keyboard.Key.alt, pk_keyboard.Key.alt_l, pk_keyboard.Key.alt_r):
                    active_mods.add("alt")

                # Check Numpad keys
                if hasattr(key, "char") and key.char is not None:
                    ch = key.char
                    if ch == "*":
                        act = hotkeys.get("num_multiply", {}).get("action")
                        if act: self.execute_action(act)
                    elif ch == "-":
                        act = hotkeys.get("num_minus", {}).get("action")
                        if act: self.execute_action(act)
                    elif ch == "+":
                        act = hotkeys.get("num_plus", {}).get("action")
                        if act: self.execute_action(act)
                    elif ch.lower() == "w" and "ctrl" in active_mods and "shift" in active_mods:
                        act = hotkeys.get("custom_wp", {}).get("action")
                        if act: self.execute_action(act)
                    elif ch.lower() == "a" and "ctrl" in active_mods and "shift" in active_mods:
                        act = hotkeys.get("custom_aud", {}).get("action")
                        if act: self.execute_action(act)

                elif key == pk_keyboard.Key.space and "ctrl" in active_mods and "shift" in active_mods:
                    act = hotkeys.get("custom_pwr", {}).get("action")
                    if act: self.execute_action(act)

            def on_release(key):
                if key in (pk_keyboard.Key.ctrl, pk_keyboard.Key.ctrl_l, pk_keyboard.Key.ctrl_r):
                    active_mods.discard("ctrl")
                elif key in (pk_keyboard.Key.shift, pk_keyboard.Key.shift_l, pk_keyboard.Key.shift_r):
                    active_mods.discard("shift")
                elif key in (pk_keyboard.Key.alt, pk_keyboard.Key.alt_l, pk_keyboard.Key.alt_r):
                    active_mods.discard("alt")

            def on_move(x, y):
                self._last_user_activity = time.time()

            self._key_listener = pk_keyboard.Listener(on_press=on_press, on_release=on_release)
            self._key_listener.daemon = True
            self._key_listener.start()

            self._mouse_listener = pk_mouse.Listener(on_move=on_move, on_click=lambda x,y,b,d: on_move(x,y))
            self._mouse_listener.daemon = True
            self._mouse_listener.start()
        except Exception as e:
            logger.warning(f"Could not start keyboard/mouse listeners: {e}")

    def _update_wpm(self, now: float):
        cutoff = now - 5.0
        self._keystroke_times = [t for t in self._keystroke_times if t > cutoff]
        count = len(self._keystroke_times)
        raw_wpm = (count / 5.0) * 12.0
        self._current_wpm = self._current_wpm * 0.85 + raw_wpm * 0.15

    def _poll_audio(self):
        if not self._audio_meter:
            return 0.0
        try:
            val = self._audio_meter.GetPeakValue()
            if val > self._audio_level:
                self._audio_level = val
            else:
                self._audio_level = self._audio_level * 0.80 + val * 0.20
            return self._audio_level
        except Exception:
            return 0.0

    def _render_loop(self):
        start_time = time.time()
        fps = 50
        frame_delay = 1.0 / fps

        last_sent_left = (-1, -1, -1)
        last_sent_mid = (-1, -1, -1)
        last_sent_right = (-1, -1, -1)

        while self._running:
            frame_start = time.time()
            t = (frame_start - start_time)

            self._update_wpm(frame_start)

            with self._lock:
                effective_bright = self.brightness
                
                is_notification = (frame_start < self._notification_until)

                if not is_notification and self.smart_idle_dim and (frame_start - self._last_user_activity > 45.0):
                    effective_bright = min(effective_bright, 35)

                if self.battery_saver:
                    if frame_start - self._last_battery_poll > 2.0:
                        self._last_battery_poll = frame_start
                        self._battery_info = psutil.sensors_battery()
                    if self._battery_info and not self._battery_info.power_plugged:
                        effective_bright = min(effective_bright, 75)

                is_night = False
                if self.night_shift and not is_notification:
                    hour = datetime.now().hour
                    is_night = (hour >= 22 or hour < 7)

                if not self.power or effective_bright == 0:
                    raw_left, raw_mid, raw_right = (0, 0, 0), (0, 0, 0), (0, 0, 0)
                else:
                    raw_left, raw_mid, raw_right = self._compute_frame(t, effective_bright)

                    if is_night:
                        raw_left = lerp_color(raw_left, (255, 120, 30), 0.5)
                        raw_mid = lerp_color(raw_mid, (255, 120, 30), 0.5)
                        raw_right = lerp_color(raw_right, (255, 120, 30), 0.5)

                    # Fluid Notification Wave Overlay
                    if is_notification:
                        elapsed_n = frame_start - self._notification_start
                        dur = max(0.2, self._notification_duration)
                        progress = max(0.0, min(1.0, elapsed_n / dur))
                        
                        envelope = math.sin(progress * math.pi)
                        wave = 0.5 + 0.5 * math.sin(progress * math.pi * 4.0 - math.pi / 2.0)
                        blend_factor = (envelope ** 1.3) * (0.35 + 0.65 * wave)
                        blend_factor = max(0.0, min(1.0, blend_factor))

                        flash_b = int(effective_bright + (255 - effective_bright) * (envelope * 0.7))
                        notif_colored = apply_brightness(self._notification_color, flash_b)
                        
                        raw_left = lerp_color(raw_left, notif_colored, blend_factor)
                        raw_mid = lerp_color(raw_mid, notif_colored, blend_factor)
                        raw_right = lerp_color(raw_right, notif_colored, blend_factor)

                # Temporal anti-aliasing (50 FPS smooth glide)
                alpha = 0.38
                for idx in range(3):
                    self._smooth_left[idx] += (raw_left[idx] - self._smooth_left[idx]) * alpha
                    self._smooth_mid[idx] += (raw_mid[idx] - self._smooth_mid[idx]) * alpha
                    self._smooth_right[idx] += (raw_right[idx] - self._smooth_right[idx]) * alpha

                final_left = (int(round(self._smooth_left[0])), int(round(self._smooth_left[1])), int(round(self._smooth_left[2])))
                final_mid = (int(round(self._smooth_mid[0])), int(round(self._smooth_mid[1])), int(round(self._smooth_mid[2])))
                final_right = (int(round(self._smooth_right[0])), int(round(self._smooth_right[1])), int(round(self._smooth_right[2])))

                self.current_left = final_left
                self.current_middle = final_mid
                self.current_right = final_right

            # Send to hardware
            if (final_left != last_sent_left or final_mid != last_sent_mid or final_right != last_sent_right):
                if self.zone_mode == "single" or final_left == final_mid == final_right:
                    driver.set_color(final_mid[0], final_mid[1], final_mid[2], ZONE_ALL)
                else:
                    driver.set_zones(final_left, final_mid, final_right)
                last_sent_left, last_sent_mid, last_sent_right = final_left, final_mid, final_right

            if self.on_frame_rendered:
                try:
                    self.on_frame_rendered(final_left, final_mid, final_right)
                except Exception:
                    pass

            elapsed = time.time() - frame_start
            sleep_time = max(0.003, frame_delay - elapsed)
            time.sleep(sleep_time)

    def _compute_frame(self, t: float, bright: int):
        mode = self.mode
        speed = max(0.05, float(self.speed))
        is_single = (self.zone_mode == "single")

        if mode == "Wallpaper Engine Sync":
            l_col, m_col, r_col = wallpaper_sync.get_colors(is_single=is_single)
            return apply_brightness(l_col, bright), apply_brightness(m_col, bright), apply_brightness(r_col, bright)

        elif mode == "Static":
            if not is_single:
                l = apply_brightness(self.color_left, bright)
                m = apply_brightness(self.color_middle, bright)
                r = apply_brightness(self.color_right, bright)
            else:
                l = m = r = apply_brightness(self.color_single, bright)
            return l, m, r

        elif mode == "Rainbow Wave":
            if is_single:
                h = (t * speed * 0.25) % 1.0
                rgb = [int(c * 255) for c in colorsys.hsv_to_rgb(h, 1.0, 1.0)]
                col = apply_brightness(rgb, bright)
                return col, col, col
            else:
                h0 = (t * speed * 0.35) % 1.0
                h1 = (t * speed * 0.35 + 0.33) % 1.0
                h2 = (t * speed * 0.35 + 0.66) % 1.0
                rgb0 = [int(c * 255) for c in colorsys.hsv_to_rgb(h0, 1.0, 1.0)]
                rgb1 = [int(c * 255) for c in colorsys.hsv_to_rgb(h1, 1.0, 1.0)]
                rgb2 = [int(c * 255) for c in colorsys.hsv_to_rgb(h2, 1.0, 1.0)]
                return apply_brightness(rgb0, bright), apply_brightness(rgb1, bright), apply_brightness(rgb2, bright)

        elif mode == "Dual-Color Wave":
            wave = (math.sin(t * speed * 2.0) + 1.0) / 2.0
            if is_single:
                col = lerp_color(self.color_single, self.color_secondary, wave)
                c = apply_brightness(col, bright)
                return c, c, c
            else:
                w_l = (math.sin(t * speed * 2.0) + 1.0) / 2.0
                w_m = (math.sin(t * speed * 2.0 + 1.0) + 1.0) / 2.0
                w_r = (math.sin(t * speed * 2.0 + 2.0) + 1.0) / 2.0
                l = lerp_color(self.color_single, self.color_secondary, w_l)
                m = lerp_color(self.color_single, self.color_secondary, w_m)
                r = lerp_color(self.color_single, self.color_secondary, w_r)
                return apply_brightness(l, bright), apply_brightness(m, bright), apply_brightness(r, bright)

        elif mode == "Breathing":
            sine_val = (math.sin(t * speed * math.pi * 1.5) + 1.0) / 2.0
            effective_bright = bright * (0.05 + 0.95 * sine_val)

            if not is_single:
                l = apply_brightness(self.color_left, effective_bright)
                m = apply_brightness(self.color_middle, effective_bright)
                r = apply_brightness(self.color_right, effective_bright)
            else:
                col = lerp_color(self.color_secondary, self.color_single, sine_val)
                l = m = r = apply_brightness(col, effective_bright)
            return l, m, r

        elif mode == "Spectrum Cycle":
            h = (t * speed * 0.2) % 1.0
            rgb = [int(c * 255) for c in colorsys.hsv_to_rgb(h, 1.0, 1.0)]
            col = apply_brightness(rgb, bright)
            return col, col, col

        elif mode == "Audio Visualizer":
            audio_peak = self._poll_audio()
            audio_power = min(1.0, audio_peak * 2.2)
            
            hue = (t * speed * 0.1 + audio_power * 0.4) % 1.0
            base_rgb = [int(c * 255) for c in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]
            
            eff_b = bright * (0.10 + 0.90 * audio_power)
            col = apply_brightness(base_rgb, eff_b)
            
            if is_single:
                return col, col, col
            else:
                l_b = bright * (0.10 + 0.90 * (audio_power if audio_power > 0.3 else audio_power * 0.4))
                m_b = bright * (0.10 + 0.90 * audio_power)
                r_b = bright * (0.10 + 0.90 * (audio_power if audio_power > 0.6 else audio_power * 0.2))
                return apply_brightness(base_rgb, l_b), apply_brightness(base_rgb, m_b), apply_brightness(base_rgb, r_b)

        elif mode == "WPM Typing Speed":
            wpm = self._current_wpm
            if wpm < 25:
                t_wpm = wpm / 25.0
                col = lerp_color((0, 180, 255), (0, 255, 120), t_wpm)
            elif wpm < 60:
                t_wpm = (wpm - 25.0) / 35.0
                col = lerp_color((0, 255, 120), (255, 0, 180), t_wpm)
            else:
                t_wpm = min(1.0, (wpm - 60.0) / 40.0)
                col = lerp_color((255, 0, 180), (255, 20, 0), t_wpm)
                
            c = apply_brightness(col, bright)
            return c, c, c

        elif mode == "RAM Usage Meter":
            now = time.time()
            if now - self._last_cpu_poll > 1.0:
                self._last_cpu_poll = now
                self._last_ram_percent = psutil.virtual_memory().percent

            ram = self._last_ram_percent / 100.0
            if ram < 0.50:
                col = lerp_color((0, 255, 150), (0, 200, 255), ram / 0.50)
            elif ram < 0.80:
                col = lerp_color((0, 200, 255), (255, 180, 0), (ram - 0.50) / 0.30)
            else:
                col = lerp_color((255, 180, 0), (255, 0, 50), (ram - 0.80) / 0.20)

            c = apply_brightness(col, bright)
            return c, c, c

        elif mode == "Battery Gauge":
            now = time.time()
            if now - self._last_battery_poll > 2.0:
                self._last_battery_poll = now
                self._battery_info = psutil.sensors_battery()

            pct = 100
            plugged = True
            if self._battery_info:
                pct = self._battery_info.percent
                plugged = self._battery_info.power_plugged

            if pct > 70:
                col = (0, 255, 60)
            elif pct > 40:
                col = (255, 200, 0)
            elif pct > 15:
                col = (255, 80, 0)
            else:
                flash = (math.sin(t * 8.0) > 0)
                col = (255, 0, 0) if flash else (50, 0, 0)

            if plugged:
                charging_pulse = 0.8 + 0.2 * math.sin(t * 4.0)
                c = apply_brightness(col, bright * charging_pulse)
            else:
                c = apply_brightness(col, bright)
            return c, c, c

        elif mode == "Reactive Typing":
            self._key_energy = max(0.0, self._key_energy * 0.88 - 0.01)
            e = self._key_energy

            flash_col = self.color_single
            base_col = self.color_secondary

            if not is_single:
                z = self._key_zone_focus
                l_col = lerp_color(self.color_left, (255, 255, 255), e) if z == 0 else self.color_left
                m_col = lerp_color(self.color_middle, (255, 255, 255), e) if z == 1 else self.color_middle
                r_col = lerp_color(self.color_right, (255, 255, 255), e) if z == 2 else self.color_right
                
                l_b = bright * (0.15 + 0.85 * (e if z == 0 else e * 0.3))
                m_b = bright * (0.15 + 0.85 * (e if z == 1 else e * 0.3))
                r_b = bright * (0.15 + 0.85 * (e if z == 2 else e * 0.3))
                return apply_brightness(l_col, l_b), apply_brightness(m_col, m_b), apply_brightness(r_col, r_b)
            else:
                col = lerp_color(base_col, flash_col, e)
                eff_b = bright * (0.15 + 0.85 * e)
                c = apply_brightness(col, eff_b)
                return c, c, c

        elif mode == "CPU Temp Monitor":
            now = time.time()
            if now - self._last_cpu_poll > 0.8:
                self._last_cpu_poll = now
                self._last_cpu_percent = psutil.cpu_percent(interval=None)

            usage = self._last_cpu_percent / 100.0

            if self.temp_alert and usage > 0.92:
                flash = (math.sin(t * 10.0) > 0)
                col = (255, 0, 0) if flash else (120, 0, 0)
                c = apply_brightness(col, bright)
                return c, c, c

            if usage < 0.35:
                t_sub = usage / 0.35
                col = lerp_color((0, 255, 100), (255, 220, 0), t_sub)
            elif usage < 0.70:
                t_sub = (usage - 0.35) / 0.35
                col = lerp_color((255, 220, 0), (255, 100, 0), t_sub)
            else:
                t_sub = (usage - 0.70) / 0.30
                col = lerp_color((255, 100, 0), (255, 0, 0), t_sub)

            if is_single:
                c = apply_brightness(col, bright)
                return c, c, c
            else:
                l = apply_brightness(lerp_color((0, 200, 80), col, 0.5), bright)
                m = apply_brightness(col, bright)
                r = apply_brightness(lerp_color(col, (255, 0, 0), usage), bright)
                return l, m, r

        elif mode == "Ambient Screen":
            now = time.time()
            if now - self._last_ambient_grab > 0.1:
                self._last_ambient_grab = now
                try:
                    img = ImageGrab.grab(bbox=None).resize((60, 20))
                    w, h = img.size
                    
                    if is_single:
                        avg_p = img.resize((1, 1)).getpixel((0, 0))
                        raw_c = (avg_p[0], avg_p[1], avg_p[2])
                        self._ambient_cache[1] = lerp_color(self._ambient_cache[1], raw_c, 0.3)
                        self._ambient_cache[0] = self._ambient_cache[1]
                        self._ambient_cache[2] = self._ambient_cache[1]
                    else:
                        left_crop = img.crop((0, 0, w // 3, h))
                        mid_crop = img.crop((w // 3, 0, 2 * w // 3, h))
                        right_crop = img.crop((2 * w // 3, 0, w, h))
                        
                        def avg_rgb(im):
                            stat = im.resize((1, 1)).getpixel((0, 0))
                            return stat[0], stat[1], stat[2]
                            
                        self._ambient_cache[0] = lerp_color(self._ambient_cache[0], avg_rgb(left_crop), 0.3)
                        self._ambient_cache[1] = lerp_color(self._ambient_cache[1], avg_rgb(mid_crop), 0.3)
                        self._ambient_cache[2] = lerp_color(self._ambient_cache[2], avg_rgb(right_crop), 0.3)
                except Exception:
                    pass

            l = apply_brightness(self._ambient_cache[0], bright)
            m = apply_brightness(self._ambient_cache[1], bright)
            r = apply_brightness(self._ambient_cache[2], bright)
            return l, m, r

        elif mode == "Pomodoro Timer":
            cycle_time = (time.time() - self._pomodoro_start) % 1800.0
            if cycle_time < 1500.0:
                c = apply_brightness((0, 180, 220), bright)
            else:
                pulse = 0.6 + 0.4 * math.sin(t * 3.0)
                c = apply_brightness((255, 180, 0), bright * pulse)
            return c, c, c

        elif mode == "Cyberpunk Neon":
            wave = (math.sin(t * speed * 2.0) + 1.0) / 2.0
            if is_single:
                cycle_t = (t * speed * 0.4) % 3.0
                if cycle_t < 1.0:
                    col = lerp_color((255, 0, 128), (0, 255, 255), cycle_t)
                elif cycle_t < 2.0:
                    col = lerp_color((0, 255, 255), (255, 220, 0), cycle_t - 1.0)
                else:
                    col = lerp_color((255, 220, 0), (255, 0, 128), cycle_t - 2.0)
                c = apply_brightness(col, bright)
                return c, c, c
            else:
                l = lerp_color((255, 0, 128), (0, 255, 255), wave)
                m = lerp_color((0, 255, 255), (255, 220, 0), (wave + 0.33) % 1.0)
                r = lerp_color((255, 220, 0), (255, 0, 128), (wave + 0.66) % 1.0)
                return apply_brightness(l, bright), apply_brightness(m, bright), apply_brightness(r, bright)

        elif mode == "Fire & Ember":
            f1 = 0.7 + 0.3 * math.sin(t * speed * 4.0 + math.sin(t * 11.0))
            c_deep_red = (255, 20, 0)
            c_orange = (255, 120, 0)
            c_yellow = (255, 220, 10)
            
            if is_single:
                col = lerp_color(c_deep_red, c_orange, f1)
                c = apply_brightness(col, bright * f1)
                return c, c, c
            else:
                f2 = 0.7 + 0.3 * math.sin(t * speed * 5.0 + math.cos(t * 13.0))
                f3 = 0.7 + 0.3 * math.sin(t * speed * 3.5 + math.sin(t * 9.0))
                l = lerp_color(c_deep_red, c_orange, f1)
                m = lerp_color(c_orange, c_yellow, f2)
                r = lerp_color(c_deep_red, c_orange, f3)
                return apply_brightness(l, bright * f1), apply_brightness(m, bright * f2), apply_brightness(r, bright * f3)

        elif mode == "Matrix Rain":
            pulse = max(0.05, math.sin(t * speed * 3.5)) ** 3
            col = lerp_color((0, 30, 10), (0, 255, 60), pulse)
            c = apply_brightness(col, bright)
            return c, c, c

        elif mode == "Strobe / Flash":
            flash_state = (math.sin(t * speed * math.pi * 6.0) > 0.3)
            col = self.color_single if flash_state else (0, 0, 0)
            c = apply_brightness(col, bright if flash_state else 0)
            return c, c, c

        elif mode == "Police Siren":
            phase = int((t * speed * 3.0) % 2)
            col = (255, 0, 0) if phase == 0 else (0, 0, 255)
            c = apply_brightness(col, bright)
            if is_single:
                return c, c, c
            else:
                l = (255, 0, 0) if phase == 0 else (0, 0, 255)
                r = (0, 0, 255) if phase == 0 else (255, 0, 0)
                m = (60, 0, 60)
                return apply_brightness(l, bright), apply_brightness(m, bright), apply_brightness(r, bright)

        return (0, 0, 0), (0, 0, 0), (0, 0, 0)


engine = LightingEngine()
