# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
"""Herz-Symbol für Tray und .exe."""
from __future__ import annotations

ON = (225, 45, 70, 255)
OFF = (140, 140, 140, 255)


def heart(color, size: int = 64):
    from PIL import Image, ImageDraw
    s = size / 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4 * s, 8 * s, 34 * s, 38 * s), fill=color)
    d.ellipse((30 * s, 8 * s, 60 * s, 38 * s), fill=color)
    d.polygon([(6 * s, 28 * s), (58 * s, 28 * s), (32 * s, 60 * s)], fill=color)
    return img
