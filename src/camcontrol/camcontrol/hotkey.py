"""Global toggle hotkey via ctypes ``RegisterHotKey`` (SPEC 8).

``parse_hotkey`` (pure, unit-tested) turns "ctrl+alt+h" into Win32 modifier flags
and a virtual-key code. ``HotkeyListener`` (manual shell) registers the hotkey on
its own thread and runs a message loop, invoking a callback on each press.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
from collections.abc import Callable

if sys.platform == "win32":
    from ctypes import wintypes

logger = logging.getLogger(__name__)

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

_MODIFIERS = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
}

_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_HOTKEY_ID = 1


def parse_hotkey(spec: str) -> tuple[int, int]:
    """"ctrl+alt+h" -> (modifier flags, virtual-key code)."""
    *mod_tokens, key = [t.strip().lower() for t in spec.split("+")]
    mods = 0
    for tok in mod_tokens:
        if tok not in _MODIFIERS:
            raise ValueError(f"unknown modifier: {tok!r}")
        mods |= _MODIFIERS[tok]
    if len(key) != 1 or not key.isalnum():
        raise ValueError(f"unsupported key: {key!r}")
    return mods, ord(key.upper())


class HotkeyListener:
    """Calls ``on_press`` whenever the registered hotkey fires. Runs a Win32
    message loop on a dedicated thread."""

    def __init__(self, spec: str, on_press: Callable[[], None]) -> None:
        self._mods, self._vk = parse_hotkey(spec)
        self._on_press = on_press
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None

    def start(self) -> None:
        if sys.platform != "win32":
            # No global-hotkey backend off Windows yet; the daemon still runs,
            # just without the toggle. A Linux backend (X11/evdev) plugs in here.
            logger.warning("global toggle hotkey not supported on %s — disabled", sys.platform)
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, _HOTKEY_ID, self._mods, self._vk):
            # Don't crash the daemon over a hotkey clash (usually another
            # instance already holds it). Log and leave the toggle disabled.
            logger.warning(
                "could not register toggle hotkey (already in use? another daemon "
                "running?) — hotkey toggle disabled for this instance"
            )
            return
        try:
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == _WM_HOTKEY:
                    self._on_press()
        finally:
            user32.UnregisterHotKey(None, _HOTKEY_ID)

    def stop(self) -> None:
        if self._thread_id is not None:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, _WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
