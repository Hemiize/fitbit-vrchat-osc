# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
"""Baut dist/fitbit-osc.exe (eine Datei, ohne Konsole, Tray-Modus).

Aufruf aus dem Projektordner:  .venv\\Scripts\\python.exe packaging\\build_exe.py
Braucht die Pakete aus requirements.txt und requirements-dev.txt.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
sys.path.insert(0, ROOT)

from fitbit_osc import __version__  # noqa: E402
from fitbit_osc.icons import ON, heart  # noqa: E402


def write_icon(path: str) -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    heart(ON, 256).save(path, sizes=[(s, s) for s in sizes])


def write_version_file(path: str) -> None:
    nums = (__version__.split(".") + ["0", "0", "0"])[:4]
    tup = ", ".join(str(int(n)) for n in nums)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({tup}), prodvers=({tup})),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'hemiize'),
    StringStruct('FileDescription', 'Fitbit Air heart rate to VRChat (OSC)'),
    StringStruct('FileVersion', '{__version__}'),
    StringStruct('InternalName', 'fitbit-osc'),
    StringStruct('LegalCopyright', 'Copyright 2026 hemiize, Apache-2.0'),
    StringStruct('OriginalFilename', 'fitbit-osc.exe'),
    StringStruct('ProductName', 'fitbit-osc'),
    StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
""")


def main() -> None:
    os.makedirs(BUILD, exist_ok=True)
    icon = os.path.join(BUILD, "heart.ico")
    version = os.path.join(BUILD, "version.txt")
    write_icon(icon)
    write_version_file(version)
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "fitbit-osc", "--icon", icon, "--version-file", version,
        "--distpath", DIST, "--workpath", BUILD, "--specpath", BUILD,
        "--hidden-import", "pystray._win32",
        "--collect-submodules", "winrt",
        "--collect-submodules", "bleak.backends.winrt",
        "--collect-submodules", "zeroconf",
        "--collect-all", "openvr",
        "--add-data", os.path.join(ROOT, "LICENSE") + os.pathsep + ".",
        "--add-data", os.path.join(ROOT, "NOTICE") + os.pathsep + ".",
        os.path.join(ROOT, "hr_osc.py"),
    ]
    subprocess.run(cmd, check=True, cwd=ROOT)
    exe = os.path.join(DIST, "fitbit-osc.exe")
    print(f"built {exe} ({os.path.getsize(exe) / 1e6:.1f} MB), version {__version__}")


if __name__ == "__main__":
    main()
