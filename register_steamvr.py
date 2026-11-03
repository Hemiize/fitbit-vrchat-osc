# Registriert die Brücke als SteamVR-Overlay-App mit Autostart (oder entfernt sie wieder mit --remove).
# Schreibt fitbit-osc.vrmanifest mit den Pfaden dieses Ordners und meldet es über OpenVR an.
# SteamVR muss nicht laufen; OpenVR startet dafür kurz den vrserver.
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "fitbit-osc.vrmanifest")
APP_KEY = "fitbit-osc.heartrate-bridge"

ap = argparse.ArgumentParser(description="Fitbit-Puls-Brücke bei SteamVR an-/abmelden")
ap.add_argument("--remove", action="store_true", help="Registrierung entfernen")
ap.add_argument("--console", action="store_true", help="mit sichtbarem Konsolenfenster statt Tray starten")
ap.add_argument("--extra-args", default="", help="weitere Argumente für hr_osc.py, z. B. \"--chatbox --max 200\"")
args = ap.parse_args()

try:
    import openvr
except ImportError:
    sys.exit("pyopenvr fehlt: .venv\\Scripts\\pip install openvr")

pythonw = os.path.join(HERE, ".venv", "Scripts", "python.exe" if args.console else "pythonw.exe")
if not os.path.exists(pythonw):
    sys.exit(f"{pythonw} nicht gefunden – erst install.bat ausführen")

manifest = {
    "source": "builtin",
    "applications": [{
        "app_key": APP_KEY,
        "launch_type": "binary",
        "binary_path_windows": pythonw,
        "arguments": ("hr_osc.py --follow-steamvr " + ("" if args.console else "--tray ") + args.extra_args).strip(),
        "working_directory": HERE,
        "is_dashboard_overlay": True,  # nur Overlay-Apps dürfen mit SteamVR automatisch starten
        "strings": {"en_us": {
            "name": "Fitbit Heart Rate -> VRChat",
            "description": "Reads the Fitbit Air heart rate over Bluetooth LE and sends it to VRChat via OSC"}},
    }],
}

openvr.init(openvr.VRApplication_Utility)
try:
    apps = openvr.VRApplications()
    if args.remove:
        if os.path.exists(MANIFEST):
            apps.removeApplicationManifest(MANIFEST)
            os.remove(MANIFEST)
        print("Registrierung entfernt:", not apps.isApplicationInstalled(APP_KEY))
    else:
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        apps.addApplicationManifest(MANIFEST, False)
        apps.setApplicationAutoLaunch(APP_KEY, True)
        print("Registriert:", apps.isApplicationInstalled(APP_KEY), "| Autostart:", bool(apps.getApplicationAutoLaunch(APP_KEY)))
        print("Start:", pythonw, manifest["applications"][0]["arguments"])
        print("In SteamVR unter Einstellungen -> Start/Beenden -> Overlay-Apps beim Start auswählen sichtbar.")
finally:
    openvr.shutdown()
