"""
Wallpaper Engine RGB Sync Provider for Thunderobot RGB Keyboard.
Provides:
1. Built-in Razer Chroma REST API Server on 127.0.0.1:12018 (receives real-time LED stream from Wallpaper Engine)
2. Live Wallpaper Engine Desktop Window Color Sampler (captures live wallpaper surface colors as fallback/direct mode)
"""

import os
import sys
import time
import json
import math
import logging
import threading
import winreg
import http.server
import socketserver
import ctypes
from ctypes import wintypes
from PIL import ImageGrab

logger = logging.getLogger(__name__)


def ensure_chroma_registry():
    """Registers Razer Chroma REST URI in Windows Registry so Wallpaper Engine LED plugin discovers it."""
    for root_key, sub_path in [
        (winreg.HKEY_CURRENT_USER, r"Software\Razer\ChromaSDK"),
        (winreg.HKEY_CURRENT_USER, r"Software\Razer Chroma SDK"),
    ]:
        try:
            k = winreg.CreateKey(root_key, sub_path)
            winreg.SetValueEx(k, "RESTURI", 0, winreg.REG_SZ, "http://127.0.0.1:12018/razer/chromasdk")
            winreg.SetValueEx(k, "Connected", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(k)
        except Exception as e:
            logger.debug(f"Could not set Chroma registry at {sub_path}: {e}")


def bgr_int_to_rgb(val: int):
    """Converts 0x00BBGGRR or 0x00RRGGBB integer to (R, G, B) tuple."""
    r = val & 0xFF
    g = (val >> 8) & 0xFF
    b = (val >> 16) & 0xFF
    return (r, g, b)


class ChromaRESTHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data: dict, status=200):
        try:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else ""
        
        wallpaper_sync.on_chroma_session_started()
        self._send_json({
            "sessionid": 1,
            "uri": "http://127.0.0.1:12018/razer/chromasdk/session"
        })

    def do_PUT(self):
        length = int(self.headers.get("content-length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else ""
        
        if body:
            try:
                data = json.loads(body)
                wallpaper_sync.process_chroma_frame(self.path, data)
            except Exception:
                pass
                
        self._send_json({"result": 0})

    def do_GET(self):
        self._send_json({
            "version": "3.20.0",
            "connected": True,
            "device": "Thunderobot RGB Keyboard"
        })

    def do_DELETE(self):
        wallpaper_sync.on_chroma_session_stopped()
        self._send_json({"result": 0})


class WallpaperEngineSyncProvider:
    def __init__(self):
        self._server = None
        self._server_thread = None
        self._running = False
        
        # State
        self.is_connected = False
        self.last_frame_time = 0.0
        self.current_left = (0, 180, 255)
        self.current_middle = (0, 180, 255)
        self.current_right = (0, 180, 255)
        self.current_single = (0, 180, 255)
        
        # Desktop Window Sampler state (fallback)
        self._last_screen_grab = 0.0
        self._desktop_cache = [(0, 180, 255), (0, 180, 255), (0, 180, 255)]

    def start(self):
        if self._running:
            return
        self._running = True
        ensure_chroma_registry()
        
        def run_srv():
            try:
                socketserver.TCPServer.allow_reuse_address = True
                self._server = socketserver.TCPServer(("127.0.0.1", 12018), ChromaRESTHandler)
                logger.info("Razer Chroma REST Server for Wallpaper Engine started on 127.0.0.1:12018")
                self._server.serve_forever()
            except Exception as e:
                logger.warning(f"Could not start Chroma REST server on 12018: {e}")

        self._server_thread = threading.Thread(target=run_srv, daemon=True)
        self._server_thread.start()

    def stop(self):
        self._running = False
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass

    def on_chroma_session_started(self):
        self.is_connected = True
        self.last_frame_time = time.time()
        logger.info("Wallpaper Engine Chroma session established!")

    def on_chroma_session_stopped(self):
        self.is_connected = False
        logger.info("Wallpaper Engine Chroma session closed.")

    def process_chroma_frame(self, path: str, data: dict):
        """Processes RGB matrix or ChromaLink color array from Wallpaper Engine."""
        self.is_connected = True
        self.last_frame_time = time.time()

        effect = data.get("effect", "")
        param = data.get("param")

        if not param:
            return

        if effect == "CHROMA_CUSTOM" and isinstance(param, list) and len(param) > 0 and isinstance(param[0], list):
            rows = len(param)
            cols = len(param[0]) if rows > 0 else 0

            left_colors, mid_colors, right_colors = [], [], []

            for r in range(rows):
                for c in range(cols):
                    val = param[r][c]
                    if val != 0:
                        rgb = bgr_int_to_rgb(val)
                        if rgb[0] > 5 or rgb[1] > 5 or rgb[2] > 5:
                            if c < cols // 3:
                                left_colors.append(rgb)
                            elif c < 2 * (cols // 3):
                                mid_colors.append(rgb)
                            else:
                                right_colors.append(rgb)

            def avg_list(lst, default):
                if not lst:
                    return default
                r = sum(x[0] for x in lst) // len(lst)
                g = sum(x[1] for x in lst) // len(lst)
                b = sum(x[2] for x in lst) // len(lst)
                return (r, g, b)

            if left_colors or mid_colors or right_colors:
                all_c = left_colors + mid_colors + right_colors
                self.current_single = avg_list(all_c, self.current_single)
                self.current_left = avg_list(left_colors, self.current_single)
                self.current_middle = avg_list(mid_colors, self.current_single)
                self.current_right = avg_list(right_colors, self.current_single)

        elif effect == "CHROMA_STATIC" and isinstance(param, dict):
            val = param.get("color", 0)
            rgb = bgr_int_to_rgb(val)
            self.current_single = self.current_left = self.current_middle = self.current_right = rgb

        elif isinstance(param, list) and len(param) > 0 and isinstance(param[0], int):
            valid = [bgr_int_to_rgb(v) for v in param if v > 0]
            if valid:
                self.current_single = valid[len(valid) // 2]
                self.current_left = valid[0]
                self.current_middle = valid[len(valid) // 2]
                self.current_right = valid[-1]

    def get_colors(self, is_single: bool = True):
        now = time.time()

        if self.is_connected and (now - self.last_frame_time < 2.5):
            if is_single:
                return self.current_single, self.current_single, self.current_single
            return self.current_left, self.current_middle, self.current_right

        if now - self._last_screen_grab > 0.08:
            self._last_screen_grab = now
            try:
                img = ImageGrab.grab(bbox=None).resize((60, 20))
                w, h = img.size

                def avg_rgb(im):
                    stat = im.resize((1, 1)).getpixel((0, 0))
                    return (stat[0], stat[1], stat[2])

                if is_single:
                    avg_c = avg_rgb(img)
                    self._desktop_cache[1] = avg_c
                    self._desktop_cache[0] = avg_c
                    self._desktop_cache[2] = avg_c
                else:
                    self._desktop_cache[0] = avg_rgb(img.crop((0, 0, w // 3, h)))
                    self._desktop_cache[1] = avg_rgb(img.crop((w // 3, 0, 2 * w // 3, h)))
                    self._desktop_cache[2] = avg_rgb(img.crop((2 * w // 3, 0, w, h)))
            except Exception:
                pass

        if is_single:
            c = self._desktop_cache[1]
            return c, c, c
        return self._desktop_cache[0], self._desktop_cache[1], self._desktop_cache[2]


wallpaper_sync = WallpaperEngineSyncProvider()
