# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
"""SteamVR-Autostart: als Overlay-App mit Autolaunch anmelden (wie VRCOSC), und das Ende von SteamVR erkennen."""
from __future__ import annotations

import json
import os
import shlex
import subprocess

from .autostart import launch
from .config import app_dir, data_dir

APP_KEY = "fitbit-osc.heartrate-bridge"


def manifest_path() -> str:
    return os.path.join(data_dir(), "fitbit-osc.vrmanifest")


def build_manifest(console: bool = False, extra_args: str = "") -> dict:
    extra = shlex.split(extra_args, posix=False) if extra_args else []
    flags = ["--follow-steamvr"] + ([] if console else ["--tray"]) + extra
    exe, args = launch(*flags, console=console)
    return {
        "source": "builtin",
        "applications": [{
            "app_key": APP_KEY,
            "launch_type": "binary",
            "binary_path_windows": exe,
            "arguments": subprocess.list2cmdline(args),
            "working_directory": app_dir(),
            "is_dashboard_overlay": True,  # nur Overlay-Apps dürfen mit SteamVR automatisch starten
            "strings": {"en_us": {
                "name": "Fitbit Heart Rate -> VRChat",
                "description": "Reads the Fitbit Air heart rate over Bluetooth LE and sends it to VRChat via OSC"}},
        }],
    }


def register(console: bool = False, extra_args: str = "") -> tuple[bool, bool, dict]:
    """Manifest schreiben und bei OpenVR anmelden. OpenVR startet dafür kurz den vrserver, SteamVR muss nicht laufen."""
    import openvr
    manifest = build_manifest(console, extra_args)
    openvr.init(openvr.VRApplication_Utility)
    try:
        apps = openvr.VRApplications()
        path = manifest_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        apps.addApplicationManifest(path, False)
        apps.setApplicationAutoLaunch(APP_KEY, True)
        return bool(apps.isApplicationInstalled(APP_KEY)), bool(apps.getApplicationAutoLaunch(APP_KEY)), manifest
    finally:
        openvr.shutdown()


def unregister() -> bool:
    import openvr
    openvr.init(openvr.VRApplication_Utility)
    try:
        apps = openvr.VRApplications()
        for path in {manifest_path(), os.path.join(app_dir(), "fitbit-osc.vrmanifest")}:
            if os.path.exists(path):
                apps.removeApplicationManifest(path)
                os.remove(path)
        return not apps.isApplicationInstalled(APP_KEY)
    finally:
        openvr.shutdown()


def is_registered() -> bool:
    """Ohne OpenVR zu starten: Steam merkt sich den Autostart in config/vrappconfig/<app_key>.vrappconfig."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            steam = winreg.QueryValueEx(k, "SteamPath")[0]
        path = os.path.join(steam, "config", "vrappconfig", APP_KEY + ".vrappconfig")
        with open(path, encoding="utf-8") as f:
            return bool(json.load(f).get("autolaunch"))
    except (OSError, ValueError):
        return False


def vrserver_running() -> bool:
    # tasklist schreibt in OEM-Kodierung; nur nach dem ASCII-Namen suchen. CREATE_NO_WINDOW, weil unter
    # pythonw sonst alle 10 s kurz ein Konsolenfenster aufblitzt.
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq vrserver.exe", "/NH"], capture_output=True,
                         creationflags=subprocess.CREATE_NO_WINDOW).stdout
    return b"vrserver.exe" in out
