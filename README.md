# Fitbit Air → VRChat heart rate over OSC

Show your live heart rate on your VRChat avatar **without a phone app, without HypeRate/Pulsoid and without any
account**. A small Python program on your Windows PC reads the heart rate straight from the Fitbit Air over
Bluetooth LE and sends it to VRChat via OSC. It runs as a tray icon and can start automatically with SteamVR.

![Overview](docs/overview.svg)

## What you need

| | |
|---|---|
| **Band** | Fitbit Air (Google). Other bands that expose the standard Bluetooth *Heart Rate Service* (0x180D) should work too, but only the Fitbit Air was tested. |
| **Phone** | The **Google Health** app (Android or iPhone), only once, to switch on heart-rate sharing on the band. After that the phone can stay in another room. |
| **PC** | Windows 10/11, Python 3.11 or newer from [python.org](https://www.python.org/downloads/) (tick *Add python to PATH*). |
| **Bluetooth** | A real Bluetooth LE adapter. Tested and recommended: **TP-Link UB500** (Realtek RTL8761B, ~10 €). Cheap no-name sticks that identify as *CSR8510 A10* are counterfeits: they go deaf after ~15 s of scanning, cannot scan while paired and drop the connection. They do not work reliably. |
| **VRChat** | OSC enabled (Action menu → Options → OSC → Enabled) and an avatar with a heart-rate prefab, see [Avatar parameters](#avatar-parameters). |

## Install

1. Download this repository (green **Code** button → *Download ZIP*) and unpack it, e.g. to `C:\Tools\fitbit-osc`.
   Avoid a path inside *Program Files* or a cloud-synced folder.
2. Double-click **`install.bat`**. It creates a private Python environment in `.venv` and installs the dependencies
   (bleak, WinRT, pystray, pyopenvr). Takes about a minute and needs internet once.
3. Set up the band in Google Health, see the next section.
4. If you use **VRCOSC** with its HypeRate or Pulsoid module: disable that module, otherwise two programs
   write the same parameters.

## Set up the band in Google Health

The Fitbit Air only broadcasts its heart rate over Bluetooth while *heart-rate sharing* is switched on. This is a
setting stored **in the band itself**; the phone is only needed to flip it. Google documents the feature as
"Share your real-time heart rate with fitness equipment & apps"
([Google Health help](https://support.google.com/googlehealth/answer/14236705)); the bridge is just another piece
of "equipment" to the band.

**Android**

1. Open the **Google Health** app.
2. Top left, tap **Connections**, then your **Fitbit Air**.
3. Tap **Share heart rate**, then **Get started**.
4. On the same screen switch **Always visible** on.

**iPhone**

1. Open **Google Health**, tap the device icon, then your **Fitbit Air**.
2. Scroll to **Share heart rate** and switch **Always visible** on.

**What the two switches do**

| Setting | Effect |
|---|---|
| **Share heart rate** | The band starts advertising the Bluetooth *Heart Rate Service*. Without it the PC cannot see the band at all (`No band seen` in the log). |
| **Always visible** | The band keeps sharing on its own, also when Google Health is closed and after the phone goes to sleep. Without it the band only shares while Google Health is running a sharing session, so the PC loses it as soon as you close the app. Switch it on. |

**Good to know**

- **One listener at a time.** The band shares its heart rate with one device only. Close the HypeRate or Pulsoid
  app on the phone (or uninstall it) and do not connect the band to a treadmill or bike at the same time,
  otherwise the PC never gets a turn.
- **Pairing happens on the PC, not on the phone.** When the bridge sees the band for the first time, Windows pairs
  with it. The bridge accepts the pairing request itself; you do not have to click anything. The phone may show a
  hint like *"Select 'Fitbit Air' on DESKTOP-XXXX"* at that moment: that is the band waiting for the PC, and the
  bridge answers within a few seconds.
- **The band changes its Bluetooth address from time to time** (a privacy feature). The bridge handles that: if
  the paired band stays unreachable twice in a row (about 40 s), it removes the pairing and searches again. The
  address also changes when you switch *Share heart rate* off and on, which is the standard fix when pairing
  keeps failing.
- **0 BPM means the band is not on the wrist.** The band still sends values while lying on the desk, just zeros.
  The bridge logs this once and sends nothing to the avatar until a real pulse arrives.
- **Battery.** Google notes that real-time sharing costs battery, so expect the band to need charging a bit
  sooner with sharing permanently on.
- The band keeps syncing with the phone as usual; sharing only adds a second Bluetooth listener.

## Run

| | |
|---|---|
| **`start-tray.bat`** | Runs invisibly with a heart icon in the system tray. Grey = no band, red = heart rate flowing. Hover for the current BPM, right-click for *Open log* / *Quit*. |
| **`start.bat`** | Same, but in a console window so you can watch what happens. Add options after the name, e.g. `start.bat --chatbox`. |

![Tray icon](docs/tray.png)

### First run, step by step

Start `start.bat` once so you can see the log. With sharing on and the band on your wrist you should see this
within about 20 seconds:

```
Scanning for band (is heart-rate sharing enabled on the band?)
Band seen: 5D:DC:7E:7B:6E:3C Fitbit Air RSSI -52
Pairing with 5D:DC:7E:7B:6E:3C
Pairing request, kind 1 - accepting
Pairing status 0 (0 = paired)
Heart rate subscribed, sending OSC to 127.0.0.1:9000
BPM 72
```

![Console log](docs/console.png)

From then on the band is paired with Windows and every later start connects directly, without a scan
(`Band is paired (...), connecting directly`). If the band disconnects, the bridge reconnects on its own. If the
Bluetooth adapter is unplugged or the radio is switched off, it logs `Bluetooth error` and retries every 10 s
instead of exiting.

### Options

```
--chatbox            also show "♥ 72 BPM" in the VRChat chatbox every 3 s
--min 40 --max 200   range used for HRPercent / Normalised (default 0–255)
--ip / --port        OSC target, default 127.0.0.1:9000 (VRChat)
--name fitbit        part of the band's Bluetooth name (default "fitbit"); the scan accepts any 0x180D
                     device, but reconnecting to an already paired band on a later start goes by this name,
                     so pass e.g. --name polar for another brand
--demo               no band: send synthetic values, handy for testing the avatar
--tray               tray icon instead of console, log goes to fitbit-osc.log
--follow-steamvr     exit ~20 s after SteamVR closes (used by the SteamVR autostart)
```

## Start automatically with SteamVR

```
.venv\Scripts\python.exe register_steamvr.py
```

This registers the bridge as a SteamVR overlay application with autostart, the same mechanism VRCOSC and
other VR tools use. From then on SteamVR launches it (tray mode) and it quits itself shortly after SteamVR
closes. You can toggle it in SteamVR under *Settings → Startup/Shutdown → Choose startup overlay apps*.
Undo with `register_steamvr.py --remove`. If you move the folder, run the script again.
Extra options for the autostart go in like this: `register_steamvr.py --extra-args "--chatbox --max 200"`.

## Avatar parameters

The bridge sends several parameter families at once so most heart-rate prefabs work out of the box.
All addresses are `/avatar/parameters/<name>`.

| Name | Type | Value | Used by |
|---|---|---|---|
| `VRCOSC/Heartrate/Value` | int | BPM (0–255) | VRCOSC heart-rate prefab |
| `VRCOSC/Heartrate/Normalised` | float | 0…1 | VRCOSC |
| `VRCOSC/Heartrate/Units`, `Tens`, `Hundreds` | int | digits | VRCOSC |
| `VRCOSC/Heartrate/Enabled` | bool | band connected | VRCOSC |
| `HR` | int | BPM | HRtoVRChat_OSC style prefabs |
| `onesHR`, `tensHR`, `hundredsHR` | int | digits | HRtoVRChat_OSC |
| `HRPercent`, `FullHRPercent` | float | 0…1 / −1…1 | HRtoVRChat_OSC |
| `isHRConnected`, `isHRActive` | bool | status | HRtoVRChat_OSC |
| `isHRBeat`, `HeartBeatToggle` | bool | toggles with each heartbeat | HRtoVRChat_OSC |

If your prefab uses other names, edit `send_hr()` in `hr_osc.py`; it is a handful of lines.
Remember that many prefabs also have a menu toggle on the avatar that has to be switched on.

### No heart-rate prefab on your avatar yet?

The bridge works out of the box with the official **VRCOSC Heartrate prefab** (a number display with a
beating heart), made by VolcanicArts:

**[Download VRCOSC-Heartrate.unitypackage](https://vrcosc.com/assets/files/VRCOSC-Heartrate-44bc3d431ee04ea4fe13c84162417987.unitypackage)**
(from the [VRCOSC prefab downloads](https://vrcosc.com/docs/downloads#prefabs))

1. Install [VRCFury](https://vrcfury.com/download) in your avatar project (VRChat Creator Companion).
2. Install RED_SIM's free [Simple Counter Shader](https://www.patreon.com/posts/simple-counter-62864361), the prefab uses it for the digits.
3. Import the unitypackage, drag the `Heartrate` prefab onto your avatar (e.g. onto the chest bone) and upload.
4. In VRChat, switch the *Heartrate* toggle on in your avatar's expression menu.

The prefab only needs `VRCOSC/Heartrate/Value`, which the bridge sends. It is not included in this
repository because it is VolcanicArts' work; please get it from the link above.

Quick check without the band: `start.bat --demo` sends a synthetic pulse between 60 and 100 BPM, so you can
see whether the avatar reacts before you deal with Bluetooth.

## How it works

The connection sequence mirrors what the official HypeRate Android app does (scan for service 0x180D,
connect, enable notifications on characteristic 0x2A37), with three things the app gets wrong fixed:

- The heart-rate flags byte is evaluated correctly, so 16-bit values are read properly.
- The band is paired deliberately. Without pairing the Fitbit Air disconnects after 20–30 s.
  Android pairs implicitly on the first protected access, Windows only on request.
- Lost connections are re-established automatically, also when Windows fails to report the drop
  (no measurement for 20 s counts as disconnected).

Pairing is done through the Windows Bluetooth API only, with no second connection held by the script at the
same time; a parallel connection made pairing fail and left the band invisible.

## Troubleshooting

| Symptom | What to check |
|---|---|
| `No band seen` | *Share heart rate* and *Always visible* on in Google Health? Band on the wrist and awake (lift the arm)? HypeRate/Pulsoid app on the phone closed, no gym equipment connected? Adapter is a real Bluetooth LE adapter? |
| `No band seen`, but the phone shows the band is sharing | Switch *Share heart rate* off and on again; the band then advertises with a fresh address. Also check in Windows *Bluetooth & devices* whether an old *Fitbit Air* entry is left over and remove it. |
| `Pairing status 19` | The band dropped the connection during pairing. The bridge retries; if it keeps failing, toggle *Share heart rate* off and on. |
| `Pairing status 2` (NotPaired) | Pairing was refused. Make sure no other device holds the band (phone app, treadmill), toggle *Share heart rate* off and on, then restart the bridge. |
| `paired band unreachable (GATT status 1)` | The band is out of range or sleeping. After two attempts the bridge unpairs and scans again; nothing to do. If it happens with the band on your wrist next to the PC, the adapter is the problem. |
| `Band reports 0 BPM` | Put the band on; the optical sensor needs skin contact. The avatar keeps the last real value until then. |
| `Bluetooth error ... retrying in 10 s` | The Bluetooth adapter is gone or the radio is off. Plug it back in; the bridge continues on its own. |
| Values arrive but the avatar shows nothing | OSC enabled in VRChat? Prefab menu toggle on? Parameter names match (see table)? Test with `start.bat --demo`. |
| Connection drops every ~15 s | Almost always the Bluetooth adapter. Try a different USB port or an extension cable away from the PC case, or a better adapter. |
| Two bridges fight over the band | Only one instance runs at a time; a second start exits immediately. Check the SteamVR autostart isn't running next to a manual start. |

The log lives in `fitbit-osc.log` next to the script when running in tray mode (tray menu → *Open log*).

## License and credit

Apache License 2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE).

You may use, change and share this project, also commercially, **as long as you credit the author**:
keep the `NOTICE` file and mention **hemiize** with a link to this repository
(https://github.com/Hemiize/fitbit-vrchat-osc) in your README, release notes or the about/credits screen
of your app. Changed files must say that you changed them.

*Deutsch: Du darfst das Projekt nutzen, ändern und weitergeben, auch kommerziell, solange du
**hemiize** mit Link zu diesem Repository nennst und die `NOTICE`-Datei mitlieferst.*
