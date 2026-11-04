# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
"""Reine Funktionen ohne Bluetooth: Pulspakete lesen, OSC-Nachrichten bauen, Avatar-Parameter berechnen."""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

HR_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"

# Parameter, die "Puls kommt gerade" bzw. "Band verbunden" anzeigen
ACTIVE_PARAMS = ("VRCOSC/Heartrate/Enabled", "isHRActive")
CONNECTED_PARAM = "isHRConnected"
BATTERY_PARAM = "HRBattery"


@dataclass
class HrMeasurement:
    bpm: int
    contact: bool | None = None  # None: das Band meldet keinen Hautkontakt-Status
    energy_kj: int | None = None
    rr_ms: list[float] = field(default_factory=list)


def parse_hr(data: bytes) -> HrMeasurement | None:
    """Heart Rate Measurement (0x2A37) nach Bluetooth-Spezifikation lesen. None bei kaputtem Paket."""
    if len(data) < 2:
        return None
    flags = data[0]
    if flags & 0x01:  # Bit 0: Puls als UINT16 (HypeRate prüft hier fälschlich getProperties())
        if len(data) < 3:
            return None
        bpm, i = int.from_bytes(data[1:3], "little"), 3
    else:
        bpm, i = data[1], 2
    contact = bool(flags & 0x02) if flags & 0x04 else None  # Bit 2: Kontakt-Status unterstützt, Bit 1: Kontakt
    energy = None
    if flags & 0x08:  # Bit 3: Energieverbrauch (UINT16 kJ)
        if len(data) >= i + 2:
            energy = int.from_bytes(data[i:i + 2], "little")
        i += 2
    rr = []
    if flags & 0x10:  # Bit 4: RR-Intervalle, je UINT16 in 1/1024 s
        while i + 1 < len(data):
            rr.append(int.from_bytes(data[i:i + 2], "little") * 1000 / 1024)
            i += 2
    return HrMeasurement(bpm, contact, energy, rr)


def _osc_string(s: str) -> bytes:
    b = s.encode("utf-8")
    return b + b"\0" * (4 - len(b) % 4)  # mindestens ein Nullbyte, auf 4 Bytes aufgefüllt


def encode_osc(address: str, *values) -> bytes:
    tags, payload = ",", b""
    for v in values:
        if isinstance(v, bool):
            tags += "T" if v else "F"
        elif isinstance(v, int):
            tags += "i"
            payload += struct.pack(">i", v)
        elif isinstance(v, float):
            tags += "f"
            payload += struct.pack(">f", v)
        else:
            tags += "s"
            payload += _osc_string(str(v))
    return _osc_string(address) + _osc_string(tags) + payload


def percent(bpm: int, lo: int, hi: int) -> float:
    return min(max((bpm - lo) / max(hi - lo, 1), 0.0), 1.0)


def hr_params(bpm: int, lo: int, hi: int) -> list[tuple[str, object]]:
    """Alle Avatar-Parameter für einen gültigen Pulswert."""
    pct = percent(bpm, lo, hi)
    return [
        # VRCOSC-Heartrate-Prefab: hört auf VRCOSC/Heartrate/Value (Int 0-255)
        ("VRCOSC/Heartrate/Value", min(bpm, 255)),
        ("VRCOSC/Heartrate/Normalised", float(pct)),
        ("VRCOSC/Heartrate/Units", bpm % 10),
        ("VRCOSC/Heartrate/Tens", bpm // 10 % 10),
        ("VRCOSC/Heartrate/Hundreds", bpm // 100 % 10),
        ("VRCOSC/Heartrate/Enabled", True),
        # Namen wie HRtoVRChat_OSC, die viele andere Puls-Prefabs nutzen
        ("HR", min(bpm, 255)),
        ("onesHR", bpm % 10),
        ("tensHR", bpm // 10 % 10),
        ("hundredsHR", bpm // 100 % 10),
        ("HRPercent", float(pct)),
        ("FullHRPercent", float(pct * 2 - 1)),
        ("isHRActive", True),
        (CONNECTED_PARAM, True),
    ]
