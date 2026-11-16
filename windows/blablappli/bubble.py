"""Le cercle flottant façon "Jarvis"."""

from __future__ import annotations

import math
import sys
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QApplication, QWidget

# couleurs par état : (principale, secondaire)
PALETTE = {
    "loading": ("#7d8b99", "#3a4550"),
    "idle": ("#39d0ff", "#0d3550"),
    "listening": ("#5ff3ff", "#0a6c9a"),
    "processing": ("#ffc35c", "#6a4300"),
    "error": ("#ff5c6c", "#5a0d16"),
}


class Bubble(QWidget):
    clicked = Signal()
    pressed = Signal()                 # juste avant un clic : on mémorise la fenêtre active
    menu_requested = Signal(QPoint)
    moved = Signal(int, int)

    def __init__(self, size: int = 76):
        super().__init__(None)
        self.core = size
        self.margin = 22
        side = size + 2 * self.margin
        self.setFixedSize(side, side)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setToolTip("blablappli\nClic : démarrer / arrêter la dictée\nClic droit : options, synonymes, répétitions")
        self.state = "loading"
        self.level_source = lambda: 0.0
        self.level = 0.0
        self.continuous = False
        self.badge = 0                 # nombre de mots répétés dans la dernière dictée
        self._angle = 0.0
        self._t0 = time.time()
        self._press_pos = None
        self._drag_offset = None
        self._dragging = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    # --- Windows : ne jamais prendre le focus du logiciel où l'on écrit -------
    def showEvent(self, e):
        super().showEvent(e)
        if sys.platform == "win32":
            import ctypes

            hwnd = int(self.winId())
            GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST = -20, 0x08000000, 0x80, 0x8
            u = ctypes.windll.user32
            style = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
            u.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST)

    def set_state(self, state: str) -> None:
        self.state = state
        self.update()

    def _tick(self):
        speed = {"loading": 4, "idle": 0.6, "listening": 3.5, "processing": 7, "error": 0}[self.state]
        self._angle = (self._angle + speed) % 360
        target = self.level_source() if self.state == "listening" else 0.0
        self.level += (target - self.level) * 0.35
        self.update()

    # --- Dessin ---------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        main, dark = (QColor(c) for c in PALETTE[self.state])
        c = QPointF(self.width() / 2, self.height() / 2)
        r = self.core / 2
        t = time.time() - self._t0

        # halo qui suit la voix
        breathe = 0.5 + 0.5 * math.sin(t * 2.2)
        glow_r = r + 6 + self.level * 16 + (breathe * 3 if self.state == "idle" else 0)
        g = QRadialGradient(c, glow_r)
        halo = QColor(main)
        halo.setAlpha(110 if self.state == "listening" else 55)
        g.setColorAt(0.55, halo)
        halo.setAlpha(0)
        g.setColorAt(1.0, halo)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(c, glow_r, glow_r)

        # disque central
        core = QRadialGradient(c - QPointF(r * 0.3, r * 0.3), r * 1.3)
        light = QColor(main)
        light.setAlpha(235)
        core.setColorAt(0.0, light)
        core.setColorAt(0.55, dark)
        core.setColorAt(1.0, QColor("#050b12"))
        p.setBrush(core)
        p.drawEllipse(c, r * 0.78, r * 0.78)

        # anneau extérieur : 3 arcs qui tournent
        ring = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        pen = QPen(main, 3.2, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        for k in range(3):
            start = (self._angle + k * 120) * 16
            p.drawArc(ring, int(start), int(70 * 16))

        # anneau intérieur fin, sens inverse, en pointillés
        inner = r * 0.9
        ring2 = QRectF(c.x() - inner, c.y() - inner, 2 * inner, 2 * inner)
        faint = QColor(main)
        faint.setAlpha(150)
        pen2 = QPen(faint, 1.4, Qt.CustomDashLine, Qt.FlatCap)
        pen2.setDashPattern([2, 4])
        p.setPen(pen2)
        p.save()
        p.translate(c)
        p.rotate(-self._angle * 1.6)
        p.translate(-c)
        p.drawEllipse(ring2)
        p.restore()

        # icône micro
        self._draw_mic(p, c, r * 0.36, QColor("#eafcff") if self.state != "loading" else QColor("#c8d0d8"))

        # pastilles
        if self.continuous:
            self._pill(p, QPointF(c.x() + r * 0.72, c.y() + r * 0.72), "∞", QColor("#1fd18b"))
        if self.badge:
            self._pill(p, QPointF(c.x() + r * 0.72, c.y() - r * 0.72), str(self.badge), QColor("#ff9a3c"))
        p.end()

    def _draw_mic(self, p: QPainter, c: QPointF, s: float, color: QColor):
        p.setPen(QPen(color, max(1.6, s * 0.16), Qt.SolidLine, Qt.RoundCap))
        p.setBrush(color if self.state == "listening" else Qt.NoBrush)
        body = QRectF(c.x() - s * 0.38, c.y() - s * 0.95, s * 0.76, s * 1.25)
        p.drawRoundedRect(body, s * 0.38, s * 0.38)
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        arc = QRectF(c.x() - s * 0.7, c.y() - s * 0.6, s * 1.4, s * 1.2)
        path.arcMoveTo(arc, 200)
        path.arcTo(arc, 200, 140)
        p.drawPath(path)
        p.drawLine(QPointF(c.x(), c.y() + s * 0.6), QPointF(c.x(), c.y() + s * 0.95))

    def _pill(self, p: QPainter, at: QPointF, text: str, color: QColor):
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawEllipse(at, 10, 10)
        p.setPen(QColor("white"))
        f = QFont()
        f.setBold(True)
        f.setPointSize(8)
        p.setFont(f)
        p.drawText(QRectF(at.x() - 10, at.y() - 10, 20, 20), Qt.AlignCenter, text)

    # --- Souris -----------------------------------------------------------------
    def mousePressEvent(self, e):
        self.pressed.emit()
        if e.button() == Qt.LeftButton:
            self._press_pos = e.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._dragging = False
        elif e.button() == Qt.RightButton:
            self.menu_requested.emit(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._press_pos is None:
            return
        pos = e.globalPosition().toPoint()
        if not self._dragging and (pos - self._press_pos).manhattanLength() > 6:
            self._dragging = True
        if self._dragging:
            self.move(pos - self._drag_offset)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._press_pos is None:
            return
        if self._dragging:
            self.moved.emit(self.x(), self.y())
        else:
            self.clicked.emit()
        self._press_pos = None
        self._dragging = False

    def place_default(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 30, screen.bottom() - self.height() - 60)
