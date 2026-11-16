"""Fenêtre "Répétitions et synonymes"."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .textutils import WORD_RE, find_repetitions, match_case

COLORS = ["#ffd37a", "#9fe3ff", "#c7f59b", "#ffb3c7", "#d9c2ff", "#ffcf9e", "#a8f0dc", "#f4f49c"]

STYLE = """
QWidget { background: #0f1720; color: #e6eef5; font-size: 11pt; }
QTextEdit { background: #f9fbfc; color: #16202a; border-radius: 8px; padding: 8px; font-size: 12pt; }
QListWidget { background: #16212c; border: 1px solid #24323f; border-radius: 6px; }
QListWidget::item { padding: 4px 6px; }
QListWidget::item:selected { background: #1f6e93; }
QPushButton { background: #1d7fa8; border: none; border-radius: 6px; padding: 7px 14px; }
QPushButton:hover { background: #2596c4; }
QPushButton#secondary { background: #2a3744; }
QLabel#title { font-size: 10pt; color: #8fb3c9; text-transform: uppercase; }
"""


class AnalysisWindow(QWidget):
    apply_requested = Signal(str)   # texte final à remettre dans le document

    def __init__(self, thesaurus, window: int = 40):
        super().__init__(None)
        self.thesaurus = thesaurus
        self.window_words = window
        self.can_apply = False
        self._current_span: tuple[int, int] | None = None
        self._reps = []
        self.setWindowTitle("blablappli · Répétitions et synonymes")
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.resize(900, 520)
        self.setStyleSheet(STYLE)

        self.edit = QTextEdit()
        self.edit.setAcceptRichText(False)
        self.edit.cursorPositionChanged.connect(self._on_cursor)
        self.edit.textChanged.connect(lambda: self._debounce.start(400))
        self._debounce = QTimer(self, singleShot=True, timeout=self.refresh)

        self.rep_list = QListWidget()
        self.rep_list.itemClicked.connect(self._on_rep_clicked)
        self.syn_title = QLabel("Synonymes")
        self.syn_title.setObjectName("title")
        self.syn_list = QListWidget()
        self.syn_list.itemClicked.connect(self._on_syn_chosen)
        self.syn_list.itemActivated.connect(self._on_syn_chosen)

        rep_title = QLabel("Mots répétés")
        rep_title.setObjectName("title")
        hint = QLabel("Clique sur un mot du texte, puis clique sur un synonyme pour le remplacer.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8fb3c9; font-size:9pt;")

        self.btn_apply = QPushButton("Remettre dans le document")
        self.btn_apply.clicked.connect(lambda: self.apply_requested.emit(self.edit.toPlainText()))
        btn_copy = QPushButton("Copier le texte")
        btn_copy.setObjectName("secondary")
        btn_copy.clicked.connect(self._copy)
        btn_close = QPushButton("Fermer")
        btn_close.setObjectName("secondary")
        btn_close.clicked.connect(self.close)

        side = QVBoxLayout()
        side.addWidget(rep_title)
        side.addWidget(self.rep_list, 2)
        side.addWidget(self.syn_title)
        side.addWidget(self.syn_list, 3)
        side.addWidget(hint)

        top = QHBoxLayout()
        top.addWidget(self.edit, 3)
        top.addLayout(side, 2)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(btn_copy)
        buttons.addWidget(self.btn_apply)
        buttons.addWidget(btn_close)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addLayout(buttons)

    def open_with(self, text: str, can_apply: bool, focus_word: str | None = None):
        self.can_apply = can_apply
        self.btn_apply.setVisible(can_apply)
        self.edit.blockSignals(True)
        self.edit.setPlainText(text)
        self.edit.blockSignals(False)
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()
        if focus_word:
            self._show_synonyms(focus_word)

    # --- Répétitions ------------------------------------------------------------
    def refresh(self):
        text = self.edit.toPlainText()
        self._reps = find_repetitions(text, window=self.window_words)
        self.rep_list.clear()
        sels = []
        for i, rep in enumerate(self._reps):
            color = QColor(COLORS[i % len(COLORS)])
            item = QListWidgetItem(f"{rep.label}  ×{rep.count}")
            item.setForeground(color)
            item.setData(Qt.UserRole, i)
            self.rep_list.addItem(item)
            fmt = QTextCharFormat()
            fmt.setBackground(color)
            for s, e in rep.spans:
                sel = QTextEdit.ExtraSelection()
                cur = QTextCursor(self.edit.document())
                cur.setPosition(s)
                cur.setPosition(e, QTextCursor.KeepAnchor)
                sel.cursor = cur
                sel.format = fmt
                sels.append(sel)
        if not self._reps:
            item = QListWidgetItem("Aucune répétition repérée 👍")
            item.setFlags(Qt.NoItemFlags)
            self.rep_list.addItem(item)
        self.edit.setExtraSelections(sels)

    def _on_rep_clicked(self, item: QListWidgetItem):
        idx = item.data(Qt.UserRole)
        if idx is None:
            return
        rep = self._reps[idx]
        # on se place sur la 2e occurrence (c'est en général celle qu'on veut changer)
        s, e = rep.spans[1] if len(rep.spans) > 1 else rep.spans[0]
        cur = self.edit.textCursor()
        cur.setPosition(s)
        cur.setPosition(e, QTextCursor.KeepAnchor)
        self.edit.setTextCursor(cur)
        self._current_span = (s, e)
        self._show_synonyms(self.edit.toPlainText()[s:e])

    # --- Synonymes ----------------------------------------------------------------
    def _on_cursor(self):
        text = self.edit.toPlainText()
        pos = self.edit.textCursor().position()
        for m in WORD_RE.finditer(text):
            if m.start() <= pos <= m.end():
                if self._current_span != (m.start(), m.end()):
                    self._current_span = (m.start(), m.end())
                    self._show_synonyms(m.group(0))
                return

    def _show_synonyms(self, word: str):
        self.syn_list.clear()
        self.syn_title.setText(f"Synonymes de « {word} »")
        if not self.thesaurus.available:
            self.syn_list.addItem("Dictionnaire des synonymes non installé (relance l'installation).")
            return
        meanings = self.thesaurus.lookup(word)
        if not meanings:
            self.syn_list.addItem("Pas de synonyme trouvé.")
            return
        shown = set()
        for pos, syns in meanings[:8]:
            head = QListWidgetItem(f"— {pos} —" if pos else "—")
            head.setFlags(Qt.NoItemFlags)
            head.setForeground(QColor("#6f8fa5"))
            self.syn_list.addItem(head)
            for s in syns[:10]:
                if s.lower() in shown or s.lower() == word.lower():
                    continue
                shown.add(s.lower())
                it = QListWidgetItem(match_case(word, s))
                it.setData(Qt.UserRole, s)
                self.syn_list.addItem(it)

    def _on_syn_chosen(self, item: QListWidgetItem):
        if item.data(Qt.UserRole) is None or not self._current_span:
            return
        s, e = self._current_span
        text = self.edit.toPlainText()
        original = text[s:e]
        repl = match_case(original, item.data(Qt.UserRole))
        cur = self.edit.textCursor()
        cur.setPosition(s)
        cur.setPosition(e, QTextCursor.KeepAnchor)
        cur.insertText(repl)
        self._current_span = (s, s + len(repl))
        self.refresh()

    def _copy(self):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.edit.toPlainText())
