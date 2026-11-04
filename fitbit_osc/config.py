# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
"""Einstellungen: Standardwerte < config.json < Kommandozeile."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, fields, replace

from . import __version__


@dataclass
class Config:
    ip: str = "127.0.0.1"
    port: int | str = "auto"  # "auto": Port per OSCQuery von VRChat erfragen, sonst 9000
    name: str = "fitbit"
    min: int = 0
    max: int = 255
    chatbox: bool = False
    overlay: bool = False
    overlay_port: int = 8765


DEFAULT_OSC_PORT = 9000


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> str:
    """Ordner des Programms: neben der .exe bzw. das Repository."""
    if frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_dir() -> str:
    """Wohin Log, Einstellungen und SteamVR-Manifest kommen: neben das Programm, sonst %LOCALAPPDATA%."""
    d = app_dir()
    probe = os.path.join(d, ".fitbit-osc-write-test")
    try:
        with open(probe, "a"):
            pass
        os.remove(probe)
        return d
    except OSError:
        d = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "fitbit-osc")
        os.makedirs(d, exist_ok=True)
        return d


def parse_port(value) -> int | str:
    if isinstance(value, str) and value.strip().lower() == "auto":
        return "auto"
    if isinstance(value, bool):
        raise ValueError("must be a number or \"auto\"")
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise ValueError("must be a number or \"auto\"") from None
    if not 0 < port < 65536:
        raise ValueError("must be between 1 and 65535")
    return port


def _coerce(name: str, value, default):
    if name == "port":
        return parse_port(value)
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise ValueError("must be true or false")
        return value
    if isinstance(default, int):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("must be a whole number")
        if name == "overlay_port" and not 0 < value < 65536:
            raise ValueError("must be between 1 and 65535")
        return value
    if not isinstance(value, str):
        raise ValueError("must be text")
    return value


def validate(cfg: Config) -> list[str]:
    """Widersprüchliche Werte korrigieren; gibt Warnungen zurück."""
    warnings = []
    if cfg.min >= cfg.max:
        warnings.append(f"min ({cfg.min}) must be below max ({cfg.max}), using 0 and 255")
        cfg.min, cfg.max = 0, 255
    return warnings


def load_config(path: str) -> tuple[Config, list[str]]:
    cfg = Config()
    if not os.path.exists(path):
        return cfg, []
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        return cfg, [f"settings file ignored ({e})"]
    if not isinstance(data, dict):
        return cfg, ["settings file ignored (not a JSON object)"]
    warnings = []
    defaults = Config()
    known = {f.name for f in fields(Config)}
    for key in sorted(set(data) - known):
        warnings.append(f"unknown setting \"{key}\" ignored")
    for f in fields(Config):
        if f.name in data:
            try:
                setattr(cfg, f.name, _coerce(f.name, data[f.name], getattr(defaults, f.name)))
            except ValueError as e:
                warnings.append(f"{f.name} {e}, using {getattr(defaults, f.name)!r}")
    return cfg, warnings + validate(cfg)


def save_config(cfg: Config, path: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="fitbit-osc", description="Fitbit Air heart rate -> VRChat OSC")
    s = argparse.SUPPRESS  # nicht angegeben = Wert aus config.json
    ap.add_argument("--ip", default=s, help="OSC target address (default 127.0.0.1)")
    ap.add_argument("--port", type=parse_port, default=s,
                    help="OSC target port, or \"auto\" to ask VRChat via OSCQuery (default auto, fallback 9000)")
    ap.add_argument("--name", default=s, help="part of the band's Bluetooth name (default \"fitbit\")")
    ap.add_argument("--min", type=int, default=s, help="lower bound for HRPercent/Normalised (default 0)")
    ap.add_argument("--max", type=int, default=s, help="upper bound for HRPercent/Normalised (default 255)")
    ap.add_argument("--chatbox", action="store_true", default=s, help="also show the heart rate in the VRChat chatbox")
    ap.add_argument("--overlay", action="store_true", default=s, help="serve an OBS browser-source overlay")
    ap.add_argument("--overlay-port", type=int, default=s, help="port of the OBS overlay (default 8765)")
    ap.add_argument("--demo", action="store_true", help="no band: send synthetic values (for testing)")
    ap.add_argument("--tray", action="store_true", help="tray icon instead of console, log to fitbit-osc.log")
    ap.add_argument("--follow-steamvr", action="store_true", help="exit once SteamVR (vrserver.exe) is no longer running")
    ap.add_argument("--register-steamvr", action="store_true", help="start automatically with SteamVR, then exit")
    ap.add_argument("--unregister-steamvr", action="store_true", help="remove the SteamVR autostart, then exit")
    ap.add_argument("--version", action="version", version=f"fitbit-osc {__version__}")
    return ap


def merge(cfg: Config, ns: argparse.Namespace) -> tuple[Config, list[str]]:
    """Kommandozeile über die Datei-Einstellungen legen (nur was angegeben wurde)."""
    out = replace(cfg)
    for f in fields(Config):
        if hasattr(ns, f.name):
            setattr(out, f.name, getattr(ns, f.name))
    return out, validate(out)
