"""Address-bar suggestions: provider, popup and the controller that wires
them to the omnibox."""
from urllib.parse import quote_plus

from PySide6.QtCore import (Qt, QObject, QTimer, Signal, QUrl, QRect, QPoint,
                            QSize)
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtNetwork import (QNetworkAccessManager, QNetworkRequest,
                               QNetworkReply)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFrame, QListWidget,
                               QListWidgetItem, QApplication)

from browser import omni
from ui import icons
from ui.quick_apps import FAVICON_CACHE
from ui.theme import TOKENS as T
from ui.widgets import RowDelegate, SUB_ROLE, META_ROLE, paint_shadow

ITEM_ROLE = Qt.ItemDataRole.UserRole + 40
ROW_H = 42
MAX_ROWS = 9


class SuggestItem:
    __slots__ = ("kind", "title", "sub", "url", "icon", "tab_id", "meta")

    def __init__(self, kind, title, sub="", url="", icon="globe", tab_id=None,
                 meta=""):
        self.kind, self.title, self.sub, self.url = kind, title, sub, url
        self.icon, self.tab_id, self.meta = icon, tab_id, meta

    def __repr__(self):
        return f"<{self.kind} {self.title!r} {self.url!r}>"


def _host(url):
    return QUrl(url).host()


def _bare(url):
    u = url.split("://", 1)[-1]
    if u.startswith("www."):
        u = u[4:]
    return u.rstrip("/")


def favicon_icon(host, fallback="globe"):
    if host:
        path = FAVICON_CACHE / f"fav_{host}.png"
        if path.exists():
            px = QPixmap(str(path))
            if not px.isNull():
                return QIcon(px)
    return icons.icon(fallback, 16, T["ink3"])


