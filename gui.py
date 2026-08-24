"""
Modern Graphical User Interface for Thunderobot RGB Keyboard.
Built with CustomTkinter, featuring Categorized Effects Grid,
Multi-App Notification Flash Colors (Telegram, Discord, Steam, WhatsApp),
Audio Visualizer, WPM Speedometer, and Calibration Wizard.
"""

import tkinter as tk
from tkinter import colorchooser, messagebox
import customtkinter as ctk
import colorsys
import os
import sys
import threading
import time
import ctypes
import logging
import psutil

from driver import driver
from config import config
from effects import engine, MODE_CATEGORIES

logger = logging.getLogger(__name__)

PRESET_COLORS = [
    ("#FF0055", "Neon Red"),
    ("#FF4500", "Flame Orange"),
    ("#FFB700", "Gold"),
    ("#00FF66", "Neon Green"),
    ("#00F0FF", "Cyan"),
    ("#0077FF", "Sky Blue"),
    ("#7000FF", "Purple"),
    ("#FF00D4", "Magenta"),
    ("#FFFFFF", "Pure White"),
    ("#FF77A9", "Soft Pink"),
    ("#00FFB2", "Mint"),
    ("#1E90FF", "Ice Blue"),
]

MAPPING_OPTIONS = [
    "BRG (Clevo / Thunderobot по умолч.)",
    "BGR (Стандартный BGR)",
    "RGB (Прямой RGB)",
    "RBG (Красный-Синий-Зеленый)",
    "GRB (Зеленый-Красный-Синий)",
    "GBR (Зеленый-Синий-Красный)",
]


def rgb_to_hex(r, g, b):
    return f"#{int(r):02X}{int(g):02X}{int(b):02X}"


def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


class CustomColorDialog(ctk.CTkToplevel):
    def __init__(self, parent, initial_rgb, on_apply):
        super().__init__(parent)
        self.title("Выбор цвета")
        self.geometry("410x520")
        self.resizable(False, False)
        self.configure(fg_color="#181920")
        self.attributes("-topmost", True)

        self.current_rgb = list(initial_rgb)
        self.on_apply = on_apply

        self._build_ui()
        self.grab_set()

    def _build_ui(self):
        self.preview_frame = ctk.CTkFrame(self, height=55, fg_color="#20222B", corner_radius=10)
        self.preview_frame.pack(fill="x", padx=20, pady=(15, 10))
        self.preview_frame.pack_propagate(False)

        self.preview_box = ctk.CTkFrame(
            self.preview_frame,
            fg_color=rgb_to_hex(*self.current_rgb),
            corner_radius=8
        )
        self.preview_box.pack(fill="both", expand=True, padx=4, pady=4)

        text_col = "#000000" if sum(self.current_rgb) > 380 else "#FFFFFF"
        self.hex_label = ctk.CTkLabel(
            self.preview_box,
            text=f"{rgb_to_hex(*self.current_rgb)}  •  RGB({self.current_rgb[0]}, {self.current_rgb[1]}, {self.current_rgb[2]})",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=text_col
        )
        self.hex_label.place(relx=0.5, rely=0.5, anchor="center")

        sliders_frame = ctk.CTkFrame(self, fg_color="#20222B", corner_radius=10)
        sliders_frame.pack(fill="x", padx=20, pady=5)

        # Red Slider
        ctk.CTkLabel(sliders_frame, text="R (Красный):", text_color="#FF4B68", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=(15, 5), pady=8, sticky="w")
        self.r_slider = ctk.CTkSlider(sliders_frame, from_=0, to=255, number_of_steps=255, command=self._on_slider_change, progress_color="#FF2A55", button_color="#FF2A55", button_hover_color="#FF4B68", height=18)
        self.r_slider.set(self.current_rgb[0])
        self.r_slider.grid(row=0, column=1, sticky="ew", padx=8)
        self.r_val_lbl = ctk.CTkLabel(sliders_frame, text=str(self.current_rgb[0]), width=35, font=ctk.CTkFont(weight="bold"))
        self.r_val_lbl.grid(row=0, column=2, padx=(5, 15))

        # Green Slider
        ctk.CTkLabel(sliders_frame, text="G (Зеленый):", text_color="#2BD980", font=ctk.CTkFont(size=12, weight="bold")).grid(row=1, column=0, padx=(15, 5), pady=8, sticky="w")
        self.g_slider = ctk.CTkSlider(sliders_frame, from_=0, to=255, number_of_steps=255, command=self._on_slider_change, progress_color="#2BD980", button_color="#2BD980", button_hover_color="#45ECA0", height=18)
        self.g_slider.set(self.current_rgb[1])
        self.g_slider.grid(row=1, column=1, sticky="ew", padx=8)
        self.g_val_lbl = ctk.CTkLabel(sliders_frame, text=str(self.current_rgb[1]), width=35, font=ctk.CTkFont(weight="bold"))
        self.g_val_lbl.grid(row=1, column=2, padx=(5, 15))

        # Blue Slider
        ctk.CTkLabel(sliders_frame, text="B (Синий):", text_color="#38A6FF", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=0, padx=(15, 5), pady=8, sticky="w")
        self.b_slider = ctk.CTkSlider(sliders_frame, from_=0, to=255, number_of_steps=255, command=self._on_slider_change, progress_color="#38A6FF", button_color="#38A6FF", button_hover_color="#60BAFF", height=18)
        self.b_slider.set(self.current_rgb[2])
        self.b_slider.grid(row=2, column=1, sticky="ew", padx=8)
        self.b_val_lbl = ctk.CTkLabel(sliders_frame, text=str(self.current_rgb[2]), width=35, font=ctk.CTkFont(weight="bold"))
        self.b_val_lbl.grid(row=2, column=2, padx=(5, 15))

        sliders_frame.columnconfigure(1, weight=1)

        palette_frame = ctk.CTkFrame(self, fg_color="#20222B", corner_radius=10)
        palette_frame.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(palette_frame, text="Быстрый выбор:", font=ctk.CTkFont(size=11), text_color="#888E9E").pack(anchor="w", padx=12, pady=(6, 4))
        
        q_grid = ctk.CTkFrame(palette_frame, fg_color="transparent")
        q_grid.pack(fill="x", padx=8, pady=(0, 8))
        
        for idx, (hex_code, name) in enumerate(PRESET_COLORS):
            btn = ctk.CTkButton(
                q_grid,
                text="",
                fg_color=hex_code,
                hover_color=hex_code,
                width=24,
                height=24,
                corner_radius=4,
                command=lambda c=hex_code: self._set_quick_hex(c)
            )
            btn.grid(row=idx // 6, column=idx % 6, padx=3, pady=3)

        ctk.CTkButton(
            self,
            text="Палитра Windows (Колесо цвета)...",
            fg_color="#282B37",
            hover_color="#35394A",
            height=32,
            font=ctk.CTkFont(size=12),
            command=self._open_system_picker
        ).pack(fill="x", padx=20, pady=(4, 12))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(5, 15))

        ctk.CTkButton(
            btn_frame,
            text="Отмена",
            fg_color="#2E313E",
            hover_color="#3E4254",
            font=ctk.CTkFont(weight="bold"),
            width=160,
            height=38,
            command=self.destroy
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_frame,
            text="Применить",
            fg_color="#00ADB5",
            hover_color="#00D2DD",
            font=ctk.CTkFont(weight="bold"),
            width=180,
            height=38,
            command=self._apply_and_close
        ).pack(side="right")

    def _set_quick_hex(self, hex_code):
        r, g, b = hex_to_rgb(hex_code)
        self.r_slider.set(r)
        self.g_slider.set(g)
        self.b_slider.set(b)
        self._on_slider_change()

    def _on_slider_change(self, _=None):
        r = int(self.r_slider.get())
        g = int(self.g_slider.get())
        b = int(self.b_slider.get())
        self.current_rgb = [r, g, b]
        self.r_val_lbl.configure(text=str(r))
        self.g_val_lbl.configure(text=str(g))
        self.b_val_lbl.configure(text=str(b))
        
        hex_c = rgb_to_hex(r, g, b)
        self.preview_box.configure(fg_color=hex_c)
        text_col = "#000000" if (r + g + b) > 380 else "#FFFFFF"
        self.hex_label.configure(
            text=f"{hex_c}  •  RGB({r}, {g}, {b})",
            text_color=text_col
        )

    def _open_system_picker(self):
        curr_hex = rgb_to_hex(*self.current_rgb)
        color = colorchooser.askcolor(color=curr_hex, title="Выберите цвет")
        if color and color[0]:
            r, g, b = [int(x) for x in color[0]]
            self.r_slider.set(r)
            self.g_slider.set(g)
            self.b_slider.set(b)
            self._on_slider_change()

    def _apply_and_close(self):
        self.on_apply(tuple(self.current_rgb))
        self.destroy()


