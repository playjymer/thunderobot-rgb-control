"""
Thunderobot RGB Keyboard Suite Pro - Main Entry Point.
Manages Single Instance Mutex, System Tray, GUI lifecycle,
and Automatic Interception of Fn + / (Stock Control Center).
"""

import sys
import os
import ctypes
from ctypes import wintypes
import threading
import time
import logging
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ThunderobotRGB")

MUTEX_NAME = "Global\\ThunderobotRGBControlAppMutex"


def acquire_mutex():
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    last_error = kernel32.GetLastError()
    ERROR_ALREADY_EXISTS = 183
    if last_error == ERROR_ALREADY_EXISTS:
        return None
    return mutex


def start_stock_app_interceptor(on_intercept_callback):
    """
    Watches for the stock Clevo/Thunderobot Control Center / LedKeyboardSetting
    process launched by Fn + / and instantly replaces it with our application!
    """
    def interceptor_loop():
        target_procs = {"ledkeyboardsetting.exe", "controlcenter30.exe", "controlcenter.exe"}
        while True:
            time.sleep(0.3)
            try:
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        pname = proc.info['name'].lower()
                        if pname in target_procs:
                            logger.info(f"Intercepted stock app: {pname} (PID {proc.info['pid']})")
                            proc.terminate()
                            on_intercept_callback()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except Exception:
                pass

    t = threading.Thread(target=interceptor_loop, daemon=True)
    t.start()


def main():
    mutex = acquire_mutex()
    if not mutex:
        logger.warning("Another instance of Thunderobot RGB Control is already running.")
        sys.exit(0)

    start_minimized = ("--minimized" in sys.argv)

    from driver import driver
    from config import config
    from effects import engine
    from gui import MainWindow
    from tray import TrayIcon

    engine.start()

    window_ref = [None]

    def show_window_safe():
        if window_ref[0]:
            try:
                window_ref[0].after(0, _show_window_main)
            except Exception:
                pass

    def _show_window_main():
        if window_ref[0]:
            win = window_ref[0]
            win.deiconify()
            win.lift()
            win.attributes("-topmost", True)
            win.after(150, lambda: win.attributes("-topmost", False))
            win.focus_force()

    def toggle_power():
        new_state = not config.get("power", True)
        config.set("power", new_state)
        engine.update_params(power=new_state)
        driver.set_power(new_state)
        if window_ref[0]:
            try:
                window_ref[0].power_switch.select() if new_state else window_ref[0].power_switch.deselect()
            except Exception:
                pass

    def set_mode(mode_name):
        config.set("mode", mode_name)
        engine.update_params(mode=mode_name)
        if window_ref[0]:
            try:
                window_ref[0].mode_var.set(mode_name)
                window_ref[0]._update_mode_description()
            except Exception:
                pass

    def set_brightness(b_val):
        config.set("brightness", b_val)
        engine.update_params(brightness=b_val)
        if window_ref[0]:
            try:
                window_ref[0].bright_slider.set(b_val)
                window_ref[0].bright_lbl.configure(text=f"{int(b_val/2.55)}%")
            except Exception:
                pass

    def exit_application():
        logger.info("Exiting application...")
        engine.stop()
        if window_ref[0]:
            window_ref[0].destroy()
        sys.exit(0)

    app_callbacks = {
        "show_window": show_window_safe,
        "toggle_power": toggle_power,
        "set_mode": set_mode,
        "set_brightness": set_brightness,
        "exit_app": exit_application,
    }

    tray = TrayIcon(app_callbacks)
    tray.start()

    # Start background stock app interceptor for Fn + /
    start_stock_app_interceptor(show_window_safe)

    app = MainWindow(on_close_callback=exit_application)
    window_ref[0] = app

    if start_minimized:
        app.withdraw()

    try:
        app.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        tray.stop()


if __name__ == "__main__":
    main()
