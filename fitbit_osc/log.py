# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
"""Einfaches Log: Konsole (falls vorhanden) und optional eine Datei."""
import sys
import threading
import time

_file = None
_lock = threading.Lock()


def set_file(path: str, header: str = "") -> None:
    """Log-Datei neu anlegen; ab jetzt geht jede Zeile auch dorthin."""
    global _file
    with _lock:
        with open(path, "w", encoding="utf-8") as f:
            if header:
                f.write(header + "\n")
        _file = path


def log(*parts) -> None:
    line = time.strftime("%H:%M:%S") + " " + " ".join(str(p) for p in parts)
    with _lock:
        if sys.stdout:  # unter pythonw / im .exe ohne Konsole gibt es kein stdout
            try:
                print(line, flush=True)
            except (OSError, UnicodeError):
                pass
        if _file:
            try:
                with open(_file, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass
