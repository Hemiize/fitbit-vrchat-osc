# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
"""Bluetooth LE unter Windows: Band finden, koppeln, Puls und Akkustand abonnieren, neu verbinden.

Verbindungsablauf wie HypeRate Android 1.0.15 (0x180D scannen -> verbinden -> 0x2A37 abonnieren), mit den
Korrekturen, die der App fehlen: Flags-Byte richtig auswerten, gezielt koppeln, automatisch neu verbinden.
Getestet mit TP-Link UB500 (Realtek RTL8761B).
"""
from __future__ import annotations

import asyncio
import time
import uuid

from bleak import BleakScanner
from winrt.windows.devices.bluetooth import BluetoothCacheMode, BluetoothConnectionStatus, BluetoothLEDevice
from winrt.windows.devices.bluetooth.genericattributeprofile import (
    GattCharacteristicProperties,
    GattCommunicationStatus,
)
from winrt.windows.devices.bluetooth.genericattributeprofile import (
    GattClientCharacteristicConfigurationDescriptorValue as CCCD,
)
from winrt.windows.devices.enumeration import DeviceInformation, DevicePairingKinds, DevicePairingProtectionLevel

from .log import log
from .protocol import BATTERY_LEVEL, BATTERY_SERVICE, HR_MEASUREMENT, HR_SERVICE

SCAN_WINDOW = 15
RECHECK_WINDOW = 10  # kurzer Scan, wenn das gekoppelte Band nicht antwortet
DIRECT_TIMEOUT = 20
STALE = 20  # Sekunden ohne Messwert bei "verbundenem" Band -> Verbindung gilt als tot
BATTERY_REFRESH = 600  # Akkustand neu lesen, wenn das Band ihn nicht von selbst meldet
REPAIR_AFTER = 3  # so oft darf die Direktverbindung scheitern, obwohl das Band sichtbar ist


def ble_address(dev) -> int:
    adv = dev.details.adv or dev.details.scan
    return adv.bluetooth_address


async def find_band(name_filter: str, window: float = SCAN_WINDOW, reject_other_names: bool = False):
    """Nach einem Gerät mit Heart-Rate-Dienst (oder passendem Namen) scannen. -> (BLEDevice, rssi) oder None.

    reject_other_names: Geräte, die einen Namen senden, der nicht passt, ignorieren (z. B. den Brustgurt des
    Nachbarn), damit die Kopplung nicht wegen eines fremden Geräts gelöst wird.
    """
    hit = asyncio.get_running_loop().create_future()
    want = (name_filter or "").lower()

    def cb(dev, adv):
        if hit.done():
            return
        name = (dev.name or adv.local_name or "").lower()
        has_hr = HR_SERVICE in [u.lower() for u in adv.service_uuids]
        name_ok = bool(want) and want in name
        if reject_other_names and want and name and not name_ok:
            return
        if has_hr or name_ok:
            hit.set_result((dev, adv.rssi))

    async with BleakScanner(cb, scanning_mode="active"):
        try:
            return await asyncio.wait_for(hit, window)
        except TimeoutError:
            return None


async def pair(address: int) -> bool:
    # Die Fitbit Air trennt ohne Kopplung nach ~20-30 s. Android koppelt beim ersten geschützten Zugriff
    # von selbst, Windows nur auf Anfrage – daher eigene Zeremonie, die jede Bestätigungsart annimmt.
    # Windows baut die Verbindung dafür selbst auf; eine parallele bleak-Verbindung blieb sonst hängen.
    dev = await BluetoothLEDevice.from_bluetooth_address_async(address)
    if dev is None:
        raise ConnectionError("Windows does not resolve the band at this address")
    try:
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
    finally:
        dev.close()


async def find_paired(name_filter: str) -> int | None:
    """Gekoppeltes Band in Windows suchen -> Bluetooth-Adresse als int."""
    if not name_filter:
        return None  # ohne Namensfilter passte jedes gekoppelte BLE-Gerät (Maus, Controller)
    sel = BluetoothLEDevice.get_device_selector_from_pairing_state(True)
    for info in await DeviceInformation.find_all_async_aqs_filter(sel):
        if name_filter.lower() in (info.name or "").lower():
            dev = await BluetoothLEDevice.from_id_async(info.id)
            if dev:
                try:
                    return dev.bluetooth_address
                finally:
                    dev.close()
    return None


