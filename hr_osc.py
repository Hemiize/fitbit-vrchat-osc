# Puls der Fitbit Air per BLE lesen und per OSC an VRChat schicken – ohne HypeRate-Server.
# Verbindungsablauf wie HypeRate Android 1.0.15 (0x180D scannen -> verbinden -> 0x2A37 abonnieren),
# mit den Korrekturen, die der App fehlen: Flags-Byte richtig auswerten, gezielt koppeln, automatisch neu verbinden.
# Getestet mit TP-Link UB500 (Realtek RTL8761B). Mit dem alten CSR8510-Nachbau lief es nur mit Funk-aus/an-Tricks.
import argparse, asyncio, ctypes, os, socket, struct, sys, threading, time, uuid
from bleak import BleakScanner
from winrt.windows.devices.enumeration import DeviceInformation, DevicePairingKinds, DevicePairingProtectionLevel
from winrt.windows.devices.bluetooth import BluetoothLEDevice, BluetoothCacheMode, BluetoothConnectionStatus
from winrt.windows.devices.bluetooth.genericattributeprofile import (
    GattClientCharacteristicConfigurationDescriptorValue as CCCD, GattCommunicationStatus)

HR_SVC = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEAS = "00002a37-0000-1000-8000-00805f9b34fb"
WINDOW = 15
DIRECT_TIMEOUT = 20

ap = argparse.ArgumentParser(description="Fitbit Air heart rate -> VRChat OSC")
ap.add_argument("--ip", default="127.0.0.1")
ap.add_argument("--port", type=int, default=9000)
ap.add_argument("--name", default="fitbit", help="part of the device name to prefer (any 0x180D device is accepted)")
ap.add_argument("--min", type=int, default=0, help="lower bound for HRPercent/Normalised")
ap.add_argument("--max", type=int, default=255, help="upper bound for HRPercent/Normalised")
ap.add_argument("--chatbox", action="store_true", help="also show the heart rate in the VRChat chatbox")
ap.add_argument("--demo", action="store_true", help="no band: send synthetic values (for testing)")
ap.add_argument("--follow-steamvr", action="store_true", help="exit once SteamVR (vrserver.exe) is no longer running")
ap.add_argument("--tray", action="store_true", help="run with a tray icon instead of a console, log to fitbit-osc.log")
args = ap.parse_args()

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fitbit-osc.log")
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
state = {"bpm": 0, "last": 0.0, "connected": False}
tray = {"icon": None, "images": {}}
stop_event = None  # asyncio.Event, in main() angelegt
main_loop = None

def log(*a):
    line = time.strftime("%H:%M:%S") + " " + " ".join(str(x) for x in a)
    if sys.stdout:  # unter pythonw gibt es keine Konsole
        print(line, flush=True)
    if args.tray:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")

# --- Tray --------------------------------------------------------------------------------------

def tray_set(connected: bool, text: str):
    icon = tray["icon"]
    if icon is None:
        return
    icon.icon = tray["images"]["on" if connected else "off"]
    icon.title = text

def run_tray():
    # pystray braucht den Hauptthread; asyncio läuft daneben in einem eigenen Thread
    import pystray
    from PIL import Image, ImageDraw
    def heart(color):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((4, 8, 34, 38), fill=color)
        d.ellipse((30, 8, 60, 38), fill=color)
        d.polygon([(6, 28), (58, 28), (32, 60)], fill=color)
        return img
    tray["images"] = {"on": heart((225, 45, 70, 255)), "off": heart((140, 140, 140, 255))}
    def quit_(icon, item):
        if main_loop and stop_event:
            main_loop.call_soon_threadsafe(stop_event.set)
        else:
            icon.stop()
    def open_log(icon, item):
        os.startfile(LOG_FILE)
    def status_text(item):
        return f"Heart rate: {state['bpm']} BPM" if state["connected"] and state["bpm"] else "No band connected"
    menu = pystray.Menu(
        pystray.MenuItem(status_text, None, enabled=False),
        pystray.MenuItem("Open log", open_log),
        pystray.MenuItem("Quit", quit_))
    icon = pystray.Icon("fitbit-osc", tray["images"]["off"], "Heart rate: searching for band", menu)
    tray["icon"] = icon
    def setup(i):
        i.visible = True  # mit eigenem setup blendet pystray das Symbol nicht selbst ein
        threading.Thread(target=run_asyncio, daemon=True).start()
    icon.run(setup=setup)

