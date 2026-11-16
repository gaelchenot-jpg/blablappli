"""blablappli : dictée vocale en français, dans n'importe quel logiciel."""

from __future__ import annotations

import logging
import queue
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QPoint, Signal
from PySide6.QtGui import QActionGroup, QCursor
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QToolTip

from . import insert
from .analysis import AnalysisWindow
from .audio import Recorder, list_microphones
from .bubble import Bubble
from .config import MODELS, Config, app_dir
from .textutils import apply_voice_commands, find_repetitions, join_segment, match_case
from .thesaurus import Thesaurus

log = logging.getLogger("blablappli")


class Bridge(QObject):
    """Fait passer les évènements des fils de travail vers l'interface."""

    state = Signal(str)
    ready = Signal(str)
    error = Signal(str)
    toggle = Signal()
    synonyms = Signal()
    repetitions = Signal()
    show_synonyms_menu = Signal(str, int)
    open_analysis = Signal(str, int)
    badge = Signal(int)
    notify = Signal(str)


class App:
    def __init__(self, qapp: QApplication):
        self.qapp = qapp
        self.cfg = Config.load()
        self.bridge = Bridge()
        self.stt = None
        self.corrector = None
        self.thesaurus = Thesaurus()
        self.recorder: Recorder | None = None
        self.target_hwnd = 0
        self.session_text = ""       # texte dicté depuis le dernier démarrage
        self.last_dictation = ""
        self.jobs: queue.Queue = queue.Queue()
        self.pending = 0
        self._pending_lock = threading.Lock()

        self.bubble = Bubble(self.cfg.bubble_size)
        self.bubble.continuous = self.cfg.continuous
        self.bubble.level_source = lambda: self.recorder.level if self.recorder else 0.0
        if self.cfg.bubble_x is not None:
            self.bubble.move(self.cfg.bubble_x, self.cfg.bubble_y)
        else:
            self.bubble.place_default()
        self.bubble.pressed.connect(self.remember_target)
        self.bubble.clicked.connect(self.toggle_dictation)
        self.bubble.menu_requested.connect(self.show_menu)
        self.bubble.moved.connect(self._save_pos)
        self.bubble.show()

        self.analysis = AnalysisWindow(self.thesaurus, self.cfg.repetition_window)
        self.analysis.apply_requested.connect(self._apply_from_analysis)
        self._analysis_target = 0

        b = self.bridge
        b.state.connect(self.bubble.set_state)
        b.ready.connect(self._on_ready)
        b.error.connect(self._on_error)
        b.toggle.connect(self._toggle_from_hotkey)
        b.synonyms.connect(self.synonyms_of_selection)
        b.repetitions.connect(self.repetitions_of_selection)
        b.show_synonyms_menu.connect(self._synonyms_menu)
        b.open_analysis.connect(self._open_analysis)
        b.badge.connect(self._set_badge)
        b.notify.connect(self._notify)

        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._load_engines, daemon=True).start()
        self._start_hotkeys()

    # --- Chargement ---------------------------------------------------------------
    def _load_engines(self, only_model: bool = False):
        self.bridge.state.emit("loading")
        try:
            if not only_model:
                from .corrector import Corrector

                self.corrector = Corrector()
            from .stt import SpeechToText

            self.stt = None
            self.stt = SpeechToText(self.cfg.model, self.cfg.device)
            self.bridge.ready.emit(self.cfg.model)
        except Exception as e:
            log.exception("chargement")
            self.bridge.error.emit(str(e))

    def _on_ready(self, model):
        self.bubble.set_state("idle")
        engine = self.corrector.engine if self.corrector else "aucun"
        self._notify(f"blablappli est prêt.\nModèle : {MODELS.get(model, model)}\nCorrecteur : {engine}")

    def _on_error(self, msg):
        self.bubble.set_state("error")
        QMessageBox.warning(None, "blablappli", f"Un problème est survenu :\n\n{msg}\n\nDétails dans {app_dir() / 'blablappli.log'}")

    def _notify(self, text):
        QToolTip.showText(self.bubble.mapToGlobal(QPoint(0, -10)), text, self.bubble, self.bubble.rect(), 3500)

    # --- Dictée ---------------------------------------------------------------------
    def remember_target(self):
        hwnd = insert.foreground_window()
        if hwnd and not insert.own_process_window(hwnd):
            self.target_hwnd = hwnd

    def _toggle_from_hotkey(self):
        self.remember_target()
        self.toggle_dictation()

    def toggle_dictation(self):
        if self.stt is None:
            self._notify("Encore un instant, le modèle de reconnaissance se charge…")
            return
        if self.recorder is None:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        self.session_text = ""
        self.bubble.badge = 0
        self.recorder = Recorder(
            mic_index=self.cfg.mic_index,
            silence_seconds=self.cfg.silence_seconds,
            continuous=self.cfg.continuous,
            on_segment=lambda audio: self._enqueue(audio),
        )
        try:
            self.recorder.start()
        except Exception as e:
            log.exception("micro")
            self.recorder = None
            self._on_error(f"Impossible d'ouvrir le micro : {e}")
            return
        self.bubble.set_state("listening")

    def _stop_recording(self):
        rec, self.recorder = self.recorder, None
        audio = rec.stop()
        if audio is not None:
            self._enqueue(audio)
        if self.pending == 0:
            self.bubble.set_state("idle")

    def _enqueue(self, audio):
        with self._pending_lock:
            self.pending += 1
        if self.recorder is None:
            self.bridge.state.emit("processing")
        self.jobs.put(audio)

    def _worker(self):
        while True:
            audio = self.jobs.get()
            try:
                stt = self.stt
                text = stt.transcribe(audio, context=self.session_text) if stt else ""
                if text:
                    if self.cfg.voice_commands:
                        text = apply_voice_commands(text)
                    if self.cfg.autocorrect and self.corrector:
                        text = self.corrector.correct(text)
                    piece = join_segment(self.session_text, text)
                    insert.type_text(piece, self.target_hwnd)
                    self.session_text += piece
                    self.last_dictation = self.session_text
                    reps = find_repetitions(self.session_text, window=self.cfg.repetition_window)
                    self.bridge.badge.emit(len(reps))
            except Exception as e:
                log.exception("transcription")
                self.bridge.notify.emit(f"Erreur : {e}")
            finally:
                with self._pending_lock:
                    self.pending -= 1
                    left = self.pending
                if left == 0:
                    self.bridge.state.emit("listening" if self.recorder else "idle")

    def _set_badge(self, n):
        self.bubble.badge = n
        self.bubble.update()

    # --- Synonymes et répétitions ---------------------------------------------------------
    def synonyms_of_selection(self):
        target = self.target_hwnd

        def job():
            word = insert.get_selected_text(target).strip()
            self.bridge.show_synonyms_menu.emit(word, target)

        threading.Thread(target=job, daemon=True).start()

    def _synonyms_menu(self, word: str, target: int):
        if not word:
            self._notify("Sélectionne d'abord un mot dans ton texte.")
            return
        if " " in word.strip() or len(word) > 40:
            # plus d'un mot : on ouvre la fenêtre d'analyse
            self._open_analysis(word, target)
            return
        if not self.thesaurus.available:
            self._notify("Le dictionnaire des synonymes n'est pas installé.")
            return
        meanings = self.thesaurus.lookup(word)
        if not meanings:
            self._notify(f"Pas de synonyme trouvé pour « {word} ».")
            return
        menu = QMenu()
        menu.setStyleSheet("QMenu{background:#0f1720;color:#e6eef5;padding:4px;} QMenu::item:selected{background:#1f6e93;}")
        seen = set()
        for pos, syns in meanings[:6]:
            if pos:
                menu.addSection(pos)
            for s in syns[:8]:
                if s.lower() in seen or s.lower() == word.lower():
                    continue
                seen.add(s.lower())
                act = menu.addAction(match_case(word, s))
                act.triggered.connect(lambda _=False, rep=match_case(word, s): self._replace_selection(rep, target))
        menu.addSeparator()
        menu.addAction("Plus de choix…").triggered.connect(lambda: self._open_analysis(word, target, can_apply=True))
        menu.exec(QCursor.pos())

    def _replace_selection(self, text: str, target: int):
        threading.Thread(target=lambda: insert.type_text(text, target), daemon=True).start()

    def repetitions_of_selection(self):
        target = self.target_hwnd

        def job():
            text = insert.get_selected_text(target)
            self.bridge.open_analysis.emit(text, target)

        threading.Thread(target=job, daemon=True).start()

    def _open_analysis(self, text: str, target: int, can_apply: bool = True):
        if not text.strip():
            self._notify("Sélectionne d'abord le texte à analyser.")
            return
        self._analysis_target = target
        focus = text.strip() if " " not in text.strip() else None
        self.analysis.open_with(text, can_apply=can_apply and bool(target), focus_word=focus)

    def open_last_dictation(self):
        if not self.last_dictation:
            self._notify("Rien n'a encore été dicté.")
            return
        self._analysis_target = 0
        self.analysis.open_with(self.last_dictation, can_apply=False)

    def _apply_from_analysis(self, text: str):
        self.analysis.hide()
        target = self._analysis_target
        threading.Thread(target=lambda: insert.type_text(text, target), daemon=True).start()

    # --- Raccourcis clavier ------------------------------------------------------------------
    def _start_hotkeys(self):
        try:
            from pynput import keyboard

            self._hotkeys = keyboard.GlobalHotKeys(
                {
                    self.cfg.hotkey_dictation: self.bridge.toggle.emit,
                    self.cfg.hotkey_synonyms: lambda: (self._remember_now(), self.bridge.synonyms.emit()),
                    self.cfg.hotkey_repetitions: lambda: (self._remember_now(), self.bridge.repetitions.emit()),
                }
            )
            self._hotkeys.start()
        except Exception:
            log.exception("raccourcis clavier")

    def _remember_now(self):
        self.remember_target()

    # --- Menu (clic droit) ------------------------------------------------------------------
    def show_menu(self, pos: QPoint):
        m = QMenu()
        m.setStyleSheet("QMenu{background:#0f1720;color:#e6eef5;padding:4px;} QMenu::item{padding:5px 18px;} QMenu::item:selected{background:#1f6e93;} QMenu::separator{height:1px;background:#24323f;margin:4px 8px;}")
        a = m.addAction("Arrêter la dictée" if self.recorder else "Démarrer la dictée")
        a.triggered.connect(self.toggle_dictation)
        m.addSeparator()
        m.addAction("Synonymes du mot sélectionné   (Ctrl+Alt+S)").triggered.connect(self.synonyms_of_selection)
        m.addAction("Répétitions du texte sélectionné   (Ctrl+Alt+R)").triggered.connect(self.repetitions_of_selection)
        last = m.addAction("Répétitions de la dernière dictée")
        last.triggered.connect(self.open_last_dictation)
        last.setEnabled(bool(self.last_dictation))
        m.addSeparator()

        cont = m.addAction("Dictée continue (écrit à chaque pause)")
        cont.setCheckable(True)
        cont.setChecked(self.cfg.continuous)
        cont.toggled.connect(self._set_continuous)
        corr = m.addAction("Corriger automatiquement")
        corr.setCheckable(True)
        corr.setChecked(self.cfg.autocorrect)
        corr.toggled.connect(lambda v: self._set("autocorrect", v))
        cmds = m.addAction("Commandes vocales (« à la ligne »…)")
        cmds.setCheckable(True)
        cmds.setChecked(self.cfg.voice_commands)
        cmds.toggled.connect(lambda v: self._set("voice_commands", v))

        models = m.addMenu("Précision de la reconnaissance")
        group = QActionGroup(models)
        for key, label in MODELS.items():
            act = models.addAction(label)
            act.setCheckable(True)
            act.setChecked(key == self.cfg.model)
            group.addAction(act)
            act.triggered.connect(lambda _=False, k=key: self._set_model(k))

        mics = m.addMenu("Micro")
        mgroup = QActionGroup(mics)
        act = mics.addAction("Micro par défaut de Windows")
        act.setCheckable(True)
        act.setChecked(self.cfg.mic_index is None)
        mgroup.addAction(act)
        act.triggered.connect(lambda: self._set("mic_index", None))
        for idx, name in list_microphones():
            act = mics.addAction(name)
            act.setCheckable(True)
            act.setChecked(idx == self.cfg.mic_index)
            mgroup.addAction(act)
            act.triggered.connect(lambda _=False, i=idx: self._set("mic_index", i))

        if sys.platform == "win32":
            auto = m.addAction("Lancer au démarrage de Windows")
            auto.setCheckable(True)
            auto.setChecked(_autostart_enabled())
            auto.toggled.connect(_set_autostart)

        m.addSeparator()
        m.addAction("Quitter blablappli").triggered.connect(self.quit)
        m.exec(pos)

    def _set(self, key, value):
        setattr(self.cfg, key, value)
        self.cfg.save()

    def _set_continuous(self, value):
        self._set("continuous", value)
        self.bubble.continuous = value
        if self.recorder:
            self.recorder.continuous = value

    def _set_model(self, key):
        if key == self.cfg.model:
            return
        self._set("model", key)
        self._notify("Changement de modèle… (le premier téléchargement peut prendre quelques minutes)")
        threading.Thread(target=self._load_engines, kwargs={"only_model": True}, daemon=True).start()

    def _save_pos(self, x, y):
        self.cfg.bubble_x, self.cfg.bubble_y = x, y
        self.cfg.save()

    def quit(self):
        if self.recorder:
            self.recorder.stop()
        self.cfg.save()
        self.qapp.quit()


# --- Démarrage avec Windows ----------------------------------------------------------------
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _launcher() -> str:
    vbs = Path(__file__).resolve().parent.parent / "lancer.vbs"
    return f'wscript.exe "{vbs}"'


def _autostart_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.QueryValueEx(k, "blablappli")
            return True
    except Exception:
        return False


def _set_autostart(on: bool) -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, "blablappli", 0, winreg.REG_SZ, _launcher())
        else:
            try:
                winreg.DeleteValue(k, "blablappli")
            except FileNotFoundError:
                pass


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(app_dir() / "blablappli.log", encoding="utf-8"), logging.StreamHandler()],
    )
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setApplicationName("blablappli")
    lock = QLockFile(str(app_dir() / "blablappli.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, "blablappli", "blablappli est déjà lancé (le cercle est sur ton écran).")
        return 0
    app = App(qapp)  # noqa: F841
    return qapp.exec()
