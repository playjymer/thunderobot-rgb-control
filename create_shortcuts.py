import os
import sys
import subprocess

def create_launchers():
    curr_dir = r"C:\Users\tbesa\.gemini\antigravity\scratch\thunderobot_rgb_control"
    main_py = os.path.join(curr_dir, "main.py")
    python_exe = sys.executable
    pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw_exe):
        pythonw_exe = python_exe

    # 1. Batch Launcher
    bat_path = os.path.join(curr_dir, "Launch_Thunderobot_RGB.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(f'@echo off\nstart "" "{pythonw_exe}" "{main_py}"\n')
    print("Created:", bat_path)

    # 2. Silent VBS Launcher
    vbs_path = os.path.join(curr_dir, "Launch_Silent.vbs")
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run """{pythonw_exe}"" ""{main_py}""", 0, False\n')
    print("Created:", vbs_path)

    # 3. Windows Desktop Shortcut (.lnk)
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    shortcut_path = os.path.join(desktop, "Thunderobot RGB Control.lnk")
    
    ps_lines = [
        "$WshShell = New-Object -comObject WScript.Shell",
        f'$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")',
        f'$Shortcut.TargetPath = "{pythonw_exe}"',
        f'$Shortcut.Arguments = \'"{main_py}"\'',
        f'$Shortcut.WorkingDirectory = "{curr_dir}"',
        '$Shortcut.Description = "Thunderobot 911s RGB Keyboard Control Suite"',
        '$Shortcut.Save()'
    ]
    ps_script = "\n".join(ps_lines)
    ps_file = os.path.join(curr_dir, "create_lnk.ps1")
    with open(ps_file, "w", encoding="utf-8") as f:
        f.write(ps_script)
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_file], check=True)
    if os.path.exists(ps_file):
        os.remove(ps_file)
    print("Created Desktop shortcut:", shortcut_path)

if __name__ == "__main__":
    create_launchers()
