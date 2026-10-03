"""App-wide motion helpers.

The original ClickMotion attached a QGraphicsOpacityEffect to *every* pressed
button from an application-level event filter. Graphics effects re-parent the
widget's paint path and are a known source of crashes/flicker next to
WebEngine surfaces, so button feedback now comes from the stylesheet
(:hover / :pressed states) and this class is kept as a compatible no-op so
existing call-sites keep working.
"""
from PySide6.QtCore import (QObject, QPropertyAnimation, QEasingCurve,
                            QAbstractAnimation)


class ClickMotion(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)

    def install(self, app):
        return None

    def pulse(self, widget):
        return None


def fade_in(window, ms=140):
    """Fade a *top-level* window in via windowOpacity (safe, no effects)."""
    try:
        window.setWindowOpacity(0.0)
        anim = QPropertyAnimation(window, b"windowOpacity", window)
        anim.setDuration(ms)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        window._fade_anim = anim
    except Exception:
        window.setWindowOpacity(1.0)
