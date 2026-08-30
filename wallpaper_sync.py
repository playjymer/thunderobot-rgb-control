"""
Wallpaper Engine RGB Sync Provider & Plugin Bridge Installer for Thunderobot RGB Keyboard.
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
import struct

logger = logging.getLogger(__name__)


class IMAGE_DOS_HEADER(ctypes.Structure):
    _fields_ = [
        ("e_magic", ctypes.c_uint16),
        ("e_cblp", ctypes.c_uint16),
        ("e_cp", ctypes.c_uint16),
        ("e_crlc", ctypes.c_uint16),
        ("e_cparhdr", ctypes.c_uint16),
        ("e_minalloc", ctypes.c_uint16),
        ("e_maxalloc", ctypes.c_uint16),
        ("e_ss", ctypes.c_uint16),
        ("e_sp", ctypes.c_uint16),
        ("e_csum", ctypes.c_uint16),
        ("e_ip", ctypes.c_uint16),
        ("e_cs", ctypes.c_uint16),
        ("e_lfarlc", ctypes.c_uint16),
        ("e_ovno", ctypes.c_uint16),
        ("e_res", ctypes.c_uint16 * 4),
        ("e_oemid", ctypes.c_uint16),
        ("e_oeminfo", ctypes.c_uint16),
        ("e_res2", ctypes.c_uint16 * 10),
        ("e_lfanew", ctypes.c_uint32),
    ]

class IMAGE_FILE_HEADER(ctypes.Structure):
    _fields_ = [
        ("Machine", ctypes.c_uint16),
        ("NumberOfSections", ctypes.c_uint16),
        ("TimeDateStamp", ctypes.c_uint32),
        ("PointerToSymbolTable", ctypes.c_uint32),
        ("NumberOfSymbols", ctypes.c_uint32),
        ("SizeOfOptionalHeader", ctypes.c_uint16),
        ("Characteristics", ctypes.c_uint16),
    ]

class IMAGE_DATA_DIRECTORY(ctypes.Structure):
    _fields_ = [
        ("VirtualAddress", ctypes.c_uint32),
        ("Size", ctypes.c_uint32),
    ]

class IMAGE_OPTIONAL_HEADER64(ctypes.Structure):
    _fields_ = [
        ("Magic", ctypes.c_uint16),
        ("MajorLinkerVersion", ctypes.c_uint8),
        ("MinorLinkerVersion", ctypes.c_uint8),
        ("SizeOfCode", ctypes.c_uint32),
        ("SizeOfInitializedData", ctypes.c_uint32),
        ("SizeOfUninitializedData", ctypes.c_uint32),
        ("AddressOfEntryPoint", ctypes.c_uint32),
        ("BaseOfCode", ctypes.c_uint32),
        ("ImageBase", ctypes.c_uint64),
        ("SectionAlignment", ctypes.c_uint32),
        ("FileAlignment", ctypes.c_uint32),
        ("MajorOperatingSystemVersion", ctypes.c_uint16),
        ("MinorOperatingSystemVersion", ctypes.c_uint16),
        ("MajorImageVersion", ctypes.c_uint16),
        ("MinorImageVersion", ctypes.c_uint16),
        ("MajorSubsystemVersion", ctypes.c_uint16),
        ("MinorSubsystemVersion", ctypes.c_uint16),
        ("Win32VersionValue", ctypes.c_uint32),
        ("SizeOfImage", ctypes.c_uint32),
        ("SizeOfHeaders", ctypes.c_uint32),
        ("CheckSum", ctypes.c_uint32),
        ("Subsystem", ctypes.c_uint16),
        ("DllCharacteristics", ctypes.c_uint16),
        ("SizeOfStackReserve", ctypes.c_uint64),
        ("SizeOfStackCommit", ctypes.c_uint64),
        ("SizeOfHeapReserve", ctypes.c_uint64),
        ("SizeOfHeapCommit", ctypes.c_uint64),
        ("LoaderFlags", ctypes.c_uint32),
        ("NumberOfRvaAndSizes", ctypes.c_uint32),
        ("DataDirectory", IMAGE_DATA_DIRECTORY * 16),
    ]

class IMAGE_SECTION_HEADER(ctypes.Structure):
    _fields_ = [
        ("Name", ctypes.c_char * 8),
        ("VirtualSize", ctypes.c_uint32),
        ("VirtualAddress", ctypes.c_uint32),
        ("SizeOfRawData", ctypes.c_uint32),
        ("PointerToRawData", ctypes.c_uint32),
        ("PointerToRelocations", ctypes.c_uint32),
        ("PointerToLinenumbers", ctypes.c_uint32),
        ("NumberOfRelocations", ctypes.c_uint16),
        ("NumberOfLinenumbers", ctypes.c_uint16),
        ("Characteristics", ctypes.c_uint32),
    ]

class IMAGE_EXPORT_DIRECTORY(ctypes.Structure):
    _fields_ = [
        ("Characteristics", ctypes.c_uint32),
        ("TimeDateStamp", ctypes.c_uint32),
        ("MajorVersion", ctypes.c_uint16),
        ("MinorVersion", ctypes.c_uint16),
        ("Name", ctypes.c_uint32),
        ("Base", ctypes.c_uint32),
        ("NumberOfFunctions", ctypes.c_uint32),
        ("NumberOfNames", ctypes.c_uint32),
        ("AddressOfFunctions", ctypes.c_uint32),
        ("AddressOfNames", ctypes.c_uint32),
        ("AddressOfNameOrdinals", ctypes.c_uint32),
    ]


def build_and_install_wallpaper_engine_bridge():
    """Generates native 64-bit bridge DLL and installs it directly into Wallpaper Engine."""
    target_dirs = [
        r"C:\Program Files (x86)\Steam\steamapps\common\wallpaper_engine",
        r"C:\Program Files (x86)\Steam\steamapps\common\wallpaper_engine\bin",
        r"C:\Program Files (x86)\Steam\steamapps\common\wallpaper_engine\plugins\led",
        os.path.dirname(os.path.abspath(__file__))
    ]

    sec_align = 0x1000
    file_align = 0x200

    export_names = sorted([
        "CreateChromaLinkEffect",
        "CreateEffect",
        "CreateHeadsetEffect",
        "CreateKeyboardEffect",
        "CreateKeypadEffect",
        "CreateMouseEffect",
        "CreateMousepadEffect",
        "DeleteEffect",
        "Init",
        "QueryDevice",
        "RegisterEventNotification",
        "SetEffect",
        "UnInit",
        "UnregisterEventNotification"
    ])

    code_per_func = b"\x31\xc0\xc3\xcc"
    text_data = b"".join(code_per_func for _ in export_names)
    text_data += b"\xb8\x01\x00\x00\x00\xc3"
    dllmain_offset = len(text_data) - 6

    rva_text = sec_align
    rva_edata = sec_align * 2
    num_exp = len(export_names)

    eat = bytearray()
    for i in range(num_exp):
        func_rva = rva_text + (i * len(code_per_func))
        eat += struct.pack("<I", func_rva)

    edata_hdr_size = ctypes.sizeof(IMAGE_EXPORT_DIRECTORY)
    eat_offset = edata_hdr_size
    npt_offset = eat_offset + len(eat)
    ot_offset = npt_offset + (num_exp * 4)
    names_offset = ot_offset + (num_exp * 2)

    names_buf = bytearray()
    npt = bytearray()
    ot = bytearray()

    dll_name = "RzChromaSDK64.dll\x00".encode('ascii')
    dll_name_rva = rva_edata + names_offset
    names_buf += dll_name

    for i, name in enumerate(export_names):
        cur_name_rva = rva_edata + names_offset + len(names_buf)
        npt += struct.pack("<I", cur_name_rva)
        ot += struct.pack("<H", i)
        names_buf += (name + "\x00").encode('ascii')

    exp_dir = IMAGE_EXPORT_DIRECTORY()
    exp_dir.Name = dll_name_rva
    exp_dir.Base = 1
    exp_dir.NumberOfFunctions = num_exp
    exp_dir.NumberOfNames = num_exp
    exp_dir.AddressOfFunctions = rva_edata + eat_offset
    exp_dir.AddressOfNames = rva_edata + npt_offset
    exp_dir.AddressOfNameOrdinals = rva_edata + ot_offset

    edata_data = bytes(exp_dir) + bytes(eat) + bytes(npt) + bytes(ot) + bytes(names_buf)

    def align_up(val, alignment):
        return (val + alignment - 1) & ~(alignment - 1)

    text_raw_size = align_up(len(text_data), file_align)
    edata_raw_size = align_up(len(edata_data), file_align)

    text_file_bytes = text_data.ljust(text_raw_size, b"\x00")
    edata_file_bytes = edata_data.ljust(edata_raw_size, b"\x00")

    headers_size = align_up(0x40 + 0x40 + 4 + ctypes.sizeof(IMAGE_FILE_HEADER) + ctypes.sizeof(IMAGE_OPTIONAL_HEADER64) + 2 * ctypes.sizeof(IMAGE_SECTION_HEADER), file_align)
    image_size = align_up(rva_edata + len(edata_data), sec_align)

    dos = IMAGE_DOS_HEADER()
    dos.e_magic = 0x5A4D
    dos.e_lfanew = 0x80

    dos_bytes = bytes(dos).ljust(0x80, b"\x00")
    pe_sig = b"PE\x00\x00"

    fh = IMAGE_FILE_HEADER()
    fh.Machine = 0x8664
    fh.NumberOfSections = 2
    fh.TimeDateStamp = 0x66D00000
    fh.SizeOfOptionalHeader = ctypes.sizeof(IMAGE_OPTIONAL_HEADER64)
    fh.Characteristics = 0x2022

    opt = IMAGE_OPTIONAL_HEADER64()
    opt.Magic = 0x20B
    opt.MajorLinkerVersion = 14
    opt.SizeOfCode = text_raw_size
    opt.SizeOfInitializedData = edata_raw_size
    opt.AddressOfEntryPoint = rva_text + dllmain_offset
    opt.BaseOfCode = rva_text
    opt.ImageBase = 0x180000000
    opt.SectionAlignment = sec_align
    opt.FileAlignment = file_align
    opt.MajorOperatingSystemVersion = 6
    opt.MajorSubsystemVersion = 6
    opt.SizeOfImage = image_size
    opt.SizeOfHeaders = headers_size
    opt.Subsystem = 2
    opt.DllCharacteristics = 0x8160
    opt.SizeOfStackReserve = 0x100000
    opt.SizeOfStackCommit = 0x1000
    opt.SizeOfHeapReserve = 0x100000
    opt.SizeOfHeapCommit = 0x1000
    opt.NumberOfRvaAndSizes = 16
    opt.DataDirectory[0].VirtualAddress = rva_edata
    opt.DataDirectory[0].Size = len(edata_data)

    sec_text = IMAGE_SECTION_HEADER()
    sec_text.Name = b".text\x00\x00\x00"
    sec_text.VirtualSize = len(text_data)
    sec_text.VirtualAddress = rva_text
    sec_text.SizeOfRawData = text_raw_size
    sec_text.PointerToRawData = headers_size
    sec_text.Characteristics = 0x60000020

    sec_edata = IMAGE_SECTION_HEADER()
    sec_edata.Name = b".edata\x00\x00"
    sec_edata.VirtualSize = len(edata_data)
    sec_edata.VirtualAddress = rva_edata
    sec_edata.SizeOfRawData = edata_raw_size
    sec_edata.PointerToRawData = headers_size + text_raw_size
    sec_edata.Characteristics = 0x40000040

    headers_bytes = (dos_bytes + pe_sig + bytes(fh) + bytes(opt) + bytes(sec_text) + bytes(sec_edata)).ljust(headers_size, b"\x00")
    full_dll = headers_bytes + text_file_bytes + edata_file_bytes

    installed_count = 0
    for d in target_dirs:
        if os.path.exists(d):
            try:
                dest = os.path.join(d, "RzChromaSDK64.dll")
                with open(dest, "wb") as f:
                    f.write(full_dll)
                installed_count += 1
                logger.info(f"Installed native Chroma bridge DLL to: {dest}")
            except Exception as e:
                logger.warning(f"Could not write DLL to {d}: {e}")

    for root_key, sub_path in [
        (winreg.HKEY_CURRENT_USER, r"Software\Razer\ChromaSDK"),
        (winreg.HKEY_CURRENT_USER, r"Software\Razer Chroma SDK"),
        (winreg.HKEY_CURRENT_USER, r"Software\Razer Chroma SDK\Apps"),
    ]:
        try:
            k = winreg.CreateKey(root_key, sub_path)
            winreg.SetValueEx(k, "RESTURI", 0, winreg.REG_SZ, "http://127.0.0.1:12018/razer/chromasdk")
            winreg.SetValueEx(k, "Connected", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(k, "Installed", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(k)
        except Exception:
            pass

    return installed_count > 0


def bgr_int_to_rgb(val: int):
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
        
        self.is_connected = False
        self.last_frame_time = 0.0
        self.current_left = (0, 180, 255)
        self.current_middle = (0, 180, 255)
        self.current_right = (0, 180, 255)
        self.current_single = (0, 180, 255)
        
        self._last_screen_grab = 0.0
        self._desktop_cache = [(0, 180, 255), (0, 180, 255), (0, 180, 255)]

    def start(self):
        if self._running:
            return
        self._running = True
        build_and_install_wallpaper_engine_bridge()
        
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
