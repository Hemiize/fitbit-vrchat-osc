# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
# Puls der Fitbit Air per BLE lesen und per OSC an VRChat schicken – ohne HypeRate-Server.
# Startpunkt für start.bat, start-tray.bat, den SteamVR-Autostart und das .exe; der Code liegt in fitbit_osc/.
from fitbit_osc.app import main

if __name__ == "__main__":
    main()