class SuggestionProvider(QObject):
    remote_ready = Signal(str, list)

    def __init__(self, storage, get_tabs, get_engine, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.get_tabs = get_tabs          # -> [(id, title, url, private)]
        self.get_engine = get_engine      # -> engine key
        self.remote_enabled = True
        self._nam = QNetworkAccessManager(self)
        self._reply = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(140)
        self._debounce.timeout.connect(self._fire_remote)
        self._pending = ""

    # ------------------------------------------------------------ local
    def local(self, text, private=False):
        text = text.strip()
        if not text:
            return []
        engine = self.get_engine()
        template = omni.engine_url(engine)
        res = omni.resolve(text, template)
        items, seen = [], set()

        def add(item):
            key = item.url.rstrip("/") if item.url else item.title
            if key in seen:
                return
            seen.add(key)
            items.append(item)

        if res is not None:
            if res.kind in ("url", "internal"):
                add(SuggestItem("go", f"Go to {_bare(res.url)}", "Open address",
                                res.url, "globe"))
            else:
                label = res.label if res.label != "Search" else omni.engine_label(engine)
                add(SuggestItem("search", f"Search {label} for “{text}”"
                                if res.label != "Search" else
                                f"{label} search “{text}”",
                                "Web search", res.url, "search"))
        result = omni.calc(text)
        if result is not None:
            items.insert(0, SuggestItem("calc", f"= {result}", text, "",
                                        "calc", meta="Enter to copy"))
        low = text.lower()
        n = 0
        for tid, title, url, _priv in self.get_tabs():
            if url.startswith("http") and (low in (title or "").lower()
                                            or low in url.lower()):
                add(SuggestItem("tab", title or _bare(url), _bare(url), url,
                                "tab", tab_id=tid, meta="Switch to tab"))
                n += 1
                if n >= 2:
                    break
        for row in self.storage.suggest(text, 5):
            add(SuggestItem("saved" if row["saved"] else "history",
                            row["title"], _bare(row["url"]), row["url"],
                            "star" if row["saved"] else "history"))
        for app in self.storage.list_apps():
            if low in (app["name"] or "").lower():
                add(SuggestItem("app", app["name"], _bare(app["url"]),
                                app["url"], "globe", meta="Quick app"))
                break
        return items

    # ------------------------------------------------------------ remote
    def request_remote(self, text):
        self._pending = text.strip()
        if self._reply is not None:
            self._reply.abort()
            self._reply = None
        if not self.remote_enabled or len(self._pending) < 2 \
                or " " not in self._pending and omni.looks_like_url(self._pending):
            return
        self._debounce.start()

    def cancel(self):
        self._debounce.stop()
        self._pending = ""
        if self._reply is not None:
            self._reply.abort()
            self._reply = None

    def _fire_remote(self):
        tmpl = omni.ENGINES.get(self.get_engine(), omni.ENGINES[omni.DEFAULT_ENGINE])[2]
        if not tmpl or not self._pending:
            return
        query = self._pending
        req = QNetworkRequest(QUrl(tmpl.format(quote_plus(query))))
        req.setTransferTimeout(2500)
        reply = self._nam.get(req)
        self._reply = reply
        reply.finished.connect(lambda r=reply, q=query: self._done(r, q))

    def _done(self, reply, query):
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError \
                    and query == self._pending:
                self.remote_ready.emit(query, omni.parse_suggestions(
                    bytes(reply.readAll()), 5))
        finally:
            if reply is self._reply:
                self._reply = None
            reply.deleteLater()


class SuggestPopup(QWidget):
    activated = Signal(object)

    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setObjectName("suggest")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 8, 14, 22)
        self.box = QFrame(self)
        self.box.setObjectName("suggestBox")
        inner = QVBoxLayout(self.box)
        inner.setContentsMargins(6, 6, 6, 6)
        self.list = QListWidget(self.box)
        self.list.setObjectName("panelList")
        self.list.setItemDelegate(RowDelegate(self.list, row_h=ROW_H, icon=18))
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setMouseTracking(True)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.itemPressed.connect(self._pressed)
        self.list.itemEntered.connect(lambda it: self.list.setCurrentItem(it))
        inner.addWidget(self.list)
        outer.addWidget(self.box)
        self._items = []

    def paintEvent(self, _e):
        p = QPainter(self)
        paint_shadow(p, self.box.geometry(), 14, 12, 60)
        p.end()

    # -------------------------------------------------------------- data
    def set_items(self, items, keep_row=0):
        self._items = items
        self.list.clear()
        for it in items[:MAX_ROWS]:
            li = QListWidgetItem(it.title)
            li.setData(SUB_ROLE, it.sub)
            li.setData(META_ROLE, it.meta or None)
            li.setData(ITEM_ROLE, it)
            if it.kind in ("history", "saved", "app", "tab", "go") and \
                    _host(it.url):
                li.setIcon(favicon_icon(_host(it.url), it.icon))
            else:
                li.setIcon(icons.icon(it.icon, 16,
                                      T["accent"] if it.kind in ("search", "calc")
                                      else T["ink3"]))
            self.list.addItem(li)
        n = self.list.count()
        self.list.setFixedHeight(max(1, n) * ROW_H + 4)
        if n:
            self.list.setCurrentRow(min(keep_row, n - 1))
        self.adjustSize()

    def step(self, delta):
        n = self.list.count()
        if not n:
            return
        row = self.list.currentRow()
        self.list.setCurrentRow((row + delta) % n if row >= 0 else 0)

    def current_item(self):
        it = self.list.currentItem()
        return it.data(ITEM_ROLE) if it else None

    def _pressed(self, li):
        item = li.data(ITEM_ROLE)
        if item is not None:
            self.activated.emit(item)

    def show_under(self, anchor: QWidget):
        width = anchor.width() + 28
        self.setFixedWidth(width)
        top_left = anchor.mapToGlobal(QPoint(0, anchor.height()))
        self.move(top_left.x() - 14, top_left.y() - 4)
        if not self.isVisible():
            self.show()
        self.raise_()


