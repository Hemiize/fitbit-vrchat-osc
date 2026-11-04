# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
"""VRChats OSC-Port per OSCQuery finden (mDNS-Dienst _oscjson._tcp, dann HTTP ?HOST_INFO).

Nötig, wenn VRChat mit --osc=... auf einem anderen Port als 9000 lauscht. Findet sich nichts, bleibt es bei 9000.
"""
from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Callable

from .log import log

SERVICE = "_oscjson._tcp.local."
VRCHAT_PREFIX = "VRChat-Client-"

# Ohne Proxy: localhost-Anfragen sollen nie über einen System-Proxy laufen
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def query_host_info(host: str, http_port: int, timeout: float = 3) -> int | None:
    """OSC-Port aus der OSCQuery-HOST_INFO lesen."""
    with _opener.open(f"http://{host}:{http_port}/?HOST_INFO", timeout=timeout) as r:
        data = json.load(r)
    port = data.get("OSC_PORT")
    transport = str(data.get("OSC_TRANSPORT", "UDP")).upper()
    if isinstance(port, int) and not isinstance(port, bool) and 0 < port < 65536 and transport == "UDP":
        return port
    return None


def local_addresses() -> set[str]:
    addrs = {"127.0.0.1", "::1"}
    try:
        import ifaddr
        for adapter in ifaddr.get_adapters():
            for ip in adapter.ips:
                addrs.add(ip.ip if isinstance(ip.ip, str) else ip.ip[0])
    except Exception:
        pass
    return addrs


class VRChatDiscovery:
    def __init__(self, on_port: Callable[[int], None]):
        self.on_port = on_port
        self.zc = None
        self.browser = None

    def start(self) -> bool:
        try:
            from zeroconf import ServiceBrowser, Zeroconf
            self.zc = Zeroconf()
            self.browser = ServiceBrowser(self.zc, SERVICE, handlers=[self._changed])
            return True
        except Exception as e:
            log("OSCQuery discovery unavailable, using port 9000:", type(e).__name__, e)
            self.close()
            return False

    def _changed(self, zeroconf, service_type, name, state_change) -> None:
        from zeroconf import ServiceStateChange
        if not name.startswith(VRCHAT_PREFIX) or state_change is ServiceStateChange.Removed:
            return
        # get_service_info blockiert; nicht im Thread des Browsers
        threading.Thread(target=self._resolve, args=(service_type, name), daemon=True).start()

    def _resolve(self, service_type: str, name: str) -> None:
        try:
            info = self.zc.get_service_info(service_type, name, timeout=3000)
            if info is None:
                return
            addrs = set(info.parsed_addresses())
            if addrs and not addrs & local_addresses():
                log("OSCQuery: ignoring VRChat on another device", ", ".join(sorted(addrs)))
                return
            port = query_host_info("127.0.0.1", info.port)
            if port:
                self.on_port(port)
        except Exception as e:
            log("OSCQuery lookup failed:", type(e).__name__, e)

    def close(self) -> None:
        try:
            if self.zc is not None:
                self.zc.close()
        except Exception:
            pass
        self.zc = self.browser = None
