# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
# Registriert die Brücke als SteamVR-Overlay-App mit Autostart (oder entfernt sie wieder mit --remove).
# Schreibt fitbit-osc.vrmanifest mit den Pfaden dieses Ordners und meldet es über OpenVR an.
# SteamVR muss nicht laufen; OpenVR startet dafür kurz den vrserver.
# Dasselbe geht im Tray-Menü unter "Start with SteamVR".
import argparse
import sys

ap = argparse.ArgumentParser(description="Register the heart-rate bridge with SteamVR (autostart)")
ap.add_argument("--remove", action="store_true", help="remove the registration")
ap.add_argument("--console", action="store_true", help="start with a visible console instead of the tray icon")
ap.add_argument("--extra-args", default="", help="more options for the bridge, e.g. \"--chatbox --max 200\"")
args = ap.parse_args()

try:
    import openvr  # noqa: F401
except ImportError:
    sys.exit("pyopenvr missing: .venv\\Scripts\\pip install openvr")

from fitbit_osc import steamvr  # noqa: E402

if args.remove:
    print("Registration removed:", steamvr.unregister())
else:
    installed, auto, manifest = steamvr.register(args.console, args.extra_args)
    app = manifest["applications"][0]
    print("Registered:", installed, "| autostart:", auto)
    print("Starts:", app["binary_path_windows"], app["arguments"])
    print("Visible in SteamVR under Settings -> Startup/Shutdown -> Choose startup overlay apps.")
