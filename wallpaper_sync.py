"""
Advanced Wallpaper Engine Dynamic RGB Sync Engine for Thunderobot RGB Keyboard.
Features:
1. Direct Active Steam Workshop Wallpaper Live Analyzer (reads active wallpaper frames even when apps/games are full screen!)
2. Peak Chromatic Energy & Auto-Gain Normalization (filters out black background and boosts vibrant colors to 100% full brightness)
3. 3-Zone Left / Center / Right Spatial Gradient Mapping
4. Built-in Razer Chroma REST API Server on 127.0.0.1:12018
"""

import os
import sys
import time
import json
import math
import logging
import threading
import colorsys
import winreg
import http.server
import socketserver
from PIL import Image, ImageSequence, ImageGrab

logger = logging.getLogger(__name__)

WE_CONFIG_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\wallpaper_engine\config.json"


def bgr_int_to_rgb(val: int):
    r = val & 0xFF
    g = (val >> 8) & 0xFF
    b = (val >> 16) & 0xFF
    return (r, g, b)


def extract_vibrant_triplet(img_obj, last_valid=((0, 200, 255), (0, 200, 255), (0, 200, 255))):
    """
    Extracts high-saturation, peak chromatic energy colors for Left, Center, Right zones,
    completely ignoring black/dark background pixels and boosting brightness to 100% full intensity.
    """
    try:
        sample = img_obj.convert("RGB").resize((48, 24))
        w, h = sample.size
        pix = sample.load()

        def analyze_region(x_start, x_end):
            scored = []
            all_non_black = []
            for y in range(h):
                for x in range(x_start, x_end):
                    r, g, b = pix[x, y]
                    lum = (r + g + b) / 3.0
                    chroma = max(r, g, b) - min(r, g, b)
                    if lum > 18:
                        all_non_black.append((r, g, b))
                        if chroma > 15:
                            score = chroma * (lum ** 0.5)
                            scored.append((score, r, g, b))

            if scored:
                scored.sort(key=lambda item: item[0], reverse=True)
                top_k = scored[:max(4, int(len(scored) * 0.35))]
                avg_r = sum(p[1] for p in top_k) / len(top_k)
                avg_g = sum(p[2] for p in top_k) / len(top_k)
                avg_b = sum(p[3] for p in top_k) / len(top_k)
            elif all_non_black:
                avg_r = sum(p[0] for p in all_non_black) / len(all_non_black)
                avg_g = sum(p[1] for p in all_non_black) / len(all_non_black)
                avg_b = sum(p[2] for p in all_non_black) / len(all_non_black)
            else:
                return None

            # Convert to HSV, boost saturation and set 100% full brightness!
            h_val, s_val, v_val = colorsys.rgb_to_hsv(avg_r / 255.0, avg_g / 255.0, avg_b / 255.0)
            s_val = min(1.0, s_val * 1.4 + 0.20) if s_val > 0.04 else s_val
            v_val = 1.0 # Force 100% full bright!

            rgb_100 = tuple(int(round(c * 255)) for c in colorsys.hsv_to_rgb(h_val, s_val, v_val))
            return rgb_100

        l_c = analyze_region(0, w // 3)
        m_c = analyze_region(w // 3, 2 * (w // 3))
        r_c = analyze_region(2 * (w // 3), w)

        # Fallback resolution: if a zone is pure black, inherit the vibrant dominant color
        dominant = m_c or l_c or r_c or last_valid[1]
        l_res = l_c if l_c else dominant
        m_res = m_c if m_c else dominant
        r_res = r_c if r_c else dominant

        return (l_res, m_res, r_res)
    except Exception as e:
        logger.debug(f"Error extracting vibrant colors: {e}")
        return last_valid


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
        self._send_json({"version": "3.20.0", "connected": True, "device": "Thunderobot RGB Keyboard"})

    def do_DELETE(self):
        wallpaper_sync.on_chroma_session_stopped()
        self._send_json({"result": 0})


class WallpaperEngineSyncProvider:
    def __init__(self):
        self._server = None
        self._server_thread = None
        self._running = False

        # Live State
        self.is_connected = False
        self.last_frame_time = 0.0
        self.current_left = (219, 4, 74)
        self.current_middle = (219, 4, 74)
        self.current_right = (219, 4, 74)
        self.current_single = (219, 4, 74)

        # Active Wallpaper direct workshop frames cache
        self._last_active_file = ""
        self._cached_anim_frames = []
        self._anim_start_time = time.time()
        self._last_config_check = 0.0

        # Screen Grab cache (fallback)
        self._last_screen_poll = 0.0
        self._cached_screen_colors = ((219, 4, 74), (219, 4, 74), (219, 4, 74))

    def start(self):
        if self._running:
            return
        self._running = True
        self._reload_active_wallpaper_asset()

        def run_srv():
            try:
                socketserver.TCPServer.allow_reuse_address = True
                self._server = socketserver.TCPServer(("127.0.0.1", 12018), ChromaRESTHandler)
                logger.info("Chroma REST Server started on 127.0.0.1:12018")
                self._server.serve_forever()
            except Exception as e:
                logger.warning(f"Chroma REST port status: {e}")

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

    def on_chroma_session_stopped(self):
        self.is_connected = False

    def process_chroma_frame(self, path: str, data: dict):
        self.is_connected = True
        self.last_frame_time = time.time()

        effect = data.get("effect", "")
        param = data.get("param")
        if not param:
            return

        if effect == "CHROMA_CUSTOM" and isinstance(param, list) and len(param) > 0 and isinstance(param[0], list):
            rows = len(param)
            cols = len(param[0]) if rows > 0 else 0
            left_c, mid_c, right_c = [], [], []

            for r in range(rows):
                for c in range(cols):
                    val = param[r][c]
                    if val != 0:
                        rgb = bgr_int_to_rgb(val)
                        if (rgb[0] + rgb[1] + rgb[2]) > 25:
                            if c < cols // 3:
                                left_c.append(rgb)
                            elif c < 2 * (cols // 3):
                                mid_c.append(rgb)
                            else:
                                right_c.append(rgb)

            def boost_list(lst, default):
                if not lst:
                    return default
                avg_r = sum(x[0] for x in lst) / len(lst)
                avg_g = sum(x[1] for x in lst) / len(lst)
                avg_b = sum(x[2] for x in lst) / len(lst)
                h, s, v = colorsys.rgb_to_hsv(avg_r / 255.0, avg_g / 255.0, avg_b / 255.0)
                s = min(1.0, s * 1.4 + 0.20) if s > 0.04 else s
                return tuple(int(round(c * 255)) for c in colorsys.hsv_to_rgb(h, s, 1.0))

            if left_c or mid_c or right_c:
                self.current_middle = boost_list(mid_c or left_c or right_c, self.current_middle)
                self.current_left = boost_list(left_c or mid_c, self.current_left)
                self.current_right = boost_list(right_c or mid_c, self.current_right)
                self.current_single = self.current_middle

        elif effect == "CHROMA_STATIC" and isinstance(param, dict):
            rgb = bgr_int_to_rgb(param.get("color", 0))
            h, s, _ = colorsys.rgb_to_hsv(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
            boosted = tuple(int(round(c * 255)) for c in colorsys.hsv_to_rgb(h, min(1.0, s * 1.35 + 0.15), 1.0))
            self.current_single = self.current_left = self.current_middle = self.current_right = boosted

    def _reload_active_wallpaper_asset(self):
        """Reads active Wallpaper from Wallpaper Engine config and pre-analyzes frames."""
        try:
            if not os.path.exists(WE_CONFIG_PATH):
                return
            with open(WE_CONFIG_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)

            wp_file = None
            for user_key in d:
                if isinstance(d[user_key], dict) and "general" in d[user_key]:
                    wconf = d[user_key]["general"].get("wallpaperconfig", {})
                    sel = wconf.get("selectedwallpapers", {}).get("Monitor0", {})
                    if "file" in sel:
                        wp_file = sel["file"]
                        break

            if wp_file and wp_file != self._last_active_file:
                self._last_active_file = wp_file
                folder = os.path.dirname(wp_file)
                logger.info(f"Active Wallpaper detected: {folder}")

                # Check for preview.gif, preview.png, or video
                frames_loaded = []
                for cand in ["preview.gif", "preview.png", "preview.jpg"]:
                    p_path = os.path.join(folder, cand)
                    if os.path.exists(p_path):
                        im = Image.open(p_path)
                        if getattr(im, "is_animated", False):
                            for frame in ImageSequence.Iterator(im):
                                l, m, r = extract_vibrant_triplet(frame)
                                frames_loaded.append((l, m, r))
                        else:
                            l, m, r = extract_vibrant_triplet(im)
                            frames_loaded.append((l, m, r))
                        break

                if frames_loaded:
                    self._cached_anim_frames = frames_loaded
                    self._anim_start_time = time.time()
                    logger.info(f"Loaded {len(frames_loaded)} vibrant frames from active wallpaper!")
        except Exception as e:
            logger.debug(f"Error checking active wallpaper: {e}")

    def get_colors(self, is_single: bool = True):
        now = time.time()

        # 1. If Chroma REST stream from Wallpaper Engine is active
        if self.is_connected and (now - self.last_frame_time < 2.5):
            if is_single:
                return self.current_single, self.current_single, self.current_single
            return self.current_left, self.current_middle, self.current_right

        # 2. Check for active wallpaper changes every 4 seconds
        if now - self._last_config_check > 4.0:
            self._last_config_check = now
            self._reload_active_wallpaper_asset()

        # 3. Direct Active Wallpaper Workshop Frame Animation (Independent of foreground windows!)
        if self._cached_anim_frames:
            fps = 12.0 # Natural animated wallpaper cadence
            frame_idx = int((now - self._anim_start_time) * fps) % len(self._cached_anim_frames)
            l, m, r = self._cached_anim_frames[frame_idx]
            if is_single:
                return m, m, m
            return l, m, r

        # 4. Fallback: Fast Screen Grab with Peak Chromatic Energy Filter
        if now - self._last_screen_poll > 0.10:
            self._last_screen_poll = now
            try:
                img = ImageGrab.grab(bbox=None).resize((64, 32))
                self._cached_screen_colors = extract_vibrant_triplet(img, self._cached_screen_colors)
            except Exception:
                pass

        l, m, r = self._cached_screen_colors
        if is_single:
            return m, m, m
        return l, m, r


wallpaper_sync = WallpaperEngineSyncProvider()
