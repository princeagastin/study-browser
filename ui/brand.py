"""Single source of truth for the product brand.

To rename the browser, edit ONLY the three constants below.
Alternatives that fit the research vision:
    Zettel, Scholia, Marginalia, Lectern, Athenaeum
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QLinearGradient

NAME = "Folio"
TAGLINE = "Your browser. Your workspace."
MONOGRAM = "F"
ACCENT = "#2F5FE0"
ACCENT_DARK = "#274DBE"


def app_icon() -> QIcon:
    px = QPixmap(64, 64)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, 0, 64)
    grad.setColorAt(0.0, QColor(ACCENT))
    grad.setColorAt(1.0, QColor(ACCENT_DARK))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(0, 0, 64, 64, 16, 16)
    p.setPen(QColor("#FFFFFF"))
    size = 26 if len(MONOGRAM) <= 1 else 18
    p.setFont(QFont("Segoe UI", size, QFont.Weight.Bold))
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, MONOGRAM)
    p.end()
    return QIcon(px)