"""
Thunderobot 911s Core (Clevo / Insyde DCHU) Keyboard Backlight Driver
Provides low-level control over keyboard RGB LEDs, zones, brightness, power state,
and custom color channel mapping / white balance calibration.
"""

import os
import sys
import ctypes
import struct
import logging

logger = logging.getLogger(__name__)

# Zones definition
ZONE_ALL = 0xF0
ZONE_LEFT = 0xF1
ZONE_MIDDLE = 0xF2
ZONE_RIGHT = 0xF3
ZONE_EXTRA = 0xF4

CMD_COLOR = 103    # 0x67: Set LED Color
CMD_CONTROL = 121  # 0x79: Set Brightness / Power / Mode
CMD_TIMEOUT = 39   # 0x27: Backlight sleep timer


class KeyboardDriver:
    def __init__(self, dll_path: str = None):
        self._dchu = None
        self._available = False
        self._last_brightness = 255
        self._is_on = True

        # Color mapping and channel gains
        self.channel_mapping = "BRG"  # "BRG", "BGR", "RGB", "RBG", "GRB", "GBR"
        self.gain_r = 1.0
        self.gain_g = 1.0
        self.gain_b = 1.0

        if dll_path is None:
            base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            cand = os.path.join(base_dir, "lib", "InsydeDCHU.dll")
            cand_direct = os.path.join(base_dir, "InsydeDCHU.dll")
            if os.path.exists(cand):
                dll_path = cand
            elif os.path.exists(cand_direct):
                dll_path = cand_direct
            else:
                for sys_path in [
                    r"C:\Program Files (x86)\ControlCenter\DCHU\InsydeDCHU.dll",
                    r"C:\Program Files (x86)\ControlCenter\AppInstall\InsydeDCHU.dll",
                ]:
                    if os.path.exists(sys_path):
                        dll_path = sys_path
                        break

        if dll_path and os.path.exists(dll_path):
            try:
                os.add_dll_directory(os.path.dirname(dll_path))
                self._dchu = ctypes.CDLL(dll_path)
                
                self._dchu.SetDCHU_Data.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
                self._dchu.SetDCHU_Data.restype = ctypes.c_int
                
                if hasattr(self._dchu, "GetDCHU_Data_Integer"):
                    self._dchu.GetDCHU_Data_Integer.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
                    self._dchu.GetDCHU_Data_Integer.restype = ctypes.c_int
                    
                self._available = True
                logger.info(f"Loaded InsydeDCHU driver from: {dll_path}")
            except Exception as e:
                logger.error(f"Failed to load InsydeDCHU DLL: {e}")
        else:
            logger.warning("InsydeDCHU.dll not found; running in simulated mode.")

    @property
    def is_available(self) -> bool:
        return self._available

    def set_calibration(self, mapping: str, gain_r: float = 1.0, gain_g: float = 1.0, gain_b: float = 1.0):
        self.channel_mapping = mapping.upper()
        self.gain_r = max(0.0, min(1.0, float(gain_r)))
        self.gain_g = max(0.0, min(1.0, float(gain_g)))
        self.gain_b = max(0.0, min(1.0, float(gain_b)))

    def _send_dchu(self, cmd: int, val: int) -> bool:
        if not self._available or not self._dchu:
            return False
        try:
            buf = struct.pack("<I", val & 0xFFFFFFFF)
            res = self._dchu.SetDCHU_Data(cmd, buf, 4)
            return res == cmd
        except Exception as e:
            logger.error(f"DCHU send error (cmd={cmd}, val=0x{val:08X}): {e}")
            return False

    def set_color(self, r: int, g: int, b: int, zone: int = ZONE_ALL) -> bool:
        """
        Set color for a specific zone or whole keyboard.
        Applies gain calibration and channel mapping.
        """
        # Apply gains
        r = max(0, min(255, int(r * self.gain_r)))
        g = max(0, min(255, int(g * self.gain_g)))
        b = max(0, min(255, int(b * self.gain_b)))

        # Map RGB components to EC bytes (byte2, byte1, byte0)
        mapping = self.channel_mapping
        if mapping == "BRG":       # Clevo Standard
            byte2, byte1, byte0 = b, r, g
        elif mapping == "BGR":
            byte2, byte1, byte0 = b, g, r
        elif mapping == "RGB":
            byte2, byte1, byte0 = r, g, b
        elif mapping == "RBG":
            byte2, byte1, byte0 = r, b, g
        elif mapping == "GRB":
            byte2, byte1, byte0 = g, r, b
        elif mapping == "GBR":
            byte2, byte1, byte0 = g, b, r
        else:
            byte2, byte1, byte0 = b, r, g

        val = ((zone & 0xFF) << 24) | ((byte2 & 0xFF) << 16) | ((byte1 & 0xFF) << 8) | (byte0 & 0xFF)
        return self._send_dchu(CMD_COLOR, val)

    def set_zones(self, left: tuple, middle: tuple, right: tuple, extra: tuple = None) -> bool:
        """
        Set individual RGB colors for Left, Middle, and Right zones.
        """
        ok1 = self.set_color(left[0], left[1], left[2], ZONE_LEFT)
        ok2 = self.set_color(middle[0], middle[1], middle[2], ZONE_MIDDLE)
        ok3 = self.set_color(right[0], right[1], right[2], ZONE_RIGHT)
        if extra:
            self.set_color(extra[0], extra[1], extra[2], ZONE_EXTRA)
        return ok1 and ok2 and ok3

    def set_brightness(self, level: int) -> bool:
        """
        Set keyboard backlight brightness (0 to 255).
        """
        level = max(0, min(255, int(level)))
        self._last_brightness = level
        val = 0x18000000 | ((level & 0xFF) << 8) | 0xFF
        return self._send_dchu(CMD_CONTROL, val)

    def set_power(self, on: bool) -> bool:
        """
        Turn keyboard backlight ON or OFF.
        """
        self._is_on = on
        if on:
            self._send_dchu(CMD_CONTROL, 0x22000001)
            return self.set_brightness(self._last_brightness if self._last_brightness > 0 else 255)
        else:
            self._send_dchu(CMD_CONTROL, 0x18000000)
            val = 0x18000000 | 0xFF
            return self._send_dchu(CMD_CONTROL, val)

    def set_timeout(self, minutes: int) -> bool:
        """
        Set keyboard backlight sleep timeout in minutes.
        """
        minutes = max(0, min(60, int(minutes)))
        val = minutes
        return self._send_dchu(CMD_TIMEOUT, val)


driver = KeyboardDriver()