# --- OSC ---------------------------------------------------------------------------------------

def _pad(b: bytes) -> bytes:
    return b + b"\0" * (4 - len(b) % 4)

def osc(address: str, *values):
    tags, payload = ",", b""
    for v in values:
        if isinstance(v, bool):
            tags += "T" if v else "F"
        elif isinstance(v, int):
            tags += "i"; payload += struct.pack(">i", v)
        elif isinstance(v, float):
            tags += "f"; payload += struct.pack(">f", v)
        else:
            tags += "s"; payload += _pad(str(v).encode())
    sock.sendto(_pad(address.encode()) + _pad(tags.encode()) + payload, (args.ip, args.port))

def param(name, value):
    osc("/avatar/parameters/" + name, value)

def send_hr(bpm: int):
    pct = min(max((bpm - args.min) / max(args.max - args.min, 1), 0.0), 1.0)
    # VRCOSC-Heartrate-Prefab (auf ATL4S 11): hört auf VRCOSC/Heartrate/Value (Int 0-255),
    # die übrigen Namen schickt das VRCOSC-Modul ebenfalls
    param("VRCOSC/Heartrate/Value", min(bpm, 255))
    param("VRCOSC/Heartrate/Normalised", float(pct))
    param("VRCOSC/Heartrate/Units", bpm % 10)
    param("VRCOSC/Heartrate/Tens", bpm // 10 % 10)
    param("VRCOSC/Heartrate/Hundreds", bpm // 100 % 10)
    param("VRCOSC/Heartrate/Enabled", True)
    # Parameternamen wie HRtoVRChat_OSC – die nutzen viele andere Puls-Prefabs
    param("HR", bpm)
    param("onesHR", bpm % 10)
    param("tensHR", bpm // 10 % 10)
    param("hundredsHR", bpm // 100 % 10)
    param("HRPercent", float(pct))
    param("FullHRPercent", float(pct * 2 - 1))
    param("isHRActive", True)
    param("isHRConnected", True)

def send_disconnected():
    param("VRCOSC/Heartrate/Enabled", False)
    param("isHRConnected", False)
    param("isHRActive", False)
    tray_set(False, "Heart rate: no band connected")

async def beat_loop():
    # isHRBeat / HeartBeatToggle im Takt des Pulses umschalten
    toggle = False
    while True:
        bpm = state["bpm"]
        fresh = time.time() - state["last"] < 5
        if bpm and fresh:
            toggle = not toggle
            param("isHRBeat", toggle)
            param("HeartBeatToggle", toggle)
            await asyncio.sleep(30 / bpm)
        else:
            await asyncio.sleep(0.5)

async def chatbox_loop():
    # VRChat drosselt die Chatbox; alle 3 s reicht
    while True:
        await asyncio.sleep(3)
        if state["bpm"] and time.time() - state["last"] < 5:
            osc("/chatbox/input", f"❤ {state['bpm']} BPM", True, False)

# --- BLE ---------------------------------------------------------------------------------------

def on_hr(_, data: bytearray):
    # Bit 0 des Flags-Bytes: 0 = UINT8, 1 = UINT16 ab Offset 1 (HypeRate prüft hier fälschlich getProperties())
    bpm = int.from_bytes(data[1:3], "little") if data[0] & 1 else data[1]
    if bpm == 0:
        if state["bpm"] != 0 or not state.get("zero_logged"):
            log("Band reports 0 BPM (not on the wrist?), raw", bytes(data).hex())
            state["bpm"], state["zero_logged"] = 0, True
        return
    state["zero_logged"] = False
    if bpm != state["bpm"]:
        log("BPM", bpm)
        tray_set(True, f"Heart rate: {bpm} BPM")
    state["bpm"], state["last"] = bpm, time.time()
    send_hr(bpm)

async def find_band():
    hit = asyncio.get_running_loop().create_future()
    def cb(dev, adv):
        name = (dev.name or adv.local_name or "").lower()
        has_hr = HR_SVC in [u.lower() for u in adv.service_uuids]
        if not hit.done() and (has_hr or (args.name and args.name.lower() in name)):
            hit.set_result((dev, adv.rssi))
    async with BleakScanner(cb, scanning_mode="active"):
        try:
            return await asyncio.wait_for(hit, WINDOW)
        except asyncio.TimeoutError:
            return None

async def pair(address: int):
    # Die Fitbit Air trennt ohne Kopplung nach ~20-30 s. Android koppelt beim ersten geschützten Zugriff
    # von selbst, Windows nur auf Anfrage – daher eigene Zeremonie, die jede Bestätigungsart annimmt.
    # Windows baut die Verbindung dafür selbst auf; eine parallele bleak-Verbindung blieb sonst hängen.
    dev = await BluetoothLEDevice.from_bluetooth_address_async(address)
    if dev is None:
        raise ConnectionError("Windows does not resolve the band at this address")
    try:
        return await _pair(dev)
    finally:
        dev.close()

async def _pair(dev):
    pairing = dev.device_information.pairing
    if pairing.is_paired:
        return True
    custom = pairing.custom
    def on_req(sender, req):
        log("Pairing request, kind", int(req.pairing_kind), "- accepting")
        if req.pairing_kind == DevicePairingKinds.DISPLAY_PIN:
            log("PIN to confirm on the band/phone:", req.pin)
        req.accept()
    token = custom.add_pairing_requested(on_req)
    try:
        kinds = DevicePairingKinds.CONFIRM_ONLY | DevicePairingKinds.CONFIRM_PIN_MATCH | DevicePairingKinds.DISPLAY_PIN
        res = await custom.pair_async(kinds, DevicePairingProtectionLevel.ENCRYPTION)
        log("Pairing status", int(res.status), "(0 = paired)")
        return int(res.status) in (0, 3)  # Paired / AlreadyPaired
    finally:
        custom.remove_pairing_requested(token)

async def find_paired():
    # Gekoppelte Fitbit in Windows suchen -> Bluetooth-Adresse als int
    sel = BluetoothLEDevice.get_device_selector_from_pairing_state(True)
    for info in await DeviceInformation.find_all_async_aqs_filter(sel):
        if args.name.lower() in (info.name or "").lower():
            dev = await BluetoothLEDevice.from_id_async(info.id)
            if dev:
                return dev.bluetooth_address
    return None

async def unpair(address: int):
    dev = await BluetoothLEDevice.from_bluetooth_address_async(address)
    if dev:
        res = await dev.device_information.pairing.unpair_async()
        log("Pairing removed, status", int(res.status))
        dev.close()

async def direct_session(address: int):
    # Gekoppeltes Band direkt über Windows ansprechen, ohne Scan: Solange die Kopplung besteht, hält Windows
    # selbst eine Hintergrundverbindung offen, und der CSR-Dongle kann dann nicht mehr scannen.
    loop = asyncio.get_running_loop()
    lost = asyncio.Event()
    dev = await BluetoothLEDevice.from_bluetooth_address_async(address)
    if dev is None:
        raise ConnectionError("Windows does not know the paired band")
    def on_status(d, _):
        if d.connection_status == BluetoothConnectionStatus.DISCONNECTED:
            loop.call_soon_threadsafe(lost.set)
    def on_value(c, ev):
        data = bytearray(bytes(ev.characteristic_value))
        loop.call_soon_threadsafe(on_hr, None, data)
    status_token = dev.add_connection_status_changed(on_status)
    char, value_token = None, None
    try:
        end = time.time() + DIRECT_TIMEOUT
        while True:
            res = await dev.get_gatt_services_for_uuid_async(uuid.UUID(HR_SVC), BluetoothCacheMode.UNCACHED)
            if res.status == GattCommunicationStatus.SUCCESS and len(res.services):
                break
            if time.time() > end:
                raise ConnectionError(f"paired band unreachable (GATT status {int(res.status)})")
            await asyncio.sleep(1)
        chars = await res.services[0].get_characteristics_for_uuid_async(uuid.UUID(HR_MEAS), BluetoothCacheMode.UNCACHED)
        if not len(chars.characteristics):
            raise ConnectionError("characteristic 0x2A37 missing")
        char = chars.characteristics[0]
        value_token = char.add_value_changed(on_value)
        st = await char.write_client_characteristic_configuration_descriptor_async(CCCD.NOTIFY)
        if st != GattCommunicationStatus.SUCCESS:
            raise ConnectionError(f"notifications refused (status {int(st)})")
        state["connected"] = True
        log("Heart rate subscribed, sending OSC to", f"{args.ip}:{args.port}")
        await lost.wait()
        log("Band disconnected")
    finally:
        state["connected"] = False
        send_disconnected()
        if char is not None and value_token is not None:
            char.remove_value_changed(value_token)
        dev.remove_connection_status_changed(status_token)
        dev.close()

async def session(dev):
    # Scan-Treffer -> über Windows koppeln. Gibt True zurück, wenn das Band danach gekoppelt ist.
    adv = dev.details.adv or dev.details.scan
    address = adv.bluetooth_address
    log("Pairing with", dev.address)
    paired = await pair(address)
    if not paired:
        raise ConnectionError("pairing failed")
    return True

async def paired_loop(address: int):
    # So lange direkt verbinden, wie es klappt; zweimal hintereinander unerreichbar -> Kopplung lösen,
    # damit das Band eine neue Adresse nimmt und wieder über den Scan gefunden wird
    fails = 0
    while fails < 2:
        try:
            await direct_session(address)
            fails = 0
        except Exception as e:
            fails += 1
            log("Direct connection failed:", type(e).__name__, e)
        await asyncio.sleep(1)
    await unpair(address)

async def ble_loop():
    dev = None
    while True:
        address = await find_paired()
        if address is not None:
            log("Band is paired (%012X), connecting directly" % address)
            await paired_loop(address)
            dev = None
            continue
        if dev is None:
            log("Scanning for band (is heart-rate sharing enabled on the band?)")
            found = await find_band()
            if not found:
                log("No band seen")
                continue
            dev, rssi = found
            log("Band seen:", dev.address, dev.name, "RSSI", rssi)
        try:
            if await session(dev):
                dev = None  # nächste Runde läuft über die gekoppelte Direktverbindung
        except Exception as e:
            log("Connection failed:", type(e).__name__, e)
            dev = None  # nächster Versuch wieder über den Scan (Random-Adresse kann wechseln)
        await asyncio.sleep(1)

async def demo_loop():
    import math
    t0 = time.time()
    while True:
        on_hr(None, bytearray([0, int(80 + 20 * math.sin((time.time() - t0) / 5))]))
        await asyncio.sleep(1)

async def follow_steamvr():
    # Von SteamVR gestartet: SteamVR beendet Fremdprogramme nicht selbst, also schauen wir alle 10 s nach vrserver.exe
    import subprocess
    missing = 0
    while True:
        await asyncio.sleep(10)
        # tasklist schreibt in OEM-Kodierung; nur nach dem ASCII-Namen suchen
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq vrserver.exe", "/NH"], capture_output=True).stdout
        missing = 0 if b"vrserver.exe" in out else missing + 1
        if missing >= 2:
            log("SteamVR closed, bridge stops")
            return

async def main():
    global stop_event, main_loop
    stop_event = asyncio.Event()
    main_loop = asyncio.get_running_loop()
    send_disconnected()
    coros = [beat_loop(), demo_loop() if args.demo else ble_loop(), stop_event.wait()]
    if args.chatbox:
        coros.append(chatbox_loop())
    if args.follow_steamvr:
        coros.append(follow_steamvr())
    tasks = [asyncio.ensure_future(c) for c in coros]
    try:
        # Endet, sobald eine Aufgabe aufhört: Stop aus dem Tray, SteamVR weg oder ein Absturz
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            if not t.cancelled() and t.exception():
                log("Error:", type(t.exception()).__name__, t.exception())
    finally:
        for t in tasks:
            t.cancel()
        send_disconnected()

def run_asyncio():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        send_disconnected()
    finally:
        log("Stopped")
        if tray["icon"]:
            tray["icon"].stop()

def single_instance() -> bool:
    # Zweiter Start (z. B. von Hand neben dem SteamVR-Autostart) würde um das Band kämpfen
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW(None, False, "Local\\fitbit-osc-bridge")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS

if not single_instance():
    log("Already running, second instance exits")
    sys.exit(0)
if args.tray:
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " started in tray mode, arguments: " + " ".join(sys.argv[1:]) + "\n")
    run_tray()
else:
    run_asyncio()
