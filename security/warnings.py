from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)

from security.models import SiteReport, Verdict
from ui import icons, brand
from ui.theme import TOKENS as T
from ui.widgets import Switch, caption


def verdict_color(verdict: Verdict) -> str:
    """Resolved at call time so it follows light/dark/accent changes."""
    return {
        Verdict.SAFE: T["success"],
        Verdict.UNKNOWN: T["ink2"],
        Verdict.CAUTION: T["warn"],
        Verdict.DANGER: T["danger"],
    }.get(verdict, T["ink2"])


_VERDICT_TEXT = {
    Verdict.SAFE: ("Looks safe", "No warning signs were found for this site."),
    Verdict.UNKNOWN: ("Not rated", "Folio has no strong signal either way."),
    Verdict.CAUTION: ("Be careful", "A few things about this site are unusual."),
    Verdict.DANGER: ("Potentially dangerous", "This site shows signs of phishing or spoofing."),
}


class SecurityBanner(QFrame):
    proceed_clicked = Signal()
    dismiss_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("secBanner")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)
        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(20, 20)
        self.text = QLabel(self)
        self.text.setWordWrap(True)
        self.proceed = QPushButton("Proceed anyway", self)
        self.proceed.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back = QPushButton("Back to safety", self)
        self.back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back.setDefault(True)
        self.proceed.clicked.connect(lambda: self.proceed_clicked.emit())
        self.back.clicked.connect(lambda: self.dismiss_clicked.emit())
        lay.addWidget(self.icon_label)
        lay.addWidget(self.text, 1)
        lay.addWidget(self.proceed)
        lay.addWidget(self.back)
        self.hide()

    def show_report(self, report: SiteReport):
        col = verdict_color(report.verdict)
        self.icon_label.setPixmap(icons.pixmap("warning", 20, col))
        reasons = "; ".join(r for r in report.reasons[:3])
        self.text.setText(f"<b>{brand.NAME} Shield warning</b> — {reasons} "
                          f"<span style='color:{T['ink3']}'>({report.host})</span>")
        self.show()
        self.raise_()


def _kv(label, value, color=None):
    row = QHBoxLayout()
    a = QLabel(label)
    a.setObjectName("muted")
    b = QLabel(str(value))
    b.setStyleSheet(f"font-weight:600;{f'color:{color};' if color else ''}")
    b.setAlignment(Qt.AlignmentFlag.AlignRight)
    row.addWidget(a)
    row.addStretch(1)
    row.addWidget(b)
    return row


class SiteInfoDialog(QDialog):
    shield_toggled = Signal(bool)     # True = shield ON for this site
    reset_zoom = Signal()
    forget_permissions = Signal()

    def __init__(self, report: SiteReport, privacy_mode: str, vpn_state: str,
                 stats=None, parent=None, shield_on=True, zoom=100, perms=None):
        super().__init__(parent)
        self.setWindowTitle("Site information")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)

        col = verdict_color(report.verdict)
        title, sub = _VERDICT_TEXT.get(report.verdict, _VERDICT_TEXT[Verdict.UNKNOWN])
        head = QHBoxLayout()
        head.setSpacing(12)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("shield", 30, col))
        txt = QLabel(f"<b style='font-size:16px'>{report.host or 'Internal page'}</b><br>"
                     f"<span style='color:{col};font-weight:600'>{title}</span>"
                     f"<span style='color:{T['ink3']}'> · {sub}</span>")
        txt.setWordWrap(True)
        head.addWidget(ic)
        head.addWidget(txt, 1)
        lay.addLayout(head)

        if report.reasons:
            box = QFrame()
            box.setObjectName("cardField")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(12, 9, 12, 9)
            bl.setSpacing(3)
            for r in report.reasons:
                l = QLabel(f"•  {r}")
                l.setWordWrap(True)
                l.setStyleSheet(f"color:{T['ink2']};font-size:12px;")
                bl.addWidget(l)
            lay.addWidget(box)

        lay.addSpacing(4)
        lay.addWidget(caption("Connection"))
        lay.addLayout(_kv("Encryption", "HTTPS" if report.https else "None (http)",
                          T["success"] if report.https else T["warn"]))
        lay.addLayout(_kv("Shield mode", privacy_mode.title()))
        lay.addLayout(_kv("Tunnel / proxy", vpn_state))
        if zoom != 100:
            zr = _kv("Page zoom", f"{zoom}%")
            btn = QPushButton("Reset")
            btn.clicked.connect(lambda: (self.reset_zoom.emit(), btn.setEnabled(False)))
            zr.addWidget(btn)
            lay.addLayout(zr)

        if stats is not None:
            lay.addSpacing(4)
            lay.addWidget(caption("Blocked on this site"))
            lay.addLayout(_kv("Total", stats.get("blocked", 0)))
            lay.addLayout(_kv("Advertising", stats.get("ads", 0)))
            lay.addLayout(_kv("Analytics", stats.get("analytics", 0)))
            lay.addLayout(_kv("Cross-site tracking", stats.get("tracking", 0)))
            lay.addLayout(_kv("Third-party requests", stats.get("third", 0)))

        if report.host:
            lay.addSpacing(4)
            sw_row = QHBoxLayout()
            lab = QLabel("<b>Shield for this site</b><br>"
                         f"<span style='color:{T['ink3']};font-size:12px'>Turn off if the site is broken by blocking.</span>")
            sw = Switch(shield_on)
            sw.toggled.connect(self.shield_toggled)
            sw_row.addWidget(lab, 1)
            sw_row.addWidget(sw)
            lay.addLayout(sw_row)

        if perms:
            lay.addSpacing(4)
            lay.addWidget(caption("Permissions"))
            for ptype, granted in perms:
                lay.addLayout(_kv(ptype, "Allowed" if granted else "Blocked",
                                  T["success"] if granted else T["danger"]))
            fb = QPushButton("Reset permissions")
            fb.clicked.connect(lambda: (self.forget_permissions.emit(), fb.setEnabled(False)))
            lay.addWidget(fb, 0, Qt.AlignmentFlag.AlignLeft)

        lay.addSpacing(6)
        close = QPushButton("Done")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        lay.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
