"""Raccourcis clavier globaux (Ctrl+Alt+D…).

Sous Windows on utilise RegisterHotKey : c'est Windows lui-même qui surveille
le raccourci, sans espionner le clavier. C'est plus fiable que l'écoute de
toutes les touches, et les antivirus ne s'en méfient pas.
"""

from __future__ import annotations

import logging
import sys
import threading

log = logging.getLogger(__name__)

MODS = {"ctrl": 0x2, "alt": 0x1, "shift": 0x4, "cmd": 0x8, "win": 0x8}
MOD_NOREPEAT = 0x4000
SPECIAL_VK = {"space": 0x20, "enter": 0x0D, "tab": 0x09, **{f"f{i}": 0x6F + i for i in range(1, 13)}}


def parse(combo: str) -> tuple[int, int]:
    """'<ctrl>+<alt>+d' → (modificateurs, code de touche Windows)."""
    mods, vk = 0, 0
    for part in combo.lower().split("+"):
        name = part.strip().strip("<>")
        if name in MODS:
            mods |= MODS[name]
        elif name in SPECIAL_VK:
            vk = SPECIAL_VK[name]
        elif len(name) == 1 and name.isalnum():
            vk = ord(name.upper())
        else:
            raise ValueError(f"touche inconnue : {part}")
    if not vk:
        raise ValueError(f"raccourci incomplet : {combo}")
    return mods, vk


class GlobalHotkeys:
    def __init__(self, bindings: dict):
        self.bindings = bindings
        self.failed: list[str] = []
        self._thread_id = 0
        self._pynput = None

    def start(self):
        if sys.platform != "win32":
            from pynput import keyboard

            self._pynput = keyboard.GlobalHotKeys(self.bindings)
            self._pynput.start()
            return
        ready = threading.Event()
        threading.Thread(target=self._loop, args=(ready,), daemon=True).start()
        ready.wait(2)

    def _loop(self, ready):
        import ctypes
        import ctypes.wintypes as wt

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        actions = {}
        for i, (combo, fn) in enumerate(self.bindings.items(), start=1):
            try:
                mods, vk = parse(combo)
                if user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                    actions[i] = fn
                else:
                    self.failed.append(combo)  # déjà pris par un autre logiciel
                    log.warning("Raccourci %s déjà utilisé par un autre logiciel", combo)
            except ValueError as e:
                self.failed.append(combo)
                log.warning("%s", e)
        ready.set()
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312:  # WM_HOTKEY
                fn = actions.get(msg.wParam)
                if fn:
                    try:
                        fn()
                    except Exception:
                        log.exception("raccourci")
        for i in actions:
            user32.UnregisterHotKey(None, i)

    def stop(self):
        if self._pynput:
            self._pynput.stop()
        elif self._thread_id:
            import ctypes

            ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT
