"""
platform_compat.py
------------------
Platform initialization helpers for Linux/XWayland compatibility.
Ensures libxcb-cursor is preloaded and QT_QPA_PLATFORM is set to 'xcb'
when DISPLAY is present on Linux systems to avoid Wayland popup grab issues.
"""

import ctypes
import os
import sys
from pathlib import Path


def init_platform() -> None:
    """Configure platform environment for Qt on Linux."""
    if sys.platform.startswith("linux"):
        lib_path = (
            Path(__file__).resolve().parent / "resources" / "lib" / "libxcb-cursor.so.0"
        )
        if lib_path.is_file():
            try:
                ctypes.CDLL(str(lib_path), mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass

        # Default to xcb when a display exists, but never override a setting
        # the user (or the test suite, which uses "offscreen") already chose.
        if os.environ.get("DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
