"""Écrire dans le logiciel actif, et lire le texte sélectionné.

Le texte passe par le presse-papiers (Ctrl+V), ce qui marche dans presque
tous les logiciels et garde les accents. Le contenu précédent du
presse-papiers est remis en place juste après.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import time

import pyperclip
from pynput.keyboard import Controller, Key

log = logging.getLogger(__name__)
_kb = Controller()
IS_WIN = sys.platform == "win32"

if IS_WIN:
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32


def foreground_window() -> int:
    return _user32.GetForegroundWindow() if IS_WIN else 0


def own_process_window(hwnd: int) -> bool:
    """Vrai si la fenêtre appartient à blablappli lui-même."""
    if not IS_WIN or not hwnd:
        return False
    pid = ctypes.c_ulong()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == _kernel32.GetCurrentProcessId()


def focus_window(hwnd: int) -> None:
    if not IS_WIN or not hwnd:
        return
    if _user32.GetForegroundWindow() == hwnd:
        return
    # petite astuce : un appui sur Alt autorise le changement de fenêtre active
    _user32.keybd_event(0x12, 0, 0, 0)
    _user32.keybd_event(0x12, 0, 2, 0)
    _user32.SetForegroundWindow(hwnd)
    time.sleep(0.08)


def wait_modifiers_released(timeout: float = 1.5) -> None:
    """Attend que Ctrl / Alt / Maj soient relâchés (après un raccourci clavier)."""
    if not IS_WIN:
        time.sleep(0.2)
        return
    end = time.time() + timeout
    while time.time() < end:
        if not any(_user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x10, 0x11, 0x12, 0x5B)):
            return
        time.sleep(0.02)


def _paste_shortcut() -> None:
    with _kb.pressed(Key.ctrl):
        _kb.press("v")
        _kb.release("v")


def _copy_shortcut() -> None:
    with _kb.pressed(Key.ctrl):
        _kb.press("c")
        _kb.release("c")


def type_text(text: str, target_hwnd: int = 0) -> None:
    """Écrit `text` à l'endroit du curseur, dans la fenêtre active."""
    if not text:
        return
    if target_hwnd and own_process_window(foreground_window()):
        focus_window(target_hwnd)
    wait_modifiers_released()
    try:
        saved = pyperclip.paste()
    except Exception:
        saved = None
    pyperclip.copy(text.replace("\n", "\r\n") if IS_WIN else text)
    time.sleep(0.05)
    _paste_shortcut()
    time.sleep(0.25)  # laisse le temps au logiciel de lire le presse-papiers
    if saved is not None:
        try:
            pyperclip.copy(saved)
        except Exception:
            pass


def get_selected_text(target_hwnd: int = 0) -> str:
    """Copie la sélection du logiciel actif et la renvoie (le presse-papiers est restauré)."""
    if target_hwnd:
        focus_window(target_hwnd)
    wait_modifiers_released()
    try:
        saved = pyperclip.paste()
    except Exception:
        saved = None
    marker = "⁣blablappli⁣"
    pyperclip.copy(marker)
    _copy_shortcut()
    text = ""
    for _ in range(25):
        time.sleep(0.03)
        try:
            text = pyperclip.paste()
        except Exception:
            text = ""
        if text != marker:
            break
    if text == marker:
        text = ""
    if saved is not None:
        try:
            pyperclip.copy(saved)
        except Exception:
            pass
    return text.replace("\r\n", "\n")
