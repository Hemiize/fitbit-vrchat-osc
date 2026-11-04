# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
"""Zustand der Brücke: Messwerte annehmen, Avatar-Parameter schicken, veraltete Werte als inaktiv melden."""
from __future__ import annotations

import time
from collections.abc import Callable

from .log import log
from .protocol import ACTIVE_PARAMS, BATTERY_PARAM, CONNECTED_PARAM, hr_params, parse_hr

FRESH = 5.0  # so lange gilt ein Pulswert als aktuell


class Bridge:
    def __init__(self, cfg, send: Callable[..., None], clock: Callable[[], float] = time.time,
                 on_change: Callable[[], None] | None = None):
        self.cfg = cfg
        self._send = send
        self.clock = clock
        self.on_change = on_change or (lambda: None)
        self.bpm = 0
        self.last = 0.0  # Zeit des letzten Pulswerts > 0
        self.seen = 0.0  # Zeit des letzten Pakets überhaupt (auch 0 BPM)
        self.connected = False
        self.active = False  # was der Avatar gerade als "Puls kommt" kennt
        self.battery: int | None = None
        self._nopulse_logged = False

    # --- Ausgabe -----------------------------------------------------------------------------

    def param(self, name: str, value) -> None:
        self._send("/avatar/parameters/" + name, value)

    def _push_active(self, on: bool, force: bool = False) -> None:
        if self.active == on and not force:
            return
        self.active = on
        for name in ACTIVE_PARAMS:
            self.param(name, on)

    # --- Zustandswechsel ---------------------------------------------------------------------

    def reset(self) -> None:
        """Startzustand und Ende: dem Avatar sagen, dass nichts verbunden ist."""
        self.connected = False
        self.bpm = 0
        self._push_active(False, force=True)
        self.param(CONNECTED_PARAM, False)
        self.on_change()

    def set_connected(self, on: bool) -> None:
        if on == self.connected:
            return
        self.connected = on
        if on:
            self.seen = self.clock()
        else:
            self.bpm = 0
            self._push_active(False)
        self.param(CONNECTED_PARAM, on)
        self.on_change()

    def handle(self, data: bytes) -> None:
        """Ein Heart-Rate-Measurement-Paket vom Band."""
        m = parse_hr(bytes(data))
        if m is None:
            return
        now = self.clock()
        self.seen = now
        if m.bpm == 0 or m.contact is False:
            if not self._nopulse_logged:
                why = "0 BPM" if m.bpm == 0 else "no skin contact"
                log(f"Band reports {why} (not on the wrist?), raw", bytes(data).hex())
                self._nopulse_logged = True
            changed = self.bpm != 0 or self.active
            self.bpm = 0
            self._push_active(False)
            if changed:
                self.on_change()
            return
        self._nopulse_logged = False
        changed = m.bpm != self.bpm or not self.active
        self.bpm, self.last = m.bpm, now
        for name, value in hr_params(m.bpm, self.cfg.min, self.cfg.max):
            self.param(name, value)
        self.active = True  # hr_params setzt die Aktiv-Parameter schon
        if changed:
            log("BPM", m.bpm)
            self.on_change()

    def set_battery(self, level: int) -> None:
        level = max(0, min(100, int(level)))
        if level != self.battery:
            log("Band battery", f"{level} %")
            self.battery = level
            self.on_change()
        self.param(BATTERY_PARAM, level / 100)

    def tick(self) -> None:
        """Jede Sekunde: ohne frischen Wert zeigt der Avatar den Puls als inaktiv statt einer eingefrorenen Zahl."""
        if self.active and not self.fresh():
            log(f"No heart rate for {FRESH:.0f} s, avatar shows it as inactive")
            self._push_active(False)
            self.on_change()

    # --- Abfragen ----------------------------------------------------------------------------

    def fresh(self) -> bool:
        return self.bpm > 0 and self.clock() - self.last < FRESH

    def status_text(self) -> str:
        if not self.connected:
            return "No band connected"
        if self.fresh():
            text = f"Heart rate: {self.bpm} BPM"
        elif self.clock() - self.seen < FRESH:
            text = "Band connected, no pulse (not on the wrist?)"
        else:
            text = "Band connected, waiting for data"
        if self.battery is not None:
            text += f" | battery {self.battery} %"
        return text

    def snapshot(self) -> dict:
        fresh = self.fresh()
        return {"bpm": self.bpm if fresh else 0, "active": fresh, "connected": self.connected,
                "battery": self.battery}
