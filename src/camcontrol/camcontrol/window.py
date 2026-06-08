"""Foreground-window awareness via ctypes Win32 (SPEC 8).

The daemon only acts when a configured terminal process is foreground. We read
its client rect in *screen* pixels and normalize the calibrated dot into it.

``ScreenRect`` is pure, cross-platform, and unit-tested. The ctypes entry points
(``terminal_rect``, ``screen_size``, ``set_dpi_awareness``) are a Win32 shell,
gated behind ``sys.platform``; a Linux (X11/Wayland) backend would implement the
same three functions.
"""

from __future__ import annotations

import contextlib
import ctypes
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.platform == "win32":
    from ctypes import wintypes

# OpenProcess access right that needs no elevation; enough for the image name.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SM_CXSCREEN = 0
_SM_CYSCREEN = 1


def _unsupported(name: str):
    return NotImplementedError(
        f"{name} is implemented for Windows only; add a backend for {sys.platform!r}"
    )


@dataclass(frozen=True)
class ScreenRect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def normalize(self, px: float, py: float) -> tuple[float, float]:
        """Screen-pixel (px, py) -> [0,1]^2 within this rect (may fall outside)."""
        return ((px - self.left) / self.width, (py - self.top) / self.height)


def set_dpi_awareness() -> None:
    """Make screen px and client rect agree under display scaling. No-op where
    DPI awareness isn't a concept (non-Windows)."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware
    except (AttributeError, OSError):
        with contextlib.suppress(AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()


def screen_size() -> tuple[int, int]:
    if sys.platform != "win32":
        raise _unsupported("screen_size")
    user32 = ctypes.windll.user32
    return (user32.GetSystemMetrics(_SM_CXSCREEN), user32.GetSystemMetrics(_SM_CYSCREEN))


def _exe_name_for_hwnd(hwnd: int) -> str | None:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return None
    try:
        buf = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buf))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return None
        return Path(buf.value).name
    finally:
        kernel32.CloseHandle(handle)


def terminal_rect(process_names: list[str]) -> ScreenRect | None:
    """Client rect (screen px) of the foreground window if it is a terminal."""
    if sys.platform != "win32":
        raise _unsupported("terminal_rect")
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    exe = _exe_name_for_hwnd(hwnd)
    if exe is None or exe.lower() not in {p.lower() for p in process_names}:
        return None
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    origin = wintypes.POINT(rect.left, rect.top)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    return ScreenRect(
        left=origin.x,
        top=origin.y,
        right=origin.x + (rect.right - rect.left),
        bottom=origin.y + (rect.bottom - rect.top),
    )
