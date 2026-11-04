import json
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


def test_autostart_roundtrip_in_a_test_key(monkeypatch):
    import winreg

    from fitbit_osc import autostart
    key = r"Software\fitbit-osc-test\Run"  # nicht der echte Run-Schlüssel
    monkeypatch.setattr(autostart, "RUN_KEY", key)
    try:
        assert not autostart.is_enabled()
        cmd = autostart.enable()
        assert autostart.is_enabled() and autostart.get() == cmd
        assert "--tray" in cmd and "hr_osc.py" in cmd
        autostart.disable()
        assert not autostart.is_enabled()
        autostart.disable()  # zweimal ist kein Fehler
    finally:
        for k in (key, r"Software\fitbit-osc-test"):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, k)
            except OSError:
                pass


def test_steamvr_manifest():
    from fitbit_osc import steamvr
    app = steamvr.build_manifest()["applications"][0]
    assert app["app_key"] == steamvr.APP_KEY and app["is_dashboard_overlay"] is True
    assert app["binary_path_windows"].lower().endswith("pythonw.exe")
    assert app["arguments"].endswith("--follow-steamvr --tray")
    console = steamvr.build_manifest(console=True, extra_args="--chatbox --max 200")["applications"][0]
    assert console["binary_path_windows"].lower().endswith("python.exe")
    assert "--tray" not in console["arguments"] and console["arguments"].endswith("--follow-steamvr --chatbox --max 200")
    json.dumps(steamvr.build_manifest())  # muss als JSON schreibbar sein


def test_is_registered_never_raises():
    from fitbit_osc import steamvr
    assert steamvr.is_registered() in (True, False)