async def unpair(address: int) -> None:
    dev = await BluetoothLEDevice.from_bluetooth_address_async(address)
    if dev:
        try:
            res = await dev.device_information.pairing.unpair_async()
            log("Pairing removed, status", int(res.status))
        finally:
            dev.close()


async def read_battery(char, bridge) -> None:
    res = await char.read_value_async(BluetoothCacheMode.UNCACHED)
    if res.status == GattCommunicationStatus.SUCCESS and res.value is not None:
        data = bytes(res.value)
        if data:
            bridge.set_battery(data[0])


async def setup_battery(dev, bridge, on_battery, subs: list):
    """Akkustand (0x180F/0x2A19) lesen und, wenn möglich, abonnieren. -> Kennlinie zum Nachlesen oder None."""
    res = await dev.get_gatt_services_for_uuid_async(uuid.UUID(BATTERY_SERVICE), BluetoothCacheMode.UNCACHED)
    if res.status != GattCommunicationStatus.SUCCESS or not len(res.services):
        log("Band reports no battery level")
        return None
    chars = await res.services[0].get_characteristics_for_uuid_async(uuid.UUID(BATTERY_LEVEL), BluetoothCacheMode.UNCACHED)
    if not len(chars.characteristics):
        log("Band reports no battery level")
        return None
    char = chars.characteristics[0]
    await read_battery(char, bridge)
    if char.characteristic_properties & GattCharacteristicProperties.NOTIFY:
        subs.append((char, char.add_value_changed(on_battery)))
        st = await char.write_client_characteristic_configuration_descriptor_async(CCCD.NOTIFY)
        if st == GattCommunicationStatus.SUCCESS:
            return None  # Band meldet Änderungen selbst
    return char


async def direct_session(address: int, bridge) -> None:
    """Gekoppeltes Band direkt über Windows ansprechen, ohne Scan. Kehrt zurück, wenn die Verbindung endet."""
    loop = asyncio.get_running_loop()
    lost = asyncio.Event()
    dev = await BluetoothLEDevice.from_bluetooth_address_async(address)
    if dev is None:
        raise ConnectionError("Windows does not know the paired band")

    def on_status(d, _):
        if d.connection_status == BluetoothConnectionStatus.DISCONNECTED:
            loop.call_soon_threadsafe(lost.set)

    def on_value(c, ev):
        loop.call_soon_threadsafe(bridge.handle, bytes(ev.characteristic_value))

    def on_battery(c, ev):
        data = bytes(ev.characteristic_value)
        if data:
            loop.call_soon_threadsafe(bridge.set_battery, data[0])

    status_token = dev.add_connection_status_changed(on_status)
    subs: list = []
    try:
        end = time.time() + DIRECT_TIMEOUT
        while True:
            res = await dev.get_gatt_services_for_uuid_async(uuid.UUID(HR_SERVICE), BluetoothCacheMode.UNCACHED)
            if res.status == GattCommunicationStatus.SUCCESS and len(res.services):
                break
            if time.time() > end:
                raise ConnectionError(f"paired band unreachable (GATT status {int(res.status)})")
            await asyncio.sleep(1)
        chars = await res.services[0].get_characteristics_for_uuid_async(uuid.UUID(HR_MEASUREMENT), BluetoothCacheMode.UNCACHED)
        if not len(chars.characteristics):
            raise ConnectionError("characteristic 0x2A37 missing")
        char = chars.characteristics[0]
        subs.append((char, char.add_value_changed(on_value)))
        st = await char.write_client_characteristic_configuration_descriptor_async(CCCD.NOTIFY)
        if st != GattCommunicationStatus.SUCCESS:
            raise ConnectionError(f"notifications refused (status {int(st)})")
        # Ein kurzer Abbruch während der Dienstsuche hat `lost` evtl. schon gesetzt; der zählt nicht mehr.
        lost.clear()
        if dev.connection_status != BluetoothConnectionStatus.CONNECTED:
            raise ConnectionError("band dropped the connection right after subscribing")
        bridge.set_connected(True)
        log("Heart rate subscribed")
        battery_char = None
        try:
            battery_char = await asyncio.wait_for(setup_battery(dev, bridge, on_battery, subs), 10)
        except Exception as e:
            log("Battery level not available:", type(e).__name__, e)
        next_battery = time.time() + BATTERY_REFRESH
        while True:
            try:
                await asyncio.wait_for(lost.wait(), 5)
                log("Band disconnected")
                break
            except TimeoutError:
                pass
            # Windows meldet nicht jeden Abriss; ohne Messwerte gilt die Verbindung trotzdem als tot
            if time.time() - bridge.seen > STALE:
                log(f"No data for {STALE} s although Windows still reports a connection, reconnecting")
                break
            if battery_char is not None and time.time() > next_battery:
                next_battery = time.time() + BATTERY_REFRESH
                try:
                    await asyncio.wait_for(read_battery(battery_char, bridge), 10)
                except Exception as e:
                    log("Battery read failed:", type(e).__name__, e)
    finally:
        bridge.set_connected(False)
        for c, token in subs:
            try:
                c.remove_value_changed(token)
            except Exception:
                pass
        dev.remove_connection_status_changed(status_token)
        dev.close()


