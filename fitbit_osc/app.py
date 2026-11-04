# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
"""Programmstart, Hintergrundaufgaben und Tray-Menü."""
from __future__ import annotations

import asyncio
import ctypes
import math
import os
import sys
import threading
import time
import webbrowser
from dataclasses import replace

from . import __version__, autostart, steamvr
from .bridge import Bridge
from .config import DEFAULT_OSC_PORT, build_parser, data_dir, frozen, load_config, merge, save_config
from .log import log, set_file
from .osc import OscSender
from .oscquery import VRChatDiscovery
from .overlay import Overlay

REPO_URL = "https://github.com/Hemiize/fitbit-vrchat-osc"


def single_instance() -> bool:
    # Zweiter Start (z. B. von Hand neben dem SteamVR-Autostart) würde um das Band kämpfen
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW(None, False, "Local\\fitbit-osc-bridge")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


class App:
    def __init__(self, cfg, file_cfg, cfg_path: str, ns, tray_mode: bool):
        self.cfg = cfg  # was gerade gilt (Datei + Kommandozeile)
        self.file_cfg = file_cfg  # was in config.json steht; Tray-Schalter ändern beide
        self.cfg_path = cfg_path
        self.ns = ns
        self.tray_mode = tray_mode
        port = DEFAULT_OSC_PORT if cfg.port == "auto" else cfg.port
        self.sender = OscSender(cfg.ip, port)
        self.bridge = Bridge(cfg, self.sender.send, on_change=self.refresh_tray)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.stop_event: asyncio.Event | None = None
        self.icon = None
        self.images: dict = {}
        self.overlay: Overlay | None = None
        self.discovery: VRChatDiscovery | None = None
        self._overlay_lock = threading.Lock()
        self._menu_status = ""

    # --- Einstellungen ---------------------------------------------------------------------------

    def save(self) -> None:
        try:
            save_config(self.file_cfg, self.cfg_path)
        except OSError as e:
            log("Could not save settings:", e)

    def set_option(self, name: str, value) -> None:
        setattr(self.cfg, name, value)
        setattr(self.file_cfg, name, value)
        self.save()

    # --- OSC-Ziel per OSCQuery ---------------------------------------------------------------------

    def start_discovery(self) -> None:
        if self.cfg.port != "auto" or self.cfg.ip not in ("127.0.0.1", "localhost"):
            return

        def on_port(port: int) -> None:
            if port != self.sender.target[1]:
                log("VRChat OSC port found via OSCQuery:", port)
                self.sender.target = (self.sender.target[0], port)

        self.discovery = VRChatDiscovery(on_port)
        self.discovery.start()

    # --- OBS-Overlay -----------------------------------------------------------------------------

    def apply_overlay(self) -> None:
        with self._overlay_lock:
            if self.cfg.overlay and self.overlay is None:
                overlay = Overlay(self.bridge.snapshot, self.cfg.overlay_port)
                try:
                    url = overlay.start()
                    self.overlay = overlay
                    log("OBS overlay at", url, "(add it as a browser source)")
                except OSError as e:
                    log(f"OBS overlay could not use port {self.cfg.overlay_port}:", e)
                    self.notify(f"OBS overlay: port {self.cfg.overlay_port} is in use")
            elif not self.cfg.overlay and self.overlay is not None:
                self.overlay.stop()
                self.overlay = None
                log("OBS overlay stopped")

    # --- Hintergrundaufgaben ---------------------------------------------------------------------

    async def beat_loop(self) -> None:
        # isHRBeat / HeartBeatToggle im Takt des Pulses umschalten
        toggle = False
        while True:
            if self.bridge.fresh():
                toggle = not toggle
                self.bridge.param("isHRBeat", toggle)
                self.bridge.param("HeartBeatToggle", toggle)
                await asyncio.sleep(30 / self.bridge.bpm)
            else:
                await asyncio.sleep(0.5)

    async def status_loop(self) -> None:
        while True:
            await asyncio.sleep(1)
            self.bridge.tick()

    async def chatbox_loop(self) -> None:
        # VRChat drosselt die Chatbox; alle 3 s reicht. Der Schalter im Tray wirkt sofort.
        while True:
            await asyncio.sleep(3)
            if self.cfg.chatbox and self.bridge.fresh():
                self.sender.send("/chatbox/input", f"❤ {self.bridge.bpm} BPM", True, False)

    async def demo_loop(self) -> None:
        self.bridge.set_connected(True)
        t0 = time.time()
        while True:
            self.bridge.handle(bytes([0, int(80 + 20 * math.sin((time.time() - t0) / 5))]))
            await asyncio.sleep(1)

    async def follow_steamvr(self) -> None:
        # Von SteamVR gestartet: SteamVR beendet Fremdprogramme nicht selbst, also alle 10 s nach vrserver.exe sehen
        missing = 0
        while True:
            await asyncio.sleep(10)
            try:
                running = await asyncio.to_thread(steamvr.vrserver_running)  # blockiert den Puls-Takt nicht
            except Exception as e:
                log("tasklist failed:", type(e).__name__, e)
                continue
            missing = 0 if running else missing + 1
            if missing >= 2:
                log("SteamVR closed, bridge stops")
                return

    async def main(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.stop_event = asyncio.Event()
        self.bridge.reset()
        self.start_discovery()
        self.apply_overlay()
        target = "%s:%s" % self.sender.target
        log("Sending OSC to", target + (" (port from OSCQuery once VRChat runs)" if self.discovery else ""))
        if self.ns.demo:
            source = self.demo_loop()
        else:
            from .ble import ble_loop  # erst hier: Demo und Tests brauchen kein Bluetooth
            source = ble_loop(self.bridge, self.cfg)
        coros = [self.beat_loop(), self.status_loop(), self.chatbox_loop(), source, self.stop_event.wait()]
        if self.ns.follow_steamvr:
            coros.append(self.follow_steamvr())
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
            await asyncio.gather(*tasks, return_exceptions=True)  # Aufräumen in den Aufgaben abwarten

    def run_asyncio(self) -> None:
        try:
            asyncio.run(self.main())
        except KeyboardInterrupt:
            pass
        finally:
            self.bridge.reset()
            if self.overlay:
                self.overlay.stop()
            if self.discovery:
                self.discovery.close()
            log("Stopped")
            if self.icon:
                self.icon.stop()

    def stop(self) -> None:
        if self.loop and self.stop_event:
            self.loop.call_soon_threadsafe(self.stop_event.set)
        elif self.icon:
            self.icon.stop()

    # --- Tray ------------------------------------------------------------------------------------

    def notify(self, message: str) -> None:
        if self.icon is not None:
            try:
                self.icon.notify(message, "fitbit-osc")
            except Exception:
                pass

    def menu_status(self) -> str:
        b = self.bridge
        if not b.connected:
            return "No band connected"
        text = "Band connected" + ("" if b.fresh() else ", no heart rate")
        if b.battery is not None:
            text += f" | battery {b.battery} %"
        return text

    def refresh_tray(self) -> None:
        icon = self.icon
        if icon is None:
            return
        on = self.bridge.connected and self.bridge.fresh()
        icon.icon = self.images["on" if on else "off"]
        icon.title = self.bridge.status_text()[:127]
        # pystray baut das Menü nur bei update_menu neu. Nur bei echtem Statuswechsel, nicht bei jedem Pulswert:
        # ein Neubau zerstört ein gerade geöffnetes Menü.
        status = self.menu_status()
        if status != self._menu_status:
            self._menu_status = status
            try:
                icon.update_menu()
            except Exception:
                pass

    def run_tray(self) -> None:
        # pystray braucht den Hauptthread; asyncio läuft daneben in einem eigenen Thread
        import pystray

        from .icons import OFF, ON, heart
        self.images = {"on": heart(ON), "off": heart(OFF)}
        Item, Menu = pystray.MenuItem, pystray.Menu

        def toggle(name):
            def action(icon, item):
                self.set_option(name, not getattr(self.cfg, name))
                if name == "overlay":
                    self.apply_overlay()
                icon.update_menu()
            return action

        def toggle_windows(icon, item):
            try:
                if autostart.is_enabled():
                    autostart.disable()
                    log("Start with Windows: off")
                else:
                    log("Start with Windows: on,", autostart.enable())
            except OSError as e:
                log("Start with Windows failed:", e)
                self.notify("Could not change the Windows autostart")
            icon.update_menu()

        def toggle_steamvr(icon, item):
            def work():
                try:
                    if steamvr.is_registered():
                        ok = steamvr.unregister()
                        log("Start with SteamVR: off" if ok else "Start with SteamVR: removal not confirmed")
                    else:
                        installed, auto, _ = steamvr.register()
                        log("Start with SteamVR: registered", installed, "| autostart", auto)
                except Exception as e:  # SteamVR nicht installiert, OpenVR-Fehler
                    log("SteamVR registration failed:", type(e).__name__, e)
                    self.notify("SteamVR registration failed, see the log")
                icon.update_menu()
            threading.Thread(target=work, daemon=True).start()  # OpenVR startet kurz den vrserver

        def open_overlay(icon, item):
            if self.overlay:
                webbrowser.open(self.overlay.url)

        def open_settings(icon, item):
            if not os.path.exists(self.cfg_path):
                self.save()
            os.startfile(self.cfg_path)

        def open_log(icon, item):
            os.startfile(os.path.join(data_dir(), "fitbit-osc.log"))

        menu = Menu(
            Item(lambda item: self.menu_status(), None, enabled=False),
            Menu.SEPARATOR,
            Item("Show in VRChat chatbox", toggle("chatbox"), checked=lambda item: self.cfg.chatbox),
            Item("OBS overlay", toggle("overlay"), checked=lambda item: self.cfg.overlay),
            Item("Open overlay in browser", open_overlay, enabled=lambda item: self.overlay is not None),
            Menu.SEPARATOR,
            Item("Start with Windows", toggle_windows, checked=lambda item: autostart.is_enabled()),
            Item("Start with SteamVR", toggle_steamvr, checked=lambda item: steamvr.is_registered()),
            Menu.SEPARATOR,
            Item("Settings file (restart to apply)", open_settings),
            Item("Open log", open_log),
            Item(f"About fitbit-osc {__version__}", lambda icon, item: webbrowser.open(REPO_URL)),
            Item("Quit", lambda icon, item: self.stop()),
        )
        self.icon = pystray.Icon("fitbit-osc", self.images["off"], "Heart rate: searching for band", menu)

        def setup(icon):
            icon.visible = True  # mit eigenem setup blendet pystray das Symbol nicht selbst ein
            threading.Thread(target=self.run_asyncio, daemon=True).start()

        self.icon.run(setup=setup)

    def run(self) -> None:
        if self.tray_mode:
            self.run_tray()
        else:
            self.run_asyncio()


def main(argv=None) -> None:
    ns = build_parser().parse_args(argv)
    ddir = data_dir()
    cfg_path = os.path.join(ddir, "config.json")
    file_cfg, warnings = load_config(cfg_path)
    cfg, more = merge(file_cfg, ns)
    warnings += more

    if ns.register_steamvr or ns.unregister_steamvr:
        if ns.unregister_steamvr:
            print("SteamVR autostart removed:", steamvr.unregister())
        else:
            installed, auto, manifest = steamvr.register()
            app = manifest["applications"][0]
            print("Registered:", installed, "| autostart:", auto)
            print("Starts:", app["binary_path_windows"], app["arguments"])
        return

    # Das .exe hat keine Konsole: dort immer Tray-Modus mit Log-Datei
    tray_mode = ns.tray or (frozen() and sys.stdout is None)
    if not single_instance():
        log("Already running, second instance exits")
        return
    if tray_mode:
        set_file(os.path.join(ddir, "fitbit-osc.log"),
                 time.strftime("%Y-%m-%d %H:%M:%S") + f" fitbit-osc {__version__} started in tray mode, arguments: "
                 + " ".join(sys.argv[1:]))
    log(f"fitbit-osc {__version__}")
    for w in warnings:
        log("Settings:", w)
    App(cfg, replace(file_cfg), cfg_path, ns, tray_mode).run()
