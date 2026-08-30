"""
Thunderobot RGB Control Suite Pro — Main Application Entry Point.
"""

import sys
import os
import ctypes
import threading
import time
import logging
import psutil

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from config import config
from driver import driver
from effects import engine
from wallpaper_sync import wallpaper_sync
from gui import MainWindow
from tray import TrayIcon

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("Main")

MUTEX_NAME = "Global\\ThunderobotRGBControlAppMutex"


def check_single_instance():
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    last_error = kernel32.GetLastError()
    ERROR_ALREADY_EXISTS = 183
    if last_error == ERROR_ALREADY_EXISTS:
        return None
    return mutex


def start_stock_app_interceptor(main_win_getter):
    """
    Monitors when Fn + / (Numpad) triggers stock Control Center, kills old CC, and lifts our GUI to front.
    """
    TARGET_PROCS = {
        "ledkeyboardsetting.exe",
        "controlcenter30.exe",
        "controlcenter.exe",
        "clevocontrolcenter.exe",
        "gamingcenter.exe",
        "hotkeyapp.exe",
    }

    def interceptor_loop():
        while True:
            time.sleep(0.4)
            if not config.get("fn_redirect", True):
                continue
            try:
                for proc in psutil.process_iter(["pid", "name"]):
                    name = proc.info["name"]
                    if name and name.lower() in TARGET_PROCS:
                        logger.info(f"Intercepted stock backlight app: {name}. Bringing our GUI to front...")
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        win = main_win_getter()
                        if win:
                            win.after(0, win._restore_and_focus)
            except Exception:
                pass

    t = threading.Thread(target=interceptor_loop, daemon=True)
    t.start()


def main():
    mutex = check_single_instance()
    if not mutex:
        logger.warning("Another instance of Thunderobot RGB Control is already running. Exiting.")
        sys.exit(0)

    engine.start()

    main_win = None

    def get_main_win():
        return main_win

    main_win = MainWindow(on_close_callback=lambda: None)

    callbacks = {
        "show_window": lambda: main_win.after(0, main_win._restore_and_focus),
        "toggle_power": lambda: (config.set("power", not engine.power), engine.update_params(power=not engine.power), main_win.after(0, main_win._sync_gui_with_engine)),
        "set_mode": lambda m: (config.set("mode", m), engine.update_params(mode=m), main_win.after(0, main_win._sync_gui_with_engine)),
        "set_brightness": lambda b: (config.set("brightness", b), engine.update_params(brightness=b), main_win.after(0, main_win._sync_gui_with_engine)),
        "exit_app": lambda: main_win.after(0, main_win.destroy),
    }

    tray = TrayIcon(callbacks)
    tray.start()

    def on_gui_request():
        main_win.after(0, main_win._restore_and_focus)

    engine.on_gui_requested = on_gui_request

    start_stock_app_interceptor(get_main_win)

    start_minimized = "--minimized" in sys.argv or config.get("minimize_to_tray", False)
    if start_minimized:
        main_win.withdraw()
    else:
        main_win.deiconify()

    logger.info("Application initialized successfully. Running mainloop...")
    main_win.mainloop()

    logger.info("Shutting down...")
    engine.stop()
    tray.stop()


if __name__ == "__main__":
    main()