class MainWindow(ctk.CTk):
    def __init__(self, on_close_callback=None):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Thunderobot 911S / 911s Core D — RGB Keyboard Suite Pro")
        self.geometry("980x830")
        self.minsize(920, 760)
        self.configure(fg_color="#121318")

        self.on_close_callback = on_close_callback
        self.protocol("WM_DELETE_WINDOW", self._on_close_event)

        self._active_color_target = "single"
        self._mode_buttons = {}

        # Apply saved driver calibration
        mapping = config.get("channel_mapping", "BRG")
        gr = config.get("gain_r", 1.0)
        gg = config.get("gain_g", 1.0)
        gb = config.get("gain_b", 1.0)
        driver.set_calibration(mapping, gr, gg, gb)

        self._build_header()
        self._build_visualizer()
        self._build_main_controls()

        engine.on_frame_rendered = self._update_visualizer_colors
        self._load_from_config()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="#1A1C24", height=65, corner_radius=0)
        header.pack(fill="x", side="top")

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=25, pady=10)

        ctk.CTkLabel(
            title_box,
            text="THUNDEROBOT 911S / CORE D",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color="#00ADB5"
        ).pack(anchor="w")

        status_text = f"Контроллер Insyde EC: ПОДКЛЮЧЕН (Канал: {config.get('channel_mapping', 'BRG')})" if driver.is_available else "Режим эмуляции"
        status_color = "#00FF88" if driver.is_available else "#FFB700"
        self.status_lbl = ctk.CTkLabel(
            title_box,
            text=f"● {status_text}",
            font=ctk.CTkFont(size=11),
            text_color=status_color
        )
        self.status_lbl.pack(anchor="w")

        self.telemetry_lbl = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#00ADB5"
        )
        self.telemetry_lbl.pack(side="left", padx=30)

        power_box = ctk.CTkFrame(header, fg_color="transparent")
        power_box.pack(side="right", padx=25, pady=10)

        self.power_switch = ctk.CTkSwitch(
            power_box,
            text="Подсветка ВКЛ",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_toggle_power,
            progress_color="#00ADB5"
        )
        self.power_switch.select() if config.get("power", True) else self.power_switch.deselect()
        self.power_switch.pack()

    def _build_visualizer(self):
        vis_container = ctk.CTkFrame(self, fg_color="#181920", corner_radius=12)
        vis_container.pack(fill="x", padx=25, pady=10)

        vis_header = ctk.CTkFrame(vis_container, fg_color="transparent")
        vis_header.pack(fill="x", padx=15, pady=(6, 4))
        ctk.CTkLabel(
            vis_header,
            text="ИНТЕРАКТИВНЫЙ ВИЗУАЛИЗАТОР КЛАВИАТУРЫ В РЕАЛЬНОМ ВРЕМЕНИ",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#888E9E"
        ).pack(side="left")

        kb_frame = ctk.CTkFrame(vis_container, fg_color="#121318", corner_radius=10, height=70)
        kb_frame.pack(fill="x", padx=15, pady=(2, 10))
        kb_frame.pack_propagate(False)

        self.vis_zone_left = ctk.CTkButton(
            kb_frame,
            text="Левая часть",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#252836",
            hover_color="#303446",
            corner_radius=8,
            command=lambda: self._select_color_target("left" if config.get("zone_mode") == "zones" else "single", open_dialog=True)
        )
        self.vis_zone_left.pack(side="left", fill="both", expand=True, padx=4, pady=5)

        self.vis_zone_mid = ctk.CTkButton(
            kb_frame,
            text="Центр (Основная)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#252836",
            hover_color="#303446",
            corner_radius=8,
            command=lambda: self._select_color_target("middle" if config.get("zone_mode") == "zones" else "single", open_dialog=True)
        )
        self.vis_zone_mid.pack(side="left", fill="both", expand=True, padx=4, pady=5)

        self.vis_zone_right = ctk.CTkButton(
            kb_frame,
            text="Правая часть / Numpad",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#252836",
            hover_color="#303446",
            corner_radius=8,
            command=lambda: self._select_color_target("right" if config.get("zone_mode") == "zones" else "single", open_dialog=True)
        )
        self.vis_zone_right.pack(side="left", fill="both", expand=True, padx=4, pady=5)

    def _build_main_controls(self):
        self.tabview = ctk.CTkTabview(self, fg_color="#181920", segmented_button_fg_color="#222530", segmented_button_selected_color="#00ADB5")
        self.tabview.pack(fill="both", expand=True, padx=25, pady=(0, 15))

        tab_effects = self.tabview.add("Режимы и Эффекты")
        tab_colors = self.tabview.add("Цветовая палитра")
        tab_calib = self.tabview.add("Калибровка цветов (Core D)")
        tab_profiles = self.tabview.add("Профили")
        tab_settings = self.tabview.add("Настройки")

        self._build_effects_tab(tab_effects)
        self._build_colors_tab(tab_colors)
        self._build_calibration_tab(tab_calib)
        self._build_profiles_tab(tab_profiles)
        self._build_settings_tab(tab_settings)

    def _build_effects_tab(self, tab):
        tab.columnconfigure(0, weight=6)
        tab.columnconfigure(1, weight=4)

        left_col = ctk.CTkFrame(tab, fg_color="#20222B", corner_radius=10)
        left_col.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(left_col, text="Категории световых эффектов", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00ADB5").pack(anchor="w", padx=15, pady=(12, 6))

        cats = list(MODE_CATEGORIES.keys())
        saved_cat = config.get("active_category", cats[0])
        if saved_cat not in cats:
            saved_cat = cats[0]

        self.category_seg = ctk.CTkSegmentedButton(
            left_col,
            values=cats,
            command=self._on_category_changed,
            selected_color="#00ADB5",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34
        )
        self.category_seg.set(saved_cat)
        self.category_seg.pack(fill="x", padx=15, pady=4)

        self.modes_grid_frame = ctk.CTkFrame(left_col, fg_color="#181920", corner_radius=8)
        self.modes_grid_frame.pack(fill="both", expand=True, padx=15, pady=8)

        self.mode_desc_box = ctk.CTkFrame(left_col, fg_color="#181920", corner_radius=8)
        self.mode_desc_box.pack(fill="x", padx=15, pady=(0, 12))

        self.active_mode_title_lbl = ctk.CTkLabel(
            self.mode_desc_box,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#00ADB5"
        )
        self.active_mode_title_lbl.pack(anchor="w", padx=12, pady=(8, 2))

        self.active_mode_desc_lbl = ctk.CTkLabel(
            self.mode_desc_box,
            text="",
            wraplength=420,
            justify="left",
            text_color="#A0A5B5",
            font=ctk.CTkFont(size=12)
        )
        self.active_mode_desc_lbl.pack(anchor="w", padx=12, pady=(0, 8))

        self._populate_category_modes(saved_cat)

        right_col = ctk.CTkFrame(tab, fg_color="#20222B", corner_radius=10)
        right_col.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(right_col, text="Яркость и Скорость", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00ADB5").pack(anchor="w", padx=15, pady=(12, 10))

        ctk.CTkLabel(right_col, text="Яркость подсветки:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=15, pady=(5, 0))
        b_box = ctk.CTkFrame(right_col, fg_color="transparent")
        b_box.pack(fill="x", padx=15, pady=(2, 8))

        self.bright_slider = ctk.CTkSlider(b_box, from_=0, to=255, number_of_steps=255, command=self._on_brightness_change, progress_color="#00ADB5")
        self.bright_slider.set(config.get("brightness", 255))
        self.bright_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.bright_lbl = ctk.CTkLabel(b_box, text=f"{int(config.get('brightness', 255)/2.55)}%", width=45, font=ctk.CTkFont(weight="bold"))
        self.bright_lbl.pack(side="right")

        q_b_frame = ctk.CTkFrame(right_col, fg_color="transparent")
        q_b_frame.pack(fill="x", padx=15, pady=(0, 12))
        for p in [0, 25, 50, 75, 100]:
            btn = ctk.CTkButton(
                q_b_frame,
                text=f"{p}%",
                width=45,
                height=26,
                fg_color="#2B2E3D",
                hover_color="#383C50",
                command=lambda val=p: self._set_quick_brightness(val)
            )
            btn.pack(side="left", expand=True, padx=2)

        ctk.CTkLabel(right_col, text="Скорость анимации:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=15, pady=(5, 0))
        s_box = ctk.CTkFrame(right_col, fg_color="transparent")
        s_box.pack(fill="x", padx=15, pady=(2, 12))

        self.speed_slider = ctk.CTkSlider(s_box, from_=0.1, to=3.0, number_of_steps=29, command=self._on_speed_change, progress_color="#FF7700")
        self.speed_slider.set(config.get("speed", 1.0))
        self.speed_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.speed_lbl = ctk.CTkLabel(s_box, text=f"{config.get('speed', 1.0):.1f}x", width=45, font=ctk.CTkFont(weight="bold"))
        self.speed_lbl.pack(side="right")

    def _on_category_changed(self, cat_name):
        config.set("active_category", cat_name)
        self._populate_category_modes(cat_name)

    def _populate_category_modes(self, cat_name):
        for w in self.modes_grid_frame.winfo_children():
            w.destroy()

        self._mode_buttons = {}
        modes = MODE_CATEGORIES.get(cat_name, [])
        active_mode = config.get("mode", "Rainbow Wave")

        for idx, (m_id, m_label, m_desc) in enumerate(modes):
            is_active = (m_id == active_mode)
            btn = ctk.CTkButton(
                self.modes_grid_frame,
                text=f"  {m_label}",
                anchor="w",
                font=ctk.CTkFont(size=13, weight="bold" if is_active else "normal"),
                fg_color="#00ADB5" if is_active else "#20222B",
                hover_color="#00D2DD" if is_active else "#2C2F3D",
                text_color="#FFFFFF",
                height=38,
                corner_radius=8,
                command=lambda mid=m_id, lbl=m_label, d=m_desc: self._select_mode(mid, lbl, d)
            )
            btn.pack(fill="x", padx=10, pady=4)
            self._mode_buttons[m_id] = btn

        self._update_mode_description()

    def _select_mode(self, mode_id, mode_label, mode_desc):
        config.set("mode", mode_id)
        engine.update_params(mode=mode_id)

        for mid, btn in self._mode_buttons.items():
            if mid == mode_id:
                btn.configure(fg_color="#00ADB5", hover_color="#00D2DD", font=ctk.CTkFont(size=13, weight="bold"))
            else:
                btn.configure(fg_color="#20222B", hover_color="#2C2F3D", font=ctk.CTkFont(size=13, weight="normal"))

        self.active_mode_title_lbl.configure(text=f"Режим: {mode_label}")
        self.active_mode_desc_lbl.configure(text=mode_desc)

    def _update_mode_description(self):
        curr_m = config.get("mode", "Rainbow Wave")
        found = False
        for cat, items in MODE_CATEGORIES.items():
            for m_id, m_label, m_desc in items:
                if m_id == curr_m:
                    self.active_mode_title_lbl.configure(text=f"Режим: {m_label}")
                    self.active_mode_desc_lbl.configure(text=m_desc)
                    found = True
                    break
            if found:
                break

    def _build_colors_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)

        col_left = ctk.CTkFrame(tab, fg_color="#20222B", corner_radius=10)
        col_left.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(col_left, text="Режим зон и цвет", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00ADB5").pack(anchor="w", padx=15, pady=(15, 10))

        self.zone_mode_seg = ctk.CTkSegmentedButton(
            col_left,
            values=["Вся клавиатура (1-Zone)", "3 Раздельные зоны"],
            command=self._on_zone_mode_change,
            selected_color="#00ADB5"
        )
        self.zone_mode_seg.set("Вся клавиатура (1-Zone)" if config.get("zone_mode") == "single" else "3 Раздельные зоны")
        self.zone_mode_seg.pack(fill="x", padx=15, pady=8)

        self.color_targets_frame = ctk.CTkFrame(col_left, fg_color="transparent")
        self.color_targets_frame.pack(fill="x", padx=15, pady=5)

        self.btn_color_single = self._create_color_row(self.color_targets_frame, "Основной цвет:", "single", config.get("color_single"))
        self.btn_color_sec = self._create_color_row(self.color_targets_frame, "Второй цвет (Дыхание / Волна):", "secondary", config.get("color_secondary"))
        self.btn_color_l = self._create_color_row(self.color_targets_frame, "Левая зона (3-Zone):", "left", config.get("color_left"))
        self.btn_color_m = self._create_color_row(self.color_targets_frame, "Центр (3-Zone):", "middle", config.get("color_middle"))
        self.btn_color_r = self._create_color_row(self.color_targets_frame, "Правая (3-Zone):", "right", config.get("color_right"))

        col_right = ctk.CTkFrame(tab, fg_color="#20222B", corner_radius=10)
        col_right.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(col_right, text="Быстрая палитра (16.8M RGB)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00ADB5").pack(anchor="w", padx=15, pady=(15, 10))

        preset_grid = ctk.CTkFrame(col_right, fg_color="transparent")
        preset_grid.pack(fill="x", padx=15, pady=5)

        row, col = 0, 0
        for hex_code, name in PRESET_COLORS:
            btn = ctk.CTkButton(
                preset_grid,
                text="",
                fg_color=hex_code,
                hover_color=hex_code,
                width=50,
                height=35,
                corner_radius=6,
                command=lambda c=hex_code: self._set_color_from_hex(c)
            )
            btn.grid(row=row, column=col, padx=4, pady=4)
            col += 1
            if col >= 4:
                col = 0
                row += 1

        ctk.CTkButton(
            col_right,
            text="Палитра детальной настройки RGB...",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#00ADB5",
            hover_color="#00D2DD",
            height=38,
            command=self._open_custom_picker
        ).pack(fill="x", padx=15, pady=(20, 15))

    def _build_calibration_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)

        col_left = ctk.CTkFrame(tab, fg_color="#20222B", corner_radius=10)
        col_left.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(col_left, text="Порядок каналов RGB", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00ADB5").pack(anchor="w", padx=15, pady=(15, 5))
        ctk.CTkLabel(col_left, text="Если при выборе Красного светится Синий или Зеленый, смените порядок каналов:", font=ctk.CTkFont(size=11), text_color="#8E94A5", wraplength=340, justify="left").pack(anchor="w", padx=15, pady=(0, 10))

        curr_map = config.get("channel_mapping", "BRG")
        selected_option = next((opt for opt in MAPPING_OPTIONS if opt.startswith(curr_map)), MAPPING_OPTIONS[0])
        self.mapping_var = tk.StringVar(value=selected_option)

        self.mapping_menu = ctk.CTkOptionMenu(
            col_left,
            values=MAPPING_OPTIONS,
            variable=self.mapping_var,
            command=self._on_channel_mapping_change,
            height=36,
            fg_color="#2B2E3D",
            button_color="#00ADB5"
        )
        self.mapping_menu.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(col_left, text="Быстрая проверка соответствия цветов:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#E0E5F0").pack(anchor="w", padx=15, pady=(15, 8))
        test_box = ctk.CTkFrame(col_left, fg_color="transparent")
        test_box.pack(fill="x", padx=15, pady=5)

        ctk.CTkButton(test_box, text="🔴 Красный", fg_color="#FF0044", hover_color="#FF2266", width=80, height=32, command=lambda: self._test_color(255, 0, 0)).grid(row=0, column=0, padx=3, pady=3)
        ctk.CTkButton(test_box, text="🟢 Зеленый", fg_color="#00CC44", hover_color="#22EE66", width=80, height=32, command=lambda: self._test_color(0, 255, 0)).grid(row=0, column=1, padx=3, pady=3)
        ctk.CTkButton(test_box, text="🔵 Синий", fg_color="#0066FF", hover_color="#3388FF", width=80, height=32, command=lambda: self._test_color(0, 0, 255)).grid(row=0, column=2, padx=3, pady=3)
        ctk.CTkButton(test_box, text="⚪ Белый", fg_color="#8899AA", hover_color="#AABBCC", text_color="#000000", width=80, height=32, command=lambda: self._test_color(255, 255, 255)).grid(row=1, column=0, columnspan=3, sticky="ew", padx=3, pady=5)

        col_right = ctk.CTkFrame(tab, fg_color="#20222B", corner_radius=10)
        col_right.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(col_right, text="Баланс каналов (Gain)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00ADB5").pack(anchor="w", padx=15, pady=(15, 5))
        ctk.CTkLabel(col_right, text="Тонкая подстройка яркости отдельных каналов для идеального белого:", font=ctk.CTkFont(size=11), text_color="#8E94A5", wraplength=340, justify="left").pack(anchor="w", padx=15, pady=(0, 10))

        ctk.CTkLabel(col_right, text="Красный канал (R):", text_color="#FF5555").pack(anchor="w", padx=15, pady=(5, 0))
        r_box = ctk.CTkFrame(col_right, fg_color="transparent")
        r_box.pack(fill="x", padx=15, pady=2)
        self.gain_r_slider = ctk.CTkSlider(r_box, from_=0.1, to=1.0, number_of_steps=18, command=self._on_gain_change, progress_color="#FF3366")
        self.gain_r_slider.set(config.get("gain_r", 1.0))
        self.gain_r_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.gain_r_lbl = ctk.CTkLabel(r_box, text=f"{int(config.get('gain_r', 1.0)*100)}%", width=40)
        self.gain_r_lbl.pack(side="right")

        ctk.CTkLabel(col_right, text="Зеленый канал (G):", text_color="#55FF55").pack(anchor="w", padx=15, pady=(5, 0))
        g_box = ctk.CTkFrame(col_right, fg_color="transparent")
        g_box.pack(fill="x", padx=15, pady=2)
        self.gain_g_slider = ctk.CTkSlider(g_box, from_=0.1, to=1.0, number_of_steps=18, command=self._on_gain_change, progress_color="#33FF66")
        self.gain_g_slider.set(config.get("gain_g", 1.0))
        self.gain_g_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.gain_g_lbl = ctk.CTkLabel(g_box, text=f"{int(config.get('gain_g', 1.0)*100)}%", width=40)
        self.gain_g_lbl.pack(side="right")

        ctk.CTkLabel(col_right, text="Синий канал (B):", text_color="#55AAFF").pack(anchor="w", padx=15, pady=(5, 0))
        b_box = ctk.CTkFrame(col_right, fg_color="transparent")
        b_box.pack(fill="x", padx=15, pady=2)
        self.gain_b_slider = ctk.CTkSlider(b_box, from_=0.1, to=1.0, number_of_steps=18, command=self._on_gain_change, progress_color="#3399FF")
        self.gain_b_slider.set(config.get("gain_b", 1.0))
        self.gain_b_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.gain_b_lbl = ctk.CTkLabel(b_box, text=f"{int(config.get('gain_b', 1.0)*100)}%", width=40)
        self.gain_b_lbl.pack(side="right")

        ctk.CTkButton(
            col_right,
            text="Сбросить калибровку по умолчанию",
            fg_color="#2B2E3D",
            hover_color="#383C50",
            command=self._reset_calibration
        ).pack(fill="x", padx=15, pady=(15, 10))

    def _test_color(self, r, g, b):
        self.category_seg.set("💡 Статика")
        self._populate_category_modes("💡 Статика")
        self._select_mode("Static", "💡 Статичный цвет", "Постоянное свечение заданным цветом.")
        self._on_color_selected((r, g, b))

    def _on_channel_mapping_change(self, opt_str):
        mapping = opt_str.split()[0]
        config.set("channel_mapping", mapping)
        driver.set_calibration(mapping, self.gain_r_slider.get(), self.gain_g_slider.get(), self.gain_b_slider.get())
        if hasattr(self, "status_lbl"):
            self.status_lbl.configure(text=f"● Контроллер Insyde EC: ПОДКЛЮЧЕН (Канал: {mapping})")

    def _on_gain_change(self, _=None):
        gr = round(float(self.gain_r_slider.get()), 2)
        gg = round(float(self.gain_g_slider.get()), 2)
        gb = round(float(self.gain_b_slider.get()), 2)
        
        self.gain_r_lbl.configure(text=f"{int(gr*100)}%")
        self.gain_g_lbl.configure(text=f"{int(gg*100)}%")
        self.gain_b_lbl.configure(text=f"{int(gb*100)}%")
        
        config.set("gain_r", gr)
        config.set("gain_g", gg)
        config.set("gain_b", gb)
        
        mapping = config.get("channel_mapping", "BRG")
        driver.set_calibration(mapping, gr, gg, gb)

    def _reset_calibration(self):
        self.gain_r_slider.set(1.0)
        self.gain_g_slider.set(1.0)
        self.gain_b_slider.set(1.0)
        self._on_gain_change()
        self.mapping_menu.set(MAPPING_OPTIONS[0])
        self._on_channel_mapping_change(MAPPING_OPTIONS[0])

    def _create_color_row(self, parent, label_text, target_name, init_rgb):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=3)

        ctk.CTkLabel(row, text=label_text, width=170, anchor="w").pack(side="left")

        btn = ctk.CTkButton(
            row,
            text=rgb_to_hex(*init_rgb),
            fg_color=rgb_to_hex(*init_rgb),
            hover_color=rgb_to_hex(*init_rgb),
            text_color="#000000" if sum(init_rgb) > 380 else "#FFFFFF",
            font=ctk.CTkFont(weight="bold"),
            width=90,
            height=28,
            command=lambda: self._select_color_target(target_name, open_dialog=True)
        )
        btn.pack(side="right")
        return btn

    def _build_profiles_tab(self, tab):
        tab.columnconfigure(0, weight=1)

        container = ctk.CTkFrame(tab, fg_color="#20222B", corner_radius=10)
        container.pack(fill="both", expand=True, padx=20, pady=15)

        ctk.CTkLabel(container, text="Сохраненные профили подсветки", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00ADB5").pack(anchor="w", padx=20, pady=(15, 10))

        sel_box = ctk.CTkFrame(container, fg_color="transparent")
        sel_box.pack(fill="x", padx=20, pady=10)

        self.prof_var = tk.StringVar(value="")
        profiles_list = list(config.get("profiles", {}).keys())
        if profiles_list:
            self.prof_var.set(profiles_list[0])

        self.prof_menu = ctk.CTkOptionMenu(
            sel_box,
            values=profiles_list if profiles_list else ["(Нет профилей)"],
            variable=self.prof_var,
            width=220,
            height=36,
            fg_color="#2B2E3D",
            button_color="#00ADB5"
        )
        self.prof_menu.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            sel_box,
            text="Загрузить профиль",
            fg_color="#00ADB5",
            hover_color="#00D2DD",
            height=36,
            command=self._on_load_profile
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            sel_box,
            text="Удалить",
            fg_color="#FF3366",
            hover_color="#FF5588",
            height=36,
            command=self._on_delete_profile
        ).pack(side="left", padx=5)

        save_box = ctk.CTkFrame(container, fg_color="transparent")
        save_box.pack(fill="x", padx=20, pady=(20, 15))

        self.new_prof_entry = ctk.CTkEntry(save_box, placeholder_text="Имя нового профиля...", width=220, height=36)
        self.new_prof_entry.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            save_box,
            text="Сохранить текущие настройки",
            fg_color="#2B2E3D",
            hover_color="#383C50",
            height=36,
            command=self._on_save_profile
        ).pack(side="left", padx=5)

    def _build_settings_tab(self, tab):
        container = ctk.CTkScrollableFrame(tab, fg_color="#20222B", corner_radius=10)
        container.pack(fill="both", expand=True, padx=20, pady=15)

        ctk.CTkLabel(container, text="Световые уведомления от мессенджеров и программ", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00ADB5").pack(anchor="w", padx=10, pady=(10, 5))
        ctk.CTkLabel(container, text="Клавиатура вспыхивает цветом приложения при входящем сообщении:", font=ctk.CTkFont(size=11), text_color="#8E94A5").pack(anchor="w", padx=10, pady=(0, 8))

        notif_card = ctk.CTkFrame(container, fg_color="#181920", corner_radius=10)
        notif_card.pack(fill="x", padx=10, pady=6)

        notif_top = ctk.CTkFrame(notif_card, fg_color="transparent")
        notif_top.pack(fill="x", padx=15, pady=(12, 8))

        self.notif_flash_switch = ctk.CTkSwitch(
            notif_top,
            text="Включить световую индикацию входящих уведомлений",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_notif_flash_toggle,
            progress_color="#00ADB5"
        )
        if config.get("notification_flash", True):
            self.notif_flash_switch.select()
        self.notif_flash_switch.pack(anchor="w")

        notif_rows_box = ctk.CTkFrame(notif_card, fg_color="transparent")
        notif_rows_box.pack(fill="x", padx=12, pady=(0, 12))

        app_defs = [
            ("telegram", "✈️  Telegram", "telegram"),
            ("discord", "🎮  Discord", "discord"),
            ("steam", "🕹️  Steam", "steam"),
            ("whatsapp", "💬  WhatsApp / VK", "whatsapp"),
            ("windows", "🪟  Windows / Браузер", "windows"),
        ]

        self.app_notif_btns = {}
        for app_key, label_text, test_key in app_defs:
            r_frame = ctk.CTkFrame(notif_rows_box, fg_color="#20222B", corner_radius=8, height=44)
            r_frame.pack(fill="x", pady=3)
            r_frame.pack_propagate(False)
            r_frame.columnconfigure(0, weight=1)
            r_frame.columnconfigure(1, weight=0)
            r_frame.columnconfigure(2, weight=0)

            ctk.CTkLabel(
                r_frame,
                text=label_text,
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w"
            ).grid(row=0, column=0, sticky="w", padx=(15, 10), pady=7)

            curr_c = config.get("app_notif_colors", {}).get(app_key, [0, 180, 255])
            hex_c = rgb_to_hex(*curr_c)

            c_btn = ctk.CTkButton(
                r_frame,
                text=hex_c,
                fg_color=hex_c,
                hover_color=hex_c,
                text_color="#000000" if sum(curr_c) > 380 else "#FFFFFF",
                font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                width=105,
                height=30,
                corner_radius=6,
                command=lambda k=app_key: self._pick_app_notif_color(k)
            )
            c_btn.grid(row=0, column=1, padx=(0, 10), pady=7)
            self.app_notif_btns[app_key] = c_btn

            ctk.CTkButton(
                r_frame,
                text="Тест ⚡",
                fg_color="#2B2E3D",
                hover_color="#383C50",
                font=ctk.CTkFont(size=12, weight="bold"),
                width=80,
                height=30,
                corner_radius=6,
                command=lambda k=test_key: engine.trigger_notification_flash(app_name=k)
            ).grid(row=0, column=2, padx=(0, 12), pady=7)

        ctk.CTkLabel(container, text="Системные настройки и умные функции", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00ADB5").pack(anchor="w", padx=10, pady=(15, 8))

        self.fn_redirect_switch = ctk.CTkSwitch(
            container,
            text="Перенаправить клавишу Fn (Control Center / Fn + /) на эту программу",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_fn_redirect_toggle,
            progress_color="#00ADB5"
        )
        if config.get("fn_redirect", True):
            self.fn_redirect_switch.select()
        self.fn_redirect_switch.pack(anchor="w", padx=10, pady=6)

        self.autostart_switch = ctk.CTkSwitch(
            container,
            text="Запускать вместе с Windows (в системном трее)",
            font=ctk.CTkFont(size=13),
            command=self._on_autostart_toggle,
            progress_color="#00ADB5"
        )
        if config.get("autostart", False):
            self.autostart_switch.select()
        self.autostart_switch.pack(anchor="w", padx=10, pady=6)

        self.close_to_tray_switch = ctk.CTkSwitch(
            container,
            text="Сворачивать в системный трей при закрытии крестиком",
            font=ctk.CTkFont(size=13),
            command=self._on_close_to_tray_toggle,
            progress_color="#00ADB5"
        )
        if config.get("close_to_tray", True):
            self.close_to_tray_switch.select()
        self.close_to_tray_switch.pack(anchor="w", padx=10, pady=6)

        self.idle_dim_switch = ctk.CTkSwitch(
            container,
            text="Умное затемнение: снижать яркость до 15% при простое более 45 сек",
            font=ctk.CTkFont(size=13),
            command=self._on_idle_dim_toggle,
            progress_color="#00ADB5"
        )
        if config.get("smart_idle_dim", True):
            self.idle_dim_switch.select()
        self.idle_dim_switch.pack(anchor="w", padx=10, pady=6)

        self.bat_saver_switch = ctk.CTkSwitch(
            container,
            text="Энергосбережение: снижать яркость до 30% при работе от батареи",
            font=ctk.CTkFont(size=13),
            command=self._on_battery_saver_toggle,
            progress_color="#00ADB5"
        )
        if config.get("battery_saver", True):
            self.bat_saver_switch.select()
        self.bat_saver_switch.pack(anchor="w", padx=10, pady=6)

        self.night_shift_switch = ctk.CTkSwitch(
            container,
            text="Ночной режим (Night Shift): теплый янтарный свет после 22:00",
            font=ctk.CTkFont(size=13),
            command=self._on_night_shift_toggle,
            progress_color="#00ADB5"
        )
        if config.get("night_shift", False):
            self.night_shift_switch.select()
        self.night_shift_switch.pack(anchor="w", padx=10, pady=6)

        ctk.CTkLabel(container, text="Автоотключение подсветки при бездействии (минуты):", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=10, pady=(10, 3))
        to_box = ctk.CTkFrame(container, fg_color="transparent")
        to_box.pack(fill="x", padx=10, pady=2)

        self.timeout_slider = ctk.CTkSlider(to_box, from_=0, to=30, number_of_steps=30, command=self._on_timeout_change, progress_color="#00ADB5")
        self.timeout_slider.set(config.get("timeout_mins", 0))
        self.timeout_slider.pack(side="left", fill="x", expand=True, padx=(0, 15))

        self.timeout_lbl = ctk.CTkLabel(to_box, text=self._format_timeout(config.get("timeout_mins", 0)), width=80, font=ctk.CTkFont(weight="bold"))
        self.timeout_lbl.pack(side="right")

    def _pick_app_notif_color(self, app_key):
        curr_c = config.get("app_notif_colors", {}).get(app_key, [0, 180, 255])
        
        def on_color_chosen(rgb):
            notif_map = config.get("app_notif_colors", {})
            notif_map[app_key] = list(rgb)
            config.set("app_notif_colors", notif_map)
            engine.app_notif_colors[app_key] = rgb

            hex_c = rgb_to_hex(*rgb)
            if app_key in self.app_notif_btns:
                self.app_notif_btns[app_key].configure(
                    text=hex_c,
                    fg_color=hex_c,
                    hover_color=hex_c,
                    text_color="#000000" if sum(rgb) > 380 else "#FFFFFF"
                )

        CustomColorDialog(self, curr_c, on_color_chosen)

    def _format_timeout(self, mins):
        m = int(mins)
        return "Отключено" if m == 0 else f"{m} мин"

    def _load_from_config(self):
        engine.update_params(
            mode=config.get("mode", "Rainbow Wave"),
            power=config.get("power", True),
            brightness=config.get("brightness", 255),
            speed=config.get("speed", 1.0),
            zone_mode=config.get("zone_mode", "single"),
            battery_saver=config.get("battery_saver", True),
            night_shift=config.get("night_shift", False),
            smart_idle_dim=config.get("smart_idle_dim", True),
            notification_flash_enabled=config.get("notification_flash", True),
            app_notif_colors={k: tuple(v) for k, v in config.get("app_notif_colors", {}).items()},
            color_single=tuple(config.get("color_single", [0, 255, 255])),
            color_left=tuple(config.get("color_left", [255, 0, 128])),
            color_middle=tuple(config.get("color_middle", [0, 255, 255])),
            color_right=tuple(config.get("color_right", [120, 0, 255])),
            color_secondary=tuple(config.get("color_secondary", [255, 0, 80])),
        )

    def _update_visualizer_colors(self, left, mid, right):
        try:
            hex_l = rgb_to_hex(*left)
            hex_m = rgb_to_hex(*mid)
            hex_r = rgb_to_hex(*right)
            self.vis_zone_left.configure(fg_color=hex_l, hover_color=hex_l, text_color="#000000" if sum(left) > 380 else "#FFFFFF")
            self.vis_zone_mid.configure(fg_color=hex_m, hover_color=hex_m, text_color="#000000" if sum(mid) > 380 else "#FFFFFF")
            self.vis_zone_right.configure(fg_color=hex_r, hover_color=hex_r, text_color="#000000" if sum(right) > 380 else "#FFFFFF")

            m = engine.mode
            if m == "WPM Typing Speed":
                self.telemetry_lbl.configure(text=f"⌨️ Скорость: {int(engine._current_wpm)} WPM")
            elif m == "Audio Visualizer":
                pct = int(engine._audio_level * 100)
                self.telemetry_lbl.configure(text=f"🎵 Звук: {pct}%")
            elif m == "CPU Temp Monitor":
                self.telemetry_lbl.configure(text=f"🔥 CPU: {int(engine._last_cpu_percent)}%")
            elif m == "RAM Usage Meter":
                self.telemetry_lbl.configure(text=f"🧠 RAM: {int(engine._last_ram_percent)}%")
            else:
                self.telemetry_lbl.configure(text="")
        except Exception:
            pass

    def _on_toggle_power(self):
        on = bool(self.power_switch.get())
        config.set("power", on)
        engine.update_params(power=on)
        driver.set_power(on)

    def _on_brightness_change(self, val):
        b = int(val)
        config.set("brightness", b)
        engine.update_params(brightness=b)
        self.bright_lbl.configure(text=f"{int(b/2.55)}%")

    def _set_quick_brightness(self, percent):
        b = int(percent * 2.55)
        self.bright_slider.set(b)
        self._on_brightness_change(b)

    def _on_speed_change(self, val):
        s = round(float(val), 1)
        config.set("speed", s)
        engine.update_params(speed=s)
        self.speed_lbl.configure(text=f"{s:.1f}x")

    def _on_zone_mode_change(self, mode_str):
        mode = "single" if "1-Zone" in mode_str else "zones"
        config.set("zone_mode", mode)
        engine.update_params(zone_mode=mode)

    def _select_color_target(self, target, open_dialog=False):
        self._active_color_target = target
        if open_dialog:
            self._open_custom_picker()

    def _open_custom_picker(self):
        target = self._active_color_target
        curr = config.get(f"color_{target}", config.get("color_single", [0, 255, 255]))
        CustomColorDialog(self, curr, self._on_color_selected)

    def _set_color_from_hex(self, hex_code):
        rgb = hex_to_rgb(hex_code)
        self._on_color_selected(rgb)

    def _on_color_selected(self, rgb):
        target = self._active_color_target
        config.set(f"color_{target}", list(rgb))
        engine.update_params(**{f"color_{target}": rgb})

        hex_c = rgb_to_hex(*rgb)
        btn_map = {
            "single": self.btn_color_single,
            "secondary": self.btn_color_sec,
            "left": self.btn_color_l,
            "middle": self.btn_color_m,
            "right": self.btn_color_r,
        }
        if target in btn_map:
            btn_map[target].configure(
                text=hex_c,
                fg_color=hex_c,
                hover_color=hex_c,
                text_color="#000000" if sum(rgb) > 380 else "#FFFFFF"
            )

    def _on_save_profile(self):
        name = self.new_prof_entry.get().strip()
        if not name:
            messagebox.showwarning("Внимание", "Пожалуйста, введите название профиля.")
            return
        config.save_profile(name)
        self.new_prof_entry.delete(0, "end")
        profs = list(config.get("profiles", {}).keys())
        self.prof_menu.configure(values=profs)
        self.prof_var.set(name)
        messagebox.showinfo("Успешно", f"Профиль '{name}' успешно сохранен!")

    def _on_load_profile(self):
        name = self.prof_var.get()
        if config.load_profile(name):
            self._load_from_config()
            self._update_mode_description()
            self.bright_slider.set(config.get("brightness", 255))
            self.bright_lbl.configure(text=f"{int(config.get('brightness', 255)/2.55)}%")
            self.speed_slider.set(config.get("speed", 1.0))
            self.speed_lbl.configure(text=f"{config.get('speed', 1.0):.1f}x")
            self.zone_mode_seg.set("Вся клавиатура (1-Zone)" if config.get("zone_mode") == "single" else "3 Раздельные зоны")
            
            for t, btn in [
                ("single", self.btn_color_single),
                ("secondary", self.btn_color_sec),
                ("left", self.btn_color_l),
                ("middle", self.btn_color_m),
                ("right", self.btn_color_r),
            ]:
                c = config.get(f"color_{t}")
                if c:
                    hex_c = rgb_to_hex(*c)
                    btn.configure(text=hex_c, fg_color=hex_c, hover_color=hex_c, text_color="#000000" if sum(c) > 380 else "#FFFFFF")

    def _on_delete_profile(self):
        name = self.prof_var.get()
        if name:
            config.delete_profile(name)
            profs = list(config.get("profiles", {}).keys())
            self.prof_menu.configure(values=profs if profs else ["(Нет профилей)"])
            self.prof_var.set(profs[0] if profs else "")

    def _on_autostart_toggle(self):
        val = bool(self.autostart_switch.get())
        config.set_autostart(val)

    def _on_fn_redirect_toggle(self):
        val = bool(self.fn_redirect_switch.get())
        config.set_fn_redirect(val)

    def _on_close_to_tray_toggle(self):
        val = bool(self.close_to_tray_switch.get())
        config.set("close_to_tray", val)

    def _on_notif_flash_toggle(self):
        val = bool(self.notif_flash_switch.get())
        config.set("notification_flash", val)
        engine.update_params(notification_flash_enabled=val)

    def _on_idle_dim_toggle(self):
        val = bool(self.idle_dim_switch.get())
        config.set("smart_idle_dim", val)
        engine.update_params(smart_idle_dim=val)

    def _on_battery_saver_toggle(self):
        val = bool(self.bat_saver_switch.get())
        config.set("battery_saver", val)
        engine.update_params(battery_saver=val)

    def _on_night_shift_toggle(self):
        val = bool(self.night_shift_switch.get())
        config.set("night_shift", val)
        engine.update_params(night_shift=val)

    def _on_timeout_change(self, val):
        mins = int(val)
        config.set("timeout_mins", mins)
        self.timeout_lbl.configure(text=self._format_timeout(mins))
        driver.set_timeout(mins)

    def _on_close_event(self):
        if config.get("close_to_tray", True):
            self.withdraw()
        else:
            if self.on_close_callback:
                self.on_close_callback()
            self.destroy()
