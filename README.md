# Fitbit Air → VRChat heart rate over OSC

Show your live heart rate on your VRChat avatar **without a phone app, without HypeRate/Pulsoid and without any
account**. A small Python program on your Windows PC reads the heart rate straight from the Fitbit Air over
Bluetooth LE and sends it to VRChat via OSC. It runs as a tray icon and can start automatically with SteamVR.

![Overview](docs/overview.svg)

*Deutsch: ausführliche Anleitung weiter unten → [Deutsche Anleitung](#deutsche-anleitung).*

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

## Deutsche Anleitung

### Was du brauchst

- **Fitbit Air** von Google. Andere Bänder mit dem Bluetooth-Standardprofil *Heart Rate Service* (0x180D) sollten
  auch gehen, getestet ist nur die Fitbit Air.
- **Handy mit der Google-Health-App**, nur einmal zum Einschalten der Puls-Freigabe am Band. Danach läuft alles
  ohne Handy, es muss nicht mal in der Nähe sein.
- **Windows-PC** mit Python 3.11 oder neuer von [python.org](https://www.python.org/downloads/)
  (bei der Installation *Add python to PATH* anhaken).
- **Echter Bluetooth-LE-Stick.** Getestet und empfohlen: **TP-Link UB500** (Realtek RTL8761B, ca. 10 €). Billige
  „5.0“-Sticks, die sich in Windows als *CSR8510 A10* melden, sind Nachbauten: Sie werden nach etwa 15 s Scannen
  taub, können nicht scannen, solange ein Gerät gekoppelt ist, und verlieren die Verbindung. Damit wird es nichts.
- **VRChat** mit eingeschaltetem OSC (Action-Menü → Options → OSC → Enabled) und einem Avatar mit Puls-Prefab,
  siehe [Avatar parameters](#avatar-parameters) oben.

### Installieren

1. Repository als ZIP laden (grüner **Code**-Knopf → *Download ZIP*), entpacken, z. B. nach `C:\Tools\fitbit-osc`.
   Nicht unter *Programme* und nicht in einen Cloud-Ordner.
2. **`install.bat`** doppelklicken. Legt eine eigene Python-Umgebung in `.venv` an und installiert die Pakete.
   Dauert etwa eine Minute, braucht einmal Internet.
3. Band in Google Health einrichten, nächster Abschnitt.
4. Nutzt du **VRCOSC** mit HypeRate- oder Pulsoid-Modul: das Modul abschalten, sonst schreiben zwei Programme
   dieselben Parameter.

### Band in Google Health einrichten

Die Fitbit Air sendet ihren Puls nur dann per Bluetooth, wenn die **Herzfrequenz-Freigabe** eingeschaltet ist.
Das ist eine Einstellung **im Band selbst**, das Handy dient nur zum Umschalten. Google beschreibt die Funktion
unter „Herzfrequenz in Echtzeit mit Fitnessgeräten und Apps teilen“
([Google-Health-Hilfe](https://support.google.com/googlehealth/answer/14236705?hl=de)); für das Band ist die
Brücke einfach so ein „Fitnessgerät“.

**Android**

1. **Google Health** öffnen.
2. Oben links auf **Verbindungen** tippen, dann auf die **Fitbit Air**.
3. **Herzfrequenz teilen** antippen, dann **Los geht's** (bzw. den Start-Knopf).
4. Auf demselben Bildschirm **Immer sichtbar** einschalten.

**iPhone**

1. **Google Health** öffnen, oben auf das Gerätesymbol, dann auf die **Fitbit Air**.
2. Zu **Herzfrequenz teilen** scrollen und **Immer sichtbar** einschalten.

**Was die beiden Schalter machen**

| Einstellung | Wirkung |
|---|---|
| **Herzfrequenz teilen** | Das Band fängt an, den Bluetooth-Dienst *Heart Rate* zu bewerben. Ohne das sieht der PC das Band überhaupt nicht (`No band seen` im Log). |
| **Immer sichtbar** | Das Band teilt dauerhaft von selbst, auch wenn Google Health zu ist und das Handy schläft. Ohne den Schalter teilt das Band nur, solange Google Health eine Freigabe-Sitzung laufen hat; sobald du die App schließt, verliert der PC es. Also an. |

**Gut zu wissen**

- **Nur ein Empfänger gleichzeitig.** Das Band teilt den Puls mit genau einem Gerät. HypeRate- oder Pulsoid-App
  auf dem Handy schließen (oder löschen) und das Band nicht gleichzeitig mit Laufband oder Ergometer verbinden,
  sonst kommt der PC nie dran.
- **Gekoppelt wird am PC, nicht am Handy.** Sieht die Brücke das Band zum ersten Mal, koppelt Windows damit. Die
  Kopplungsanfrage nimmt die Brücke selbst an, du musst nichts anklicken. Das Handy zeigt in dem Moment eventuell
  einen Hinweis wie *„Auf DESKTOP-XXXX Option ‚Fitbit Air‘ auswählen“*: Das ist das Band, das auf den PC wartet,
  und die Brücke antwortet innerhalb weniger Sekunden.
- **Das Band wechselt ab und zu seine Bluetooth-Adresse** (Datenschutzfunktion). Die Brücke kommt damit klar:
  Bleibt das gekoppelte Band zweimal hintereinander unerreichbar (rund 40 s), löst sie die Kopplung und sucht neu.
  Die Adresse wechselt auch, wenn du *Herzfrequenz teilen* aus- und wieder einschaltest. Das ist der
  Standard-Handgriff, wenn das Koppeln dauerhaft scheitert.
- **0 BPM heißt: Band liegt nicht am Arm.** Auf dem Tisch sendet das Band weiter, nur eben Nullen. Die Brücke
  schreibt das einmal ins Log und schickt dem Avatar nichts, bis wieder ein echter Puls kommt.
- **Akku.** Google weist darauf hin, dass das Teilen in Echtzeit Akku kostet; mit dauerhaft eingeschalteter
  Freigabe musst du also etwas früher laden.
- Das Band synchronisiert weiter ganz normal mit dem Handy; die Freigabe ist nur ein zweiter Bluetooth-Zuhörer.

### Starten

| | |
|---|---|
| **`start-tray.bat`** | Läuft unsichtbar mit Herz-Symbol im Tray. Grau = kein Band, rot = Puls kommt. Maus drüber zeigt den aktuellen Puls, Rechtsklick: *Open log* / *Quit*. |
| **`start.bat`** | Dasselbe mit Konsolenfenster, damit du zuschauen kannst. Optionen dahinter, z. B. `start.bat --chatbox`. |

**Der erste Start, Schritt für Schritt.** Nimm einmal `start.bat`, damit du das Log siehst. Mit eingeschalteter
Freigabe und dem Band am Arm sollte innerhalb von etwa 20 Sekunden das hier stehen:

```
Scanning for band (is heart-rate sharing enabled on the band?)
Band seen: 5D:DC:7E:7B:6E:3C Fitbit Air RSSI -52
Pairing with 5D:DC:7E:7B:6E:3C
Pairing request, kind 1 - accepting
Pairing status 0 (0 = paired)
Heart rate subscribed, sending OSC to 127.0.0.1:9000
BPM 72
```

Ab dann ist das Band mit Windows gekoppelt, und jeder spätere Start verbindet direkt ohne Scan
(`Band is paired (...), connecting directly`). Trennt das Band, verbindet die Brücke von selbst neu. Ziehst du den
Bluetooth-Stick ab oder schaltest den Funk aus, meldet sie `Bluetooth error` und versucht es alle 10 s wieder,
statt sich zu beenden.

**Optionen:** `--chatbox` (Puls zusätzlich in der VRChat-Chatbox), `--min 40 --max 200` (Bereich für
HRPercent/Normalised), `--ip`/`--port` (OSC-Ziel, Standard 127.0.0.1:9000), `--name polar` (Namensteil eines
anderen Bands; der Scan nimmt jedes 0x180D-Gerät, aber die Direktverbindung zum schon gekoppelten Band beim
nächsten Start läuft über den Namen), `--demo` (Testpuls ohne Band).

### Mit SteamVR starten

```
.venv\Scripts\python.exe register_steamvr.py
```

Meldet die Brücke als SteamVR-Overlay-App mit Autostart an, so wie es VRCOSC und andere VR-Tools machen. Ab dann
startet SteamVR sie selbst (Tray-Modus), und sie beendet sich etwa 20 s nach SteamVR von selbst. In SteamVR unter
*Einstellungen → Start/Beenden → Overlay-Apps beim Start auswählen* ein- und ausschaltbar. Rückgängig mit
`register_steamvr.py --remove`. Verschiebst du den Ordner, das Skript noch einmal ausführen.
Zusatzoptionen für den Autostart: `register_steamvr.py --extra-args "--chatbox --max 200"`.

### VRChat

OSC einschalten (Action-Menü → Options → OSC → Enabled), Avatar mit Puls-Prefab anziehen und dessen Menü-Schalter
an. Welche Parameter die Brücke sendet, steht oben unter [Avatar parameters](#avatar-parameters); die meisten
Puls-Prefabs (VRCOSC, HRtoVRChat_OSC) passen ohne Änderung.

Noch kein Puls-Prefab? Das offizielle
[VRCOSC-Heartrate-Prefab](https://vrcosc.com/assets/files/VRCOSC-Heartrate-44bc3d431ee04ea4fe13c84162417987.unitypackage)
passt direkt: [VRCFury](https://vrcfury.com/download) und RED_SIMs
[Simple Counter Shader](https://www.patreon.com/posts/simple-counter-62864361) ins Avatar-Projekt, Unitypackage
importieren, `Heartrate`-Prefab auf den Avatar (z. B. Brust) ziehen, hochladen, im Spiel den *Heartrate*-Schalter
im Avatar-Menü an. Ohne Band testen: `start.bat --demo` schickt einen künstlichen Puls zwischen 60 und 100.

### Fehlersuche

| Meldung / Symptom | Prüfen |
|---|---|
| `No band seen` | *Herzfrequenz teilen* und *Immer sichtbar* in Google Health an? Band am Arm und wach (Arm heben)? HypeRate/Pulsoid-App am Handy zu, kein Fitnessgerät verbunden? Stick ein echter Bluetooth-LE-Stick? |
| `No band seen`, obwohl das Handy „teilt“ anzeigt | *Herzfrequenz teilen* aus- und wieder einschalten, dann wirbt das Band mit frischer Adresse. In Windows unter *Bluetooth & Geräte* nachsehen, ob ein alter *Fitbit Air*-Eintrag übrig ist, und ihn entfernen. |
| `Pairing status 19` | Das Band hat während der Kopplung getrennt. Die Brücke versucht es erneut; klappt es dauerhaft nicht, *Herzfrequenz teilen* aus und an. |
| `Pairing status 2` (NotPaired) | Kopplung abgelehnt. Sicherstellen, dass kein anderes Gerät das Band hält (Handy-App, Laufband), *Herzfrequenz teilen* aus und an, Brücke neu starten. |
| `paired band unreachable (GATT status 1)` | Band außer Reichweite oder schläft. Nach zwei Versuchen entkoppelt die Brücke und scannt neu, nichts zu tun. Passiert das mit dem Band am Arm direkt neben dem PC, ist der Stick das Problem. |
| `Band reports 0 BPM` | Band anlegen, der Sensor braucht Hautkontakt. Der Avatar behält bis dahin den letzten echten Wert. |
| `Bluetooth error ... retrying in 10 s` | Stick weg oder Funk aus. Wieder einstecken, die Brücke macht von selbst weiter. |
| Werte kommen, Avatar zeigt nichts | OSC in VRChat an? Menü-Schalter des Prefabs an? Parameternamen passen (Tabelle oben)? Mit `start.bat --demo` testen. |
| Verbindung bricht alle ~15 s ab | Fast immer der Bluetooth-Stick. Anderen USB-Port oder ein Verlängerungskabel weg vom Gehäuse probieren, sonst besseren Stick. |
| Zwei Brücken streiten ums Band | Es läuft immer nur eine Instanz, ein zweiter Start beendet sich sofort. Prüfen, ob der SteamVR-Autostart neben einem Handstart läuft. |

Das Log liegt im Tray-Modus als `fitbit-osc.log` neben dem Skript (Tray-Menü → *Open log*).

## License and credit

Apache License 2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE).

You may use, change and share this project, also commercially, **as long as you credit the author**:
keep the `NOTICE` file and mention **hemiize** with a link to this repository
(https://github.com/Hemiize/fitbit-vrchat-osc) in your README, release notes or the about/credits screen
of your app. Changed files must say that you changed them.

*Deutsch: Du darfst das Projekt nutzen, ändern und weitergeben, auch kommerziell, solange du
**hemiize** mit Link zu diesem Repository nennst und die `NOTICE`-Datei mitlieferst.*
