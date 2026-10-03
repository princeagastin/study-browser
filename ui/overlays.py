"""Small overlay widgets that float above the web view."""
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QFontMetrics
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QToolButton,
                               QLineEdit, QWidget, QVBoxLayout, QScrollArea,
                               QSizePolicy)

from ui import icons
from ui.theme import TOKENS as T


class FindBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("findBar")
        self._page = None
        self._case = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)
        self.edit = QLineEdit(self)
        self.edit.setObjectName("findInput")
        self.edit.setFixedWidth(210)
        self.edit.setPlaceholderText("Find in page")
        self.count = QLabel("", self)
        self.count.setMinimumWidth(58)
        self.count.setObjectName("faint")
        self.case_btn = QToolButton(self)
        self.case_btn.setObjectName("tiny")
        self.case_btn.setCheckable(True)
        self.case_btn.setText("Aa")
        self.case_btn.setToolTip("Match case")
        self.prev = QToolButton(self)
        self.prev.setObjectName("tiny")
        self.next = QToolButton(self)
        self.next.setObjectName("tiny")
        self.close_btn = QToolButton(self)
        self.close_btn.setObjectName("tiny")
        for w in (self.edit, self.count, self.case_btn, self.prev, self.next, self.close_btn):
            lay.addWidget(w)
        self.edit.textChanged.connect(lambda _t: self._find(False))
        self.edit.returnPressed.connect(self._enter)
        self.case_btn.toggled.connect(self._set_case)
        self.prev.clicked.connect(lambda _c=False: self._find(True))
        self.next.clicked.connect(lambda _c=False: self._find(False))
        self.close_btn.clicked.connect(lambda _c=False: self.close_bar())
        self.retheme()

    def retheme(self):
        self.prev.setIcon(icons.icon("up", 13, T["ink2"]))
        self.next.setIcon(icons.icon("chevron_down", 13, T["ink2"]))
        self.close_btn.setIcon(icons.icon("close", 12, T["ink2"]))

    def _enter(self):
        from PySide6.QtWidgets import QApplication
        back = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)
        self._find(back)

    def _set_case(self, on):
        self._case = on
        self._find(False)

    def set_page(self, page):
        if page is not self._page:
            self.clear_highlights()
        self._page = page

    def clear_highlights(self):
        if self._page is not None:
            try:
                self._page.findText("")
            except RuntimeError:
                pass

    def close_bar(self):
        self.clear_highlights()
        self.hide()

    def _find(self, backward):
        if self._page is None:
            return
        flags = QWebEnginePage.FindFlag(0)
        if backward:
            flags |= QWebEnginePage.FindFlag.FindBackward
        if self._case:
            flags |= QWebEnginePage.FindFlag.FindCaseSensitively
        text = self.edit.text()
        if not text:
            self.count.setText("")
            self.clear_highlights()
            return
        try:
            self._page.findText(text, flags, self._result)
        except TypeError:
            self._page.findText(text, flags)

    def _result(self, res):
        try:
            total, active = res.numberOfMatches(), res.activeMatch()
        except AttributeError:
            total = active = 1 if res else 0
        if not self.edit.text():
            self.count.setText("")
        elif total == 0:
            self.count.setText("No matches")
        else:
            self.count.setText(f"{active} of {total}")


class DuplicateBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dupBar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 10, 8)
        lay.setSpacing(8)
        self.text = QLabel("", self)
        self.switch_btn = QToolButton(self)
        self.switch_btn.setObjectName("link")
        self.switch_btn.setText("Switch to tab")
        self.anyway_btn = QToolButton(self)
        self.anyway_btn.setObjectName("link")
        self.anyway_btn.setText("Keep both")
        self.close_btn = QToolButton(self)
        self.close_btn.setObjectName("tiny")
        self.close_btn.clicked.connect(lambda _c=False: self.hide())
        for w in (self.switch_btn, self.anyway_btn, self.close_btn):
            w.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.text, 1)
        lay.addWidget(self.switch_btn)
        lay.addWidget(self.anyway_btn)
        lay.addWidget(self.close_btn)
        self.retheme()
        self.hide()

    def retheme(self):
        self.close_btn.setIcon(icons.icon("close", 12, T["ink2"]))


class StatusBubble(QLabel):
    """Chrome-style link preview, bottom-left of the page."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("statusBubble")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def show_text(self, text):
        if not text:
            self.hide()
            return
        maxw = max(200, int(self.parentWidget().width() * 0.6))
        fm = QFontMetrics(self.font())
        self.setText(fm.elidedText(text, Qt.TextElideMode.ElideMiddle, maxw - 24))
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()

    def reposition(self):
        p = self.parentWidget()
        if p is not None:
            self.move(0, p.height() - self.height())


class BookmarksBar(QWidget):
    open_url = Signal(str, bool)

    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.setObjectName("bookmarksBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.storage = storage
        self.setFixedHeight(34)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 0, 10, 0)
        outer.setSpacing(2)
        self.lay = QHBoxLayout()
        self.lay.setSpacing(2)
        outer.addLayout(self.lay)
        outer.addStretch(1)
        self.refresh()

    def refresh(self):
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rows = self.storage.list_saved()[:14]
        if not rows:
            hint = QLabel("Press Ctrl+D on a page to add it here", self)
            hint.setObjectName("faint")
            self.lay.addWidget(hint)
            return
        from ui.panels import _site_icon, _host
        for row in rows:
            title = (row["title"] or _host(row["url"]))
            b = QToolButton(self)
            b.setObjectName("pill")
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            b.setText(title if len(title) <= 22 else title[:21] + "…")
            b.setToolTip(row["url"])
            ic = _site_icon(_host(row["url"]))
            b.setIcon(ic if not ic.isNull() else icons.icon("globe", 13, T["ink3"]))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            url = row["url"]
            b.clicked.connect(lambda _c=False, u=url: self.open_url.emit(u, False))
            self.lay.addWidget(b)


class DevToolsDock(QFrame):
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("devDock")
        self.setMinimumHeight(180)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QWidget(self)
        head.setObjectName("topBar")
        head.setFixedHeight(30)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(12, 0, 6, 0)
        hl.addWidget(QLabel("Developer tools", head))
        hl.addStretch(1)
        x = QToolButton(head)
        x.setObjectName("tiny")
        x.setIcon(icons.icon("close", 12, T["ink2"]))
        x.clicked.connect(lambda _c=False: self.closed.emit())
        hl.addWidget(x)
        lay.addWidget(head)
        self.view = QWebEngineView(self)
        lay.addWidget(self.view, 1)
        self.setFixedHeight(320)

    def inspect(self, page):
        try:
            self.view.page().setInspectedPage(page)
        except Exception:
            pass

    def detach(self):
        try:
            self.view.page().setInspectedPage(None)
        except Exception:
            pass