async def paired_loop(address: int, bridge, cfg):
    """Mit dem gekoppelten Band verbunden bleiben. Gibt einen Scan-Treffer zurück, wenn neu gekoppelt werden muss.

    Die Kopplung wird nur noch gelöst, wenn das Band unter einer neuen Adresse wirbt oder trotz Sichtkontakt
    mehrmals nicht erreichbar ist. Ist es einfach außer Reichweite (Raum verlassen, Band lädt), bleibt sie bestehen.
    """
    fails = visible_fails = 0
    while True:
        try:
            await direct_session(address, bridge)
            fails = visible_fails = 0
            await asyncio.sleep(1)
            continue
        except Exception as e:
            fails += 1
            log("Direct connection failed:", type(e).__name__, e)
        found = await find_band(cfg.name, RECHECK_WINDOW, reject_other_names=True)
        if found is None:
            wait = min(5 * fails, 30)
            log(f"Band not in range, keeping the pairing, next try in {wait} s")
            await asyncio.sleep(wait)
            continue
        seen = ble_address(found[0])
        if seen != address:
            log("Band now advertises under a new address (%012X), removing the old pairing" % seen)
            await unpair(address)
            return found
        visible_fails += 1
        if visible_fails >= REPAIR_AFTER:
            log("Band is in range but the paired connection keeps failing, pairing again")
            await unpair(address)
            return found
        log("Band is in range, trying again")
        await asyncio.sleep(1)


async def ble_loop(bridge, cfg) -> None:
    pending = None  # Scan-Treffer, der als Nächstes gekoppelt wird
    while True:
        try:
            if pending is None:
                address = await find_paired(cfg.name)
                if address is not None:
                    log("Band is paired (%012X), connecting directly" % address)
                    pending = await paired_loop(address, bridge, cfg)
                    continue
                log("Scanning for band (is heart-rate sharing enabled on the band?)")
                pending = await find_band(cfg.name)
                if pending is None:
                    log("No band seen")
                    continue
            dev, rssi = pending
            pending = None
            log("Band seen:", dev.address, dev.name, "RSSI", rssi)
            address = ble_address(dev)
            log("Pairing with", dev.address)
            try:
                if not await pair(address):
                    raise ConnectionError("pairing failed")
            except Exception as e:
                log("Connection failed:", type(e).__name__, e)  # nächster Versuch über den Scan (Adresse kann wechseln)
                await asyncio.sleep(1)
                continue
            # Frisch gekoppelt: direkt mit dieser Adresse verbinden, egal unter welchem Namen Windows das Band führt
            pending = await paired_loop(address, bridge, cfg)
        except Exception as e:
            # Bluetooth-Stick abgezogen, Funk aus, WinRT-Fehler: nicht abstürzen, sondern später neu versuchen
            log("Bluetooth error:", type(e).__name__, e, "- retrying in 10 s")
            pending = None
            await asyncio.sleep(10)
