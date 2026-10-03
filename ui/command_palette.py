from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QListWidget, QListWidgetItem, QFrame, QLabel)

from browser import omni
from ui import icons
from ui.theme import TOKENS as T
from ui.widgets import RowDelegate, SUB_ROLE, META_ROLE, paint_shadow


class PaletteItem:
    __slots__ = ("icon", "label", "hint", "action", "keys", "kind")

    def __init__(self, icon_name, label, hint, action, keys="", kind=""):
        self.icon = icon_name
        self.label = label
        self.hint = hint
        self.action = action
        self.keys = keys
        self.kind = kind


def fuzzy(query: str, text: str) -> int:
    """Score >0 if every query char appears in order; higher is better."""
    if not query:
        return 1
    q, t = query.lower(), text.lower()
    if q == t:
        return 1000
    if t.startswith(q):
        return 800 - len(t)
    idx = t.find(q)
    if idx >= 0:
        return 600 - idx * 4 - len(t) // 4
    # word-initial / subsequence match
    pos, score, prev = 0, 0, -2
    for ch in q:
        pos = t.find(ch, pos)
        if pos < 0:
            return 0
        score += 10 + (8 if pos == 0 or t[pos - 1] in " -_/." else 0) \
            + (6 if pos == prev + 1 else 0)
        prev = pos
        pos += 1
    return score


class PaletteDialog(QDialog):
    ROW_H = 46

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("palette")
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.provider = None
        self._items = []
        self.box = QFrame(self)
        self.box.setObjectName("paletteBox")
        lay = QVBoxLayout(self.box)
        lay.setContentsMargins(10, 10, 10, 8)
        lay.setSpacing(6)
        head = QHBoxLayout()
        head.setContentsMargins(6, 0, 6, 0)
        head.setSpacing(8)
        glyph = QLabel(self.box)
        glyph.setPixmap(icons.pixmap("command", 17, T["ink3"]))
        self.edit = QLineEdit(self.box)
        self.edit.setObjectName("paletteInput")
        self.edit.setPlaceholderText("Search commands, tabs, saved pages, notes…")
        self.edit.textChanged.connect(lambda _t: self._refilter())
        self.edit.returnPressed.connect(self._run_current)
        head.addWidget(glyph)
        head.addWidget(self.edit, 1)
        lay.addLayout(head)
        line = QFrame(self.box)
        line.setObjectName("hairline")
        lay.addWidget(line)
        self.list = QListWidget(self.box)
        self.list.setObjectName("paletteList")
        self.list.setItemDelegate(RowDelegate(self.list, row_h=self.ROW_H, icon=18))
        self.list.setMouseTracking(True)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.setFixedHeight(self.ROW_H * 7)
        self.list.itemClicked.connect(lambda _i: self._run_current())
        lay.addWidget(self.list)
        foot = QLabel("↑↓ navigate   ↵ run   esc close", self.box)
        foot.setObjectName("faint")
        foot.setContentsMargins(8, 0, 0, 0)
        lay.addWidget(foot)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 18, 26, 34)
        outer.addWidget(self.box)
        self.setFixedWidth(640)

    def paintEvent(self, _e):
        p = QPainter(self)
        paint_shadow(p, self.box.geometry(), 14, 18, 70)
        p.end()

    def open_palette(self, prefix=""):
        self.edit.setText(prefix)
        self._refilter()
        self.adjustSize()
        par = self.parent()
        if par is not None:
            c = par.mapToGlobal(QPoint(par.width() // 2, 0))
            self.move(c.x() - self.width() // 2, c.y() + 70)
        self.show()
        self.raise_()
        self.edit.setFocus()

    def _refilter(self):
        query = self.edit.text().strip()
        source = list(self.provider() if self.provider else [])
        scored = []
        for idx, it in enumerate(source):
            if not query:
                scored.append((1000 - idx, it))
                continue
            s = max(fuzzy(query, it.label), fuzzy(query, it.hint) // 2)
            if s > 0:
                scored.append((s, it))
        scored.sort(key=lambda t: -t[0])
        self._items = [it for _s, it in scored[:60]]
        # always offer the query as an address / search / calculation
        if query:
            res = omni.resolve(query, omni.engine_url(self.engine_key()))
            calc = omni.calc(query)
            extra = []
            if calc is not None:
                extra.append(PaletteItem("calc", f"= {calc}", "Copy result",
                                         lambda c=calc: self.copy_cb(c), kind="calc"))
            if res is not None:
                if res.kind == "search":
                    extra.append(PaletteItem("search", f"Search the web for “{query}”",
                                             res.label if res.label != "Search" else "Web search",
                                             lambda u=res.url: self.go_cb(u), kind="web"))
                else:
                    extra.append(PaletteItem("globe", f"Go to {query}", "Open address",
                                             lambda u=res.url: self.go_cb(u), kind="web"))
            self._items = extra[:1] + self._items + extra[1:] if calc else self._items + extra
        self.list.clear()
        for it in self._items:
            entry = QListWidgetItem(it.label)
            entry.setData(SUB_ROLE, it.hint)
            entry.setData(META_ROLE, it.keys or None)
            entry.setIcon(icons.icon(it.icon, 17, T["accent"] if it.kind in ("calc", "web")
                                     else T["ink2"]))
            self.list.addItem(entry)
        if self.list.count():
            self.list.setCurrentRow(0)

    # injected by the main window
    def engine_key(self):
        return "duckduckgo"

    def go_cb(self, url):
        pass

    def copy_cb(self, text):
        pass

    def _run_current(self):
        row = self.list.currentRow()
        if 0 <= row < len(self._items):
            action = self._items[row].action
            self.hide()
            action()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.hide()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            n = self.list.count()
            if n:
                cur = self.list.currentRow()
                self.list.setCurrentRow((cur + (1 if key == Qt.Key.Key_Down else -1)) % n)
        elif key in (Qt.Key.Key_PageDown, Qt.Key.Key_PageUp):
            n = self.list.count()
            if n:
                step = 6 if key == Qt.Key.Key_PageDown else -6
                self.list.setCurrentRow(max(0, min(n - 1, self.list.currentRow() + step)))
        else:
            super().keyPressEvent(event)
