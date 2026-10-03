from PySide6.QtCore import Qt, Signal, QUrl, QRectF, QSize
from PySide6.QtGui import QIcon, QPainter, QColor, QPen, QFont, QFontMetrics
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QLineEdit, QToolButton,
                               QLabel, QFrame, QSizePolicy)

from ui import icons, brand
from ui.theme import TOKENS as T
from ui.widgets import qcolor


class ProgressLine(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(2)
        self._value = 0
        self._active = False

    def set_active(self, on):
        self._active = on
        self.update()

    def set_value(self, value):
        self._value = value
        self.update()

    def paintEvent(self, _event):
        if not self._active:
            return
        p = QPainter(self)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T["accent"]))
        width = int(self.width() * max(6, min(100, self._value)) / 100)
        p.drawRect(0, 0, width, 2)
        p.end()


class BadgeButton(QToolButton):
    """Chrome button that can paint a count badge and/or a progress ring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._count = 0
        self._progress = None

    def set_count(self, n):
        if n != self._count:
            self._count = n
            self.update()

    def set_progress(self, value):
        self._progress = value
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._count and self._progress is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._progress is not None:
            pen = QPen(qcolor(T["accent"]), 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            r = QRectF(self.width() / 2 - 12, self.height() / 2 - 12, 24, 24)
            p.drawArc(r, 90 * 16, int(-360 * 16 * max(0.03, self._progress)))
        if self._count:
            text = str(self._count if self._count < 100 else "99+")
            f = QFont(self.font())
            f.setPixelSize(9)
            f.setBold(True)
            p.setFont(f)
            w = max(14, QFontMetrics(f).horizontalAdvance(text) + 8)
            rect = QRectF(self.width() - w - 1, 3, w, 14)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qcolor(T["accent"]))
            p.drawRoundedRect(rect, 7, 7)
            p.setPen(qcolor(T["accent_ink"]))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        p.end()


class OmniEdit(QLineEdit):
    focus_in = Signal()
    focus_out = Signal()
    nav = Signal(int)          # +1 / -1 selection move
    accept = Signal(bool)      # new_tab?
    dismiss = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_was_delete = False

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focus_in.emit()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focus_out.emit()

    def keyPressEvent(self, event):
        key = event.key()
        self.last_was_delete = key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete)
        mods = event.modifiers()
        if key == Qt.Key.Key_Down:
            self.nav.emit(1)
            return
        if key == Qt.Key.Key_Up:
            self.nav.emit(-1)
            return
        if key == Qt.Key.Key_Escape:
            self.dismiss.emit()
            super().keyPressEvent(event)
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept.emit(bool(mods & Qt.KeyboardModifier.AltModifier))
            return
        super().keyPressEvent(event)


class Omnibox(QFrame):
    star_clicked = Signal()
    site_clicked = Signal()
    reader_clicked = Signal()
    zoom_clicked = Signal()
    return_pressed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("omniBox")
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(2)
        self.site_btn = QToolButton(self)
        self.site_btn.setObjectName("tiny")
        self.site_btn.setFixedSize(26, 26)
        self.site_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.site_btn.setToolTip("Site information")
        self.site_btn.clicked.connect(lambda _c=False: self.site_clicked.emit())
        self.edit = OmniEdit(self)
        self.edit.setObjectName("omni")
        self.edit.setPlaceholderText("Search or enter address")
        self.edit.focus_in.connect(self._on_focus_in)
        self.edit.focus_out.connect(self._on_focus_out)
        self.clear_btn = QToolButton(self)
        self.clear_btn.setObjectName("tiny")
        self.clear_btn.setVisible(False)
        self.clear_btn.clicked.connect(lambda _c=False: self.edit.clear())
        self.edit.textChanged.connect(self._sync_clear)
        self.zoom_btn = QToolButton(self)
        self.zoom_btn.setObjectName("pill")
        self.zoom_btn.setVisible(False)
        self.zoom_btn.setToolTip("Reset zoom (Ctrl+0)")
        self.zoom_btn.clicked.connect(lambda _c=False: self.zoom_clicked.emit())
        self.reader_btn = QToolButton(self)
        self.reader_btn.setObjectName("tiny")
        self.reader_btn.setCheckable(True)
        self.reader_btn.setVisible(False)
        self.reader_btn.setToolTip("Reader mode (Ctrl+Alt+R)")
        self.reader_btn.clicked.connect(lambda _c=False: self.reader_clicked.emit())
        self.star_btn = QToolButton(self)
        self.star_btn.setObjectName("tiny")
        self.star_btn.setToolTip("Save this page (Ctrl+D)")
        self.star_btn.clicked.connect(lambda _c=False: self.star_clicked.emit())
        for w in (self.site_btn,):
            lay.addWidget(w)
        lay.addWidget(self.edit, 1)
        for w in (self.clear_btn, self.zoom_btn, self.reader_btn, self.star_btn):
            lay.addWidget(w)
        self._full = ""
        self._private = False
        self._verdict = "unknown"
        self._https = False
        self._internal = True
        self.retheme()

    # ---------------------------------------------------------------- state
    def retheme(self):
        self.clear_btn.setIcon(icons.icon("close", 12, T["ink2"]))
        self.reader_btn.setIcon(icons.icon("reader", 15, T["ink2"]))
        self.set_saved(getattr(self, "_saved", False))
        self._paint_site_icon()

    def set_private(self, private):
        self._private = private
        self.setProperty("private", "true" if private else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self._paint_site_icon()

    def set_security(self, verdict: str, https: bool, internal: bool):
        self._verdict, self._https, self._internal = verdict, https, internal
        self._paint_site_icon()

    def _paint_site_icon(self):
        if self._private and self._internal:
            ic = icons.icon("mask", 15, T["priv_accent"])
        elif self._internal:
            ic = icons.icon("globe", 15, T["ink3"])
        elif self._verdict == "danger":
            ic = icons.icon("warning", 15, T["danger"])
        elif self._verdict == "caution" or not self._https:
            ic = icons.icon("lock_open", 15, T["warn"])
        else:
            ic = icons.icon("lock", 15, T["ink2"])
        self.site_btn.setIcon(ic)

    def _sync_clear(self, text):
        self.clear_btn.setVisible(bool(text) and self.edit.hasFocus())

    def _on_focus_in(self):
        self.setProperty("focused", "true")
        self.style().unpolish(self)
        self.style().polish(self)
        self.edit.setText(self._full)
        self.edit.selectAll()
        self._sync_clear(self.edit.text())

    def _on_focus_out(self):
        self.setProperty("focused", "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.edit.setText(self._simplify(self._full))
        self.edit.setCursorPosition(0)
        self._sync_clear("")

    @staticmethod
    def _simplify(url):
        if url.startswith("studybrowse"):
            return ""
        qurl = QUrl(url)
        if qurl.scheme() in ("http", "https"):
            host = qurl.host()
            if host.startswith("www."):
                host = host[4:]
            out = host + (qurl.path() if qurl.path() != "/" else "")
            if qurl.query():
                out += "?" + qurl.query()
            return out
        return url

    def set_url(self, url):
        self._full = "" if url.startswith("studybrowse") else url
        if not self.edit.hasFocus():
            self.edit.setText(self._simplify(url))
            self.edit.setCursorPosition(0)

    def set_saved(self, saved):
        self._saved = saved
        name = "star_fill" if saved else "star"
        self.star_btn.setIcon(icons.icon(name, 15, T["accent"] if saved else T["ink2"]))

    def set_zoom(self, pct):
        self.zoom_btn.setVisible(pct != 100)
        self.zoom_btn.setText(f"{pct}%")

    def set_reader_available(self, available, active=False):
        self.reader_btn.setVisible(available)
        self.reader_btn.setChecked(active)
        self.reader_btn.setIcon(icons.icon("reader", 15,
                                           T["accent"] if active else T["ink2"]))

    def focus_edit(self):
        self.edit.setFocus()
        self.edit.selectAll()


class TopBar(QWidget):
    back_clicked = Signal()
    forward_clicked = Signal()
    reload_stop_clicked = Signal()
    home_clicked = Signal()
    shield_clicked = Signal()
    external_clicked = Signal()
    menu_clicked = Signal()
    downloads_clicked = Signal()
    library_clicked = Signal()
    focus_clicked = Signal()
    url_entered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(48)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(2)
        self.back = self._btn("back", "Back (Alt+Left)")
        self.fwd = self._btn("forward", "Forward (Alt+Right)")
        self.reload = self._btn("reload", "Reload (Ctrl+R)")
        self.home = self._btn("home", "Home")
        self.back.clicked.connect(lambda _c=False: self.back_clicked.emit())
        self.fwd.clicked.connect(lambda _c=False: self.forward_clicked.emit())
        self.reload.clicked.connect(lambda _c=False: self.reload_stop_clicked.emit())
        self.home.clicked.connect(lambda _c=False: self.home_clicked.emit())
        for btn in (self.back, self.fwd, self.reload, self.home):
            lay.addWidget(btn)
        lay.addSpacing(8)
        self.omni = Omnibox(self)
        lay.addWidget(self.omni, 1)
        lay.addSpacing(8)

        self.focus_pill = QToolButton(self)
        self.focus_pill.setObjectName("pill")
        self.focus_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.focus_pill.setToolTip("Focus session")
        self.focus_pill.setVisible(False)
        self.focus_pill.clicked.connect(lambda _c=False: self.focus_clicked.emit())
        lay.addWidget(self.focus_pill)

        self.shield = BadgeButton(self)
        self._style_btn(self.shield, "shield", f"{brand.NAME} Shield")
        self.shield.clicked.connect(lambda _c=False: self.shield_clicked.emit())
        self.downloads = BadgeButton(self)
        self._style_btn(self.downloads, "download", "Downloads (Ctrl+J)")
        self.downloads.clicked.connect(lambda _c=False: self.downloads_clicked.emit())
        self.library = self._btn("saved", "Library — saved, notes, history")
        self.library.clicked.connect(lambda _c=False: self.library_clicked.emit())
        self.menu = self._btn("dots", "Menu")
        self.menu.clicked.connect(lambda _c=False: self.menu_clicked.emit())
        for w in (self.shield, self.downloads, self.library, self.menu):
            lay.addWidget(w)
        self.external = self._btn("external", "Open in external browser")
        self.external.setVisible(False)
        self.external.clicked.connect(lambda _c=False: self.external_clicked.emit())
        self.progress = ProgressLine(self)
        self.omni.return_pressed.connect(self.url_entered)
        self._shield_color = None

    def _style_btn(self, btn, name, tip):
        btn.setObjectName("chrome")
        btn.setIcon(icons.icon(name, 17, T["ink2"]))
        btn.setToolTip(tip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def _btn(self, name, tip):
        btn = QToolButton(self)
        self._style_btn(btn, name, tip)
        return btn

    def retheme(self):
        self.omni.retheme()
        self.reload.setIcon(icons.icon("reload", 17, T["ink2"]))
        self.home.setIcon(icons.icon("home", 17, T["ink2"]))
        self.library.setIcon(icons.icon("saved", 17, T["ink2"]))
        self.menu.setIcon(icons.icon("dots", 17, T["ink2"]))
        self.downloads.setIcon(icons.icon("download", 17, T["ink2"]))
        self.set_shield(self._shield_color or T["ink2"])
        self.set_nav_state(self.back.isEnabled(), self.fwd.isEnabled())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.progress.setGeometry(0, self.height() - 2, self.width(), 2)

    def set_nav_state(self, can_back, can_forward):
        self.back.setEnabled(can_back)
        self.fwd.setEnabled(can_forward)
        self.back.setIcon(icons.icon("back", 17, T["ink2"] if can_back else T["ink3"]))
        self.fwd.setIcon(icons.icon("forward", 17, T["ink2"] if can_forward else T["ink3"]))

    def set_shield(self, color, blocked=0):
        self._shield_color = color
        self.shield.setIcon(icons.icon("shield", 17, color))
        self.shield.set_count(blocked)

    def set_loading(self, loading):
        self.reload.setIcon(icons.icon("stop" if loading else "reload", 17, T["ink2"]))
        self.reload.setToolTip("Stop loading" if loading else "Reload (Ctrl+R)")
        self.progress.set_active(loading)
        if not loading:
            self.progress.set_value(0)

    def set_focus_pill(self, text, state):
        self.focus_pill.setVisible(bool(text))
        if text:
            icon = {"focus": "focus", "break": "sun", "paused": "pause"}.get(state, "focus")
            self.focus_pill.setIcon(icons.icon(icon, 14, T["accent"]))
            self.focus_pill.setText(text)
            self.focus_pill.setChecked(state == "focus")
            self.focus_pill.setCheckable(True)

    def set_download_activity(self, active, progress):
        self.downloads.set_count(active)
        self.downloads.set_progress(progress if active else None)
