# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
"""Start mit Windows über HKCU\\...\\Run (nur für den eigenen Benutzer, ohne Adminrechte) und Startbefehle."""
from __future__ import annotations

import os
import subprocess
import sys

from .config import app_dir, frozen

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "fitbit-osc"


def launch(*extra: str, console: bool = False) -> tuple[str, list[str]]:
    """Programm und Argumente, mit denen sich die Brücke selbst startet."""
    if frozen():
        return sys.executable, list(extra)
    scripts = os.path.join(app_dir(), ".venv", "Scripts")
    if not os.path.isdir(scripts):
        scripts = os.path.dirname(sys.executable)
    exe = os.path.join(scripts, "python.exe" if console else "pythonw.exe")
    if not os.path.exists(exe):
        exe = sys.executable
    return exe, [os.path.join(app_dir(), "hr_osc.py"), *extra]


def command_line() -> str:
    exe, args = launch("--tray")
    return subprocess.list2cmdline([exe, *args])


def get() -> str | None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            return winreg.QueryValueEx(k, VALUE)[0]
    except OSError:
        return None


def is_enabled() -> bool:
    return get() is not None


def enable() -> str:
    import winreg
    cmd = command_line()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
        winreg.SetValueEx(k, VALUE, 0, winreg.REG_SZ, cmd)
    return cmd


def disable() -> None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, VALUE)
    except FileNotFoundError:
        pass
