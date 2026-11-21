"""Essai complet de blablappli, comme un vrai utilisateur (utilisé par la fabrication automatique).

    blablappli.exe --e2e rapport.txt dossier_audio

Le dossier contient des phrases enregistrées (01.wav, 02.wav…) et leur texte
attendu (01.txt, 02.txt…). Un faux micro « prononce » ces phrases.

Ce qui est vérifié, dans le Bloc-notes de Windows :
  1. clic sur le cercle → dictée → clic → le texte arrive dans le Bloc-notes,
     et le cercle ne vole pas la main au Bloc-notes ;
  2. la même chose en dictée continue (le texte s'écrit à chaque pause) ;
  3. le raccourci Ctrl+Alt+D ;
  4. la lecture du texte sélectionné, les synonymes et les répétitions.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import re
import subprocess
import threading
import time
import traceback
import unicodedata
import wave
from pathlib import Path

import numpy as np

SR = 16000
user32 = ctypes.windll.user32


# --- Audio ---------------------------------------------------------------------------
def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[width]
    a = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    if width == 1:
        a = (a - 128) / 128
    else:
        a /= float(np.iinfo(dtype).max)
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if rate != SR:
        n = int(len(a) * SR / rate)
        a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)
    return a * (0.5 / max(1e-6, float(np.abs(a).max())))  # volume de voix normal


class FakeMic:
    """Remplace le micro : joue en temps réel l'audio qu'on lui donne, puis du silence."""

    audio = np.zeros(0, dtype=np.float32)

    def __init__(self, samplerate, channels, dtype, blocksize, device, callback):
        self.block = blocksize
        self.cb = callback
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        pos, t0 = 0, time.time()
        rng = np.random.default_rng(0)
        while self.running:
            chunk = FakeMic.audio[pos:pos + self.block]
            if len(chunk) < self.block:  # bruit de fond léger après la phrase
                chunk = np.concatenate([chunk, rng.normal(0, 0.0015, self.block - len(chunk)).astype(np.float32)])
            self.cb(chunk.reshape(-1, 1), self.block, None, None)
            pos += self.block
            delay = t0 + pos / SR - time.time()
            if delay > 0:
                time.sleep(delay)

    def stop(self):
        self.running = False

    def close(self):
        pass


# --- Bloc-notes -------------------------------------------------------------------------
WM_GETTEXT, WM_GETTEXTLENGTH, WM_SETTEXT, EM_SETSEL = 0x0D, 0x0E, 0x0C, 0xB1


def _class(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _children(hwnd) -> list[int]:
    out = []
    proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)(lambda h, _: out.append(h) or True)
    user32.EnumChildWindows(hwnd, proc, 0)
    return out


class Notepad:
    def __init__(self):
        subprocess.Popen(["notepad.exe"])
        self.hwnd = 0
        for _ in range(100):
            self.hwnd = user32.FindWindowW("Notepad", None)
            if self.hwnd and self._edit():
                break
            time.sleep(0.2)
        if not self.hwnd:
            raise RuntimeError("Bloc-notes introuvable")
        self.edit = self._edit()
        if not self.edit:
            raise RuntimeError(f"zone de texte du Bloc-notes introuvable ({[_class(h) for h in _children(self.hwnd)]})")

    def _edit(self) -> int:
        for h in _children(self.hwnd):
            if "edit" in _class(h).lower():
                return h
        return 0

    def text(self) -> str:
        n = user32.SendMessageW(self.edit, WM_GETTEXTLENGTH, 0, 0)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.SendMessageW(self.edit, WM_GETTEXT, n + 1, buf)
        return buf.value.replace("\r\n", "\n")

    def clear(self):
        user32.SendMessageW(self.edit, WM_SETTEXT, 0, ctypes.c_wchar_p(""))

    def select_all(self):
        user32.SendMessageW(self.edit, EM_SETSEL, 0, -1)

    def focus(self):
        r = wt.RECT()
        user32.GetWindowRect(self.edit, ctypes.byref(r))
        click((r.left + r.right) // 2, (r.top + r.bottom) // 2)
        time.sleep(0.3)


def click(x: int, y: int):
    user32.SetCursorPos(x, y)
    time.sleep(0.05)
    user32.mouse_event(0x02, 0, 0, 0, 0)
    time.sleep(0.06)
    user32.mouse_event(0x04, 0, 0, 0, 0)


def foreground_is(hwnd) -> bool:
    return user32.GetAncestor(user32.GetForegroundWindow(), 2) == user32.GetAncestor(hwnd, 2)


# --- Comparaison de textes ------------------------------------------------------------------
def words(s: str) -> list[str]:
    s = unicodedata.normalize("NFC", s.lower().replace("’", "'"))
    return re.findall(r"[\w']+", s)


def wer(ref: str, hyp: str) -> float:
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, hw in enumerate(h, 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (rw != hw))
            prev, d[j] = d[j], cur
    return d[len(h)] / max(1, len(r))


# --- Essai ---------------------------------------------------------------------------------
def run(out_path: str, audio_dir: str) -> int:
    import sounddevice

    from PySide6.QtCore import QMetaObject, Qt
    from PySide6.QtWidgets import QApplication

    from . import insert
    from .app import App

    lines: list[str] = []
    ok = True

    def log(s):
        lines.append(s)
        Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def check(name, cond, detail=""):
        nonlocal ok
        ok &= bool(cond)
        log(f"{'OK  ' if cond else 'FAIL'} {name}{' : ' + detail if detail else ''}")

    folder = Path(audio_dir)
    clips = [(read_wav(w), w.with_suffix(".txt").read_text(encoding="utf-8").strip()) for w in sorted(folder.glob("*.wav"))]
    pause = np.zeros(int(1.6 * SR), dtype=np.float32)
    all_audio = np.concatenate([np.concatenate([a, pause]) for a, _ in clips])
    expected = " ".join(t for _, t in clips)

    sounddevice.InputStream = FakeMic  # le faux micro remplace le vrai

    qapp = QApplication([])
    qapp.setQuitOnLastWindowClosed(False)
    app = App(qapp)

    def wait(cond, timeout, step=0.1):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            time.sleep(step)
        return False

    def bubble_center():
        r = wt.RECT()
        user32.GetWindowRect(int(app.bubble.winId()), ctypes.byref(r))
        return (r.left + r.right) // 2, (r.top + r.bottom) // 2

    def idle():
        return app.recorder is None and app.pending == 0 and app.jobs.empty()

    def scenario():
        try:
            t0 = time.time()
            ready = wait(lambda: app.stt is not None, 1800, 0.5)
            check("modèle Whisper chargé", ready, f"{time.time() - t0:.0f} s, correcteur {getattr(app.corrector, 'engine', None)}")
            if not ready:
                return
            pad = Notepad()
            log(f"     Bloc-notes : zone de texte « {_class(pad.edit)} »")

            # 1. clic sur le cercle
            pad.clear()
            pad.focus()
            FakeMic.audio = all_audio
            click(*bubble_center())
            started = wait(lambda: app.recorder is not None, 5)
            check("clic sur le cercle : la dictée démarre", started)
            time.sleep(0.5)
            check("le cercle ne prend pas la main au Bloc-notes", foreground_is(pad.hwnd))
            time.sleep(len(all_audio) / SR + 0.5)
            click(*bubble_center())
            t1 = time.time()
            wait(idle, 300)
            got = pad.text()
            e = wer(expected, got)
            check("texte dicté écrit dans le Bloc-notes", e <= 0.25, f"{time.time() - t1:.1f} s, erreurs {e:.0%}\n       attendu : {expected}\n       obtenu  : {got}")
            check("ponctuation dictée (« virgule », « point d'interrogation »)", "," in got and "?" in got)
            check("majuscule en début de texte", got[:1].isupper())
            check("le Bloc-notes garde la main après l'écriture", foreground_is(pad.hwnd))

            # 2. dictée continue
            app.cfg.continuous = True
            pad.clear()
            pad.focus()
            FakeMic.audio = all_audio
            click(*bubble_center())
            tc = time.time()
            wait(lambda: app.recorder is not None, 5)
            first = clips[0][0]
            partial = wait(lambda: len(pad.text()) > 5, len(first) / SR + 25)
            check("dictée continue : le texte s'écrit pendant que je parle", partial and app.recorder is not None, repr(pad.text()[:60]))
            time.sleep(max(0.0, tc + len(all_audio) / SR + 1.5 - time.time()))
            wait(lambda: app.pending == 0 and app.jobs.empty(), 120)
            time.sleep(2)
            click(*bubble_center())
            wait(idle, 120)
            got = pad.text()
            e = wer(expected, got)
            check("dictée continue : tout le texte est écrit", e <= 0.25, f"erreurs {e:.0%}\n       obtenu  : {got}")
            app.cfg.continuous = False

            # 3. raccourci clavier
            from pynput.keyboard import Controller, Key

            kb = Controller()
            pad.clear()
            pad.focus()
            FakeMic.audio = clips[0][0]
            with kb.pressed(Key.ctrl, Key.alt):
                kb.press("d"); kb.release("d")
            started = wait(lambda: app.recorder is not None, 5)
            check("Ctrl+Alt+D démarre la dictée", started)
            time.sleep(len(clips[0][0]) / SR + 0.8)
            with kb.pressed(Key.ctrl, Key.alt):
                kb.press("d"); kb.release("d")
            wait(idle, 120)
            got = pad.text()
            check("Ctrl+Alt+D : texte écrit", wer(clips[0][1], got) <= 0.3, got)

            # 4. sélection, synonymes, répétitions
            pad.focus()
            user32.SendMessageW(pad.edit, WM_SETTEXT, 0, ctypes.c_wchar_p("La maison est belle. La maison est grande."))
            pad.select_all()
            sel = insert.get_selected_text(pad.hwnd)
            check("lecture du texte sélectionné", sel == "La maison est belle. La maison est grande.", repr(sel))
            from .textutils import find_repetitions

            reps = [r.label for r in find_repetitions(sel)]
            check("répétitions trouvées", "maison" in reps, str(reps))
            syn = app.thesaurus.synonyms("maison")[:6]
            check("synonymes de « maison »", bool(syn), ", ".join(syn))
        except Exception:
            check("déroulement de l'essai", False, traceback.format_exc())
        finally:
            subprocess.run(["taskkill", "/IM", "notepad.exe", "/F"], capture_output=True)
            QMetaObject.invokeMethod(qapp, "quit", Qt.QueuedConnection)

    threading.Thread(target=scenario, daemon=True).start()
    qapp.exec()
    log("RÉSULTAT : " + ("tout fonctionne" if ok else "ÉCHEC"))
    return 0 if ok else 1