class SuggestController(QObject):
    """Glues Omnibox <-> provider <-> popup and reports what to do."""
    navigate = Signal(str, bool)        # url-or-text, new_tab
    switch_tab = Signal(int)
    copy_text = Signal(str)

    def __init__(self, omnibox, provider, is_private, top_hosts, parent=None):
        super().__init__(parent)
        self.omni = omnibox
        self.provider = provider
        self.is_private = is_private          # -> bool
        self.top_hosts = top_hosts            # -> [host, ...] for inline complete
        self.inline_enabled = True
        self.popup = SuggestPopup()
        self.popup.activated.connect(self._activate)
        provider.remote_ready.connect(self._remote)
        self._local = []
        self._text = ""
        omnibox.edit.textEdited.connect(self._typed)
        omnibox.edit.nav.connect(self._nav)
        omnibox.edit.accept.connect(self._accept)
        omnibox.edit.dismiss.connect(self.hide)
        omnibox.edit.focus_out.connect(self._focus_out)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(120)
        self._hide_timer.timeout.connect(self.hide)

    # -------------------------------------------------------------- flow
    def hide(self):
        self.provider.cancel()
        self.popup.hide()

    def _focus_out(self):
        self._hide_timer.start()

    def _typed(self, text):
        self._hide_timer.stop()
        self._text = text
        if not text.strip():
            self.hide()
            return
        self._inline(text)
        self._local = self.provider.local(text, self.is_private())
        self._render(self._local)
        if not self.is_private():
            self.provider.request_remote(text)

    def _inline(self, text):
        if not self.inline_enabled or self.omni.edit.last_was_delete \
                or " " in text or "/" in text or len(text) < 2:
            return
        low = text.lower()
        for host in self.top_hosts():
            bare = host[4:] if host.startswith("www.") else host
            if bare.startswith(low) and len(bare) > len(low):
                self.omni.edit.setText(text + bare[len(low):])
                self.omni.edit.setSelection(len(bare), -(len(bare) - len(text)))
                self._text = text
                return

    def _render(self, items, keep=0):
        if not items:
            self.popup.hide()
            return
        self.popup.set_items(items, keep)
        self.popup.show_under(self.omni)

    def _remote(self, query, phrases):
        if query.strip() != self._text.strip() or not self.omni.edit.hasFocus():
            return
        tmpl = omni.engine_url(self.provider.get_engine())
        have = {i.title.lower() for i in self._local}
        extra = []
        for phrase in phrases:
            if phrase.lower() == query.lower() or phrase.lower() in have:
                continue
            extra.append(SuggestItem("suggest", phrase, "", omni.search_url(
                phrase, tmpl), "search"))
        if extra:
            row = max(self.popup.list.currentRow(), 0)
            self._render(self._local + extra[:4], row)

    def _nav(self, delta):
        if not self.popup.isVisible():
            if delta > 0 and self.omni.edit.text().strip():
                self._local = self.provider.local(self.omni.edit.text(),
                                                  self.is_private())
                self._render(self._local)
            return
        self.popup.step(delta)

    def _accept(self, new_tab):
        text = self.omni.edit.text().strip()
        item = self.popup.current_item() if self.popup.isVisible() else None
        self.hide()
        if item is not None and self._selected_explicitly(item):
            self._activate(item, new_tab)
        else:
            self.navigate.emit(text, new_tab)

    def _selected_explicitly(self, item):
        # Row 0 is the default action for exactly what was typed – let the
        # omnibox text (possibly inline-completed) win in that case.
        return self.popup.list.currentRow() > 0

    def _activate(self, item, new_tab=False):
        self.hide()
        if item.kind == "tab" and item.tab_id is not None:
            self.switch_tab.emit(item.tab_id)
        elif item.kind == "calc":
            self.copy_text.emit(item.title.lstrip("= ").strip())
        else:
            self.navigate.emit(item.url or item.title, new_tab)
