# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
"""OSC über UDP verschicken; das Ziel kann sich zur Laufzeit ändern (OSCQuery)."""
from __future__ import annotations

import socket

from .log import log
from .protocol import encode_osc


class OscSender:
    def __init__(self, ip: str, port: int):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.target = (ip, port)
        self._error_logged = False

    def send(self, address: str, *values) -> None:
        try:
            self.sock.sendto(encode_osc(address, *values), self.target)
            self._error_logged = False
        except OSError as e:  # z. B. Netz weg bei entferntem Ziel; nicht abstürzen, nur einmal melden
            if not self._error_logged:
                log("OSC send failed:", type(e).__name__, e)
                self._error_logged = True

    def close(self) -> None:
        self.sock.close()
