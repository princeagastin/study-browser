from PySide6.QtCore import (Qt, Signal, QObject, QUrl, QTimer, QMimeData,
                            QPoint, Property, QPropertyAnimation,
                            QEasingCurve)
from PySide6.QtGui import (QPainter, QColor, QPixmap, QPen, QFont, QDrag)
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QToolButton,
                               QScrollArea, QSizePolicy)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage

from browser.engine import StudyPage, HOME_URL
from ui import icons
from ui.permissions import ask_permission
import time
from ui.theme import TOKENS as T
from ui.widgets import qcolor, RoundMenu

SEL_JS = "(function(){return window.getSelection().toString();})();"


class FolioView(QWebEngineView):
    note_from_selection = Signal(str)
    search_selection = Signal(str)
    open_link = Signal(str, bool, bool)      # url, background, private
    save_link_as_source = Signal(str, str)   # url, text

    def contextMenuEvent(self, event):
        page = self.page()
        if page is None:
            return
        try:
            data = self.lastContextMenuRequest()
        except Exception:
            data = None
        link = data.linkUrl().toString() if data is not None and data.linkUrl().isValid() else ""
        link_text = data.linkText() if data is not None and link else ""
        media_url = data.mediaUrl().toString() if data is not None and data.mediaUrl().isValid() else ""
        MT = getattr(data, "mediaType", lambda: None)() if data is not None else None
        is_image = bool(media_url) and "Image" in str(MT)
        editable = bool(data is not None and data.isContentEditable())
        sel = (data.selectedText() if data is not None else "") or ""
        has_sel = bool(sel.strip()) or page.hasSelection()

        menu = RoundMenu(self)
        chosen = {}

        def act(key, icon, text, enabled=True, shortcut=""):
            a = menu.add(icon, text, None, shortcut, enabled)
            chosen[a] = key
            return a

        if link:
            act("link_tab", "tab", "Open Link in New Tab")
            act("link_bg", "plus", "Open Link in Background Tab")
            act("link_priv", "mask", "Open Link in Private Tab")
            act("link_copy", "copy", "Copy Link Address")
            act("link_save", "star", "Save Link as Source")
            menu.addSeparator()
        if is_image:
            act("img_tab", "globe", "Open Image in New Tab")
            act("img_copy", "copy", "Copy Image")
            act("img_url", "link", "Copy Image Address")
            act("img_save", "download", "Save Image As…")
            menu.addSeparator()
        if has_sel:
            act("note", "note_add", "New Note from Selection")
            act("search", "search", "Search Selection in New Tab")
            act("copy", "copy", "Copy", shortcut="Ctrl+C")
            menu.addSeparator()
        if editable:
            act("cut", "trash", "Cut", shortcut="Ctrl+X")
            act("paste", "copy", "Paste", shortcut="Ctrl+V")
        act("selall", "grid", "Select All", shortcut="Ctrl+A")
        menu.addSeparator()
        h = page.history()
        act("back", "back", "Back", h.canGoBack(), "Alt+←")
        act("fwd", "forward", "Forward", h.canGoForward(), "Alt+→")
        act("reload", "reload", "Reload", True, "Ctrl+R")
        menu.addSeparator()
        act("source", "code", "View Page Source", shortcut="Ctrl+U")
        act("inspect", "devtools", "Inspect", shortcut="F12")

        picked = menu.exec(event.globalPos())
        key = chosen.get(picked)
        if key is None:
            return
        A = QWebEnginePage.WebAction
        from PySide6.QtGui import QGuiApplication
        if key == "link_tab":
            self.open_link.emit(link, False, False)
        elif key == "link_bg":
            self.open_link.emit(link, True, False)
        elif key == "link_priv":
            self.open_link.emit(link, False, True)
        elif key == "link_copy":
            QGuiApplication.clipboard().setText(link)
        elif key == "link_save":
            self.save_link_as_source.emit(link, link_text)
        elif key == "img_tab":
            self.open_link.emit(media_url, False, False)
        elif key == "img_copy":
            page.triggerPageAction(A.CopyImageToClipboard)
        elif key == "img_url":
            QGuiApplication.clipboard().setText(media_url)
        elif key == "img_save":
            page.triggerPageAction(A.DownloadImageToDisk)
        elif key == "note":
            text = sel if sel.strip() else ""
            if text:
                self.note_from_selection.emit(text)
            else:
                page.runJavaScript(SEL_JS, lambda t: self.note_from_selection.emit(t or ""))
        elif key == "search":
            if sel.strip():
                self.search_selection.emit(sel)
            else:
                page.runJavaScript(SEL_JS, lambda t: self.search_selection.emit(t or ""))
        elif key == "copy":
            page.triggerPageAction(A.Copy)
        elif key == "cut":
            page.triggerPageAction(A.Cut)
        elif key == "paste":
            page.triggerPageAction(A.Paste)
        elif key == "selall":
            page.triggerPageAction(A.SelectAll)
        elif key == "back":
            page.triggerPageAction(A.Back)
        elif key == "fwd":
            page.triggerPageAction(A.Forward)
        elif key == "reload":
            self.reload()
        elif key == "source":
            self.open_link.emit("view-source:" + page.url().toString(), False, False)
        elif key == "inspect":
            self.window().toggle_devtools() if hasattr(self.window(), "toggle_devtools") else None


class Tab:
    __slots__ = ("id", "view", "page", "chip", "private", "loading",
                 "url", "title", "pinned", "group", "audible", "sleeping",
                 "last_active", "reader_src", "can_read", "error")

    def __init__(self, tid, view, page, chip, private):
        self.id = tid
        self.view = view
        self.page = page
        self.chip = chip
        self.private = private
        self.loading = False
        self.url = ""
        self.title = ""
        self.pinned = False
        self.group = None
        self.audible = False
        self.sleeping = False
        self.last_active = time.time()
        self.reader_src = None      # original URL while Reader mode is shown
        self.can_read = False
        self.error = ""


class TabChip(QWidget):
    clicked = Signal(int)
    middle_clicked = Signal(int)
    close_clicked = Signal(int)
    audio_toggled = Signal(int)
    ctx_menu = Signal(int, object)

    def __init__(self, tab_id, parent=None):
        super().__init__(parent)
        self.tab_id = tab_id
        self._active = False
        self._private = False
        self._hover = False
        self._press_pos = None
        self._pop = 1.0
        self.pinned = False
        self.sleeping = False
        self.group_color = None
        self.setFixedHeight(32)
        self.setMinimumWidth(120)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 0, 6, 0)
        lay.setSpacing(5)
        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(16, 16)
        self.audio_btn = QToolButton(self)
        self.audio_btn.setObjectName("tiny")
        self.audio_btn.setFixedSize(16, 16)
        self.audio_btn.setIcon(icons.icon("volume", 12, T["ink2"]))
        self.audio_btn.setToolTip("Mute site")
        self.audio_btn.setVisible(False)
        self.audio_btn.clicked.connect(
            lambda _c=False, tid=tab_id: self.audio_toggled.emit(tid))
        self.title_label = QLabel("New Tab", self)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Ignored,
                                       QSizePolicy.Policy.Preferred)
        self.close_btn = QToolButton(self)
        self.close_btn.setObjectName("tiny")
        self.close_btn.setIcon(icons.icon("close", 12, T["ink2"]))
        self.close_btn.setVisible(False)
        self.close_btn.clicked.connect(
            lambda _checked=False, tid=tab_id: self.close_clicked.emit(tid))
        lay.addWidget(self.icon_label)
        lay.addWidget(self.audio_btn)
        lay.addWidget(self.title_label, 1)
        lay.addWidget(self.close_btn)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda p, tid=tab_id: self.ctx_menu.emit(
                tid, self.mapToGlobal(p)))

    def _get_pop(self):
        return self._pop

    def _set_pop(self, value):
        self._pop = value
        self.update()

    pop = Property(float, _get_pop, _set_pop)

    def play_pop(self):
        anim = QPropertyAnimation(self, b"pop", self)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()

    def set_state(self, active=False, private=False):
        became_active = active and not self._active
        self._active = active
        self._private = private
        if became_active:
            self.play_pop()
        self.refresh()

    def set_pinned(self, pinned):
        self.pinned = pinned
        self.title_label.setVisible(not pinned)
        if pinned:
            self.close_btn.setVisible(False)
        self.refresh()

    def set_sleeping(self, on):
        self.sleeping = on
        self.refresh()

    def set_group(self, color):
        self.group_color = color
        self.update()

    def set_audio(self, playing, muted=False):
        self.audio_playing, self.audio_muted = playing, muted
        self.audio_btn.setVisible(playing or muted)
        self.audio_btn.setIcon(icons.icon(
            "volume_off" if muted else "volume", 13,
            T["ink3"] if muted else T["accent"]))

    def set_title(self, title):
        title = title or "New Tab"
        self.title_label.setText(title)
        self.title_label.setToolTip(title)
        self.refresh()

    def set_icon_pixmap(self, px):
        if px is None or (isinstance(px, QPixmap) and px.isNull()):
            self.icon_label.setPixmap(icons.pixmap("globe", 14, T["ink3"]))
            return
        px = px.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        if self.sleeping:
            dim = QPixmap(px.size())
            dim.fill(Qt.GlobalColor.transparent)
            q = QPainter(dim)
            q.setOpacity(0.45)
            q.drawPixmap(0, 0, px)
            q.end()
            px = dim
        self.icon_label.setPixmap(px)

    def refresh(self):
        font = QFont("Segoe UI", 9)
        font.setWeight(QFont.Weight.DemiBold if self._active
                       else QFont.Weight.Normal)
        self.title_label.setFont(font)
        if self._private:
            col = T["priv_text"] if self._active else "#B9C0D4"
        else:
            col = T["ink1"] if self._active else T["ink2"]
        if self.sleeping:
            col = T["ink3"]
        self.title_label.setStyleSheet(
            f"color:{col};background:transparent;")
        if not self.pinned:
            self.close_btn.setVisible(self._active or self._hover)
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.refresh()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.refresh()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.middle_clicked.emit(self.tab_id)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and \
                self._press_pos is not None:
            self._press_pos = None
            self.clicked.emit(self.tab_id)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_pos is not None and not self.pinned and (
                event.position().toPoint() - self._press_pos
        ).manhattanLength() > 12:
            self._press_pos = None
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData("sb/tab", str(self.tab_id).encode())
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)
            return
        super().mouseMoveEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 3, 0, 3)
        if self._private:
            p.setBrush(qcolor(T["priv_bg"]))
            p.setPen(QPen(QColor("#3A4157"), 1))
        elif self.pinned:
            p.setBrush(qcolor(T["accent_tint"]))
            p.setPen(Qt.PenStyle.NoPen)
        elif self._active:
            p.setBrush(qcolor(T["surface"]))
            p.setPen(QPen(qcolor(T["hairline"]), 1))
        else:
            base = qcolor(T["surface"])
            base.setAlpha(200 if self._hover else 120)
            p.setBrush(base)
            p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 9, 9)
        if self.sleeping and not self._active:
            pen = QPen(qcolor(T["hairline"]), 1, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 9, 9)
        if self.group_color:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(self.group_color))
            p.drawEllipse(rect.x() + 3, rect.center().y() - 3, 6, 6)
        if self._active:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qcolor(T["priv_accent"] if self._private
                              else T["accent"]))
            bar_w = max(6, int((rect.width() - 16) *
                               (0.35 + 0.65 * self._pop)))
            cx = rect.center().x()
            p.drawRoundedRect(cx - bar_w // 2, rect.y(), bar_w, 2, 1, 1)
        p.end()


class TabStrip(QWidget):
    chip_clicked = Signal(int)
    chip_close = Signal(int)
    chip_middle = Signal(int)
    new_tab = Signal(bool)
    order_changed = Signal(list)
    chip_ctx = Signal(int, object)
    chip_audio = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tabShelf")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(40)
        self.setAcceptDrops(True)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("stripScroll")
        self.scroll.setWidgetResizable(False)
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.inner = QWidget()
        self.lay = QHBoxLayout(self.inner)
        self.lay.setContentsMargins(8, 0, 8, 0)
        self.lay.setSpacing(4)
        self.lay.addStretch(1)
        self.plus = QToolButton(self.inner)
        self.plus.setObjectName("tiny")
        self.plus.setIcon(icons.icon("plus", 14, T["ink2"]))
        self.plus.setToolTip("New tab (Ctrl+T)")
        self.plus.setFixedSize(28, 28)
        self.plus.clicked.connect(
            lambda _checked=False: self.new_tab.emit(False))
        self.lay.addWidget(self.plus)
        self.scroll.setWidget(self.inner)
        outer.addWidget(self.scroll)
        self.chips = []

    def add_chip(self, tab_id):
        chip = TabChip(tab_id, self.inner)
        chip.clicked.connect(self.chip_clicked)
        chip.middle_clicked.connect(self.chip_middle)
        chip.close_clicked.connect(self.chip_close)
        chip.ctx_menu.connect(self.chip_ctx)
        chip.audio_toggled.connect(self.chip_audio)
        self.chips.append(chip)
        self.lay.insertWidget(self.lay.count() - 2, chip)
        self._relayout()
        return chip

    def remove_chip(self, tab_id):
        for chip in list(self.chips):
            if chip.tab_id == tab_id:
                self.chips.remove(chip)
                self.lay.removeWidget(chip)
                chip.deleteLater()
        self._relayout()

    def chip(self, tab_id):
        for chip in self.chips:
            if chip.tab_id == tab_id:
                return chip
        return None

    def clear(self):
        for chip in list(self.chips):
            self.chips.remove(chip)
            chip.deleteLater()
        self._relayout()

    def reorder_chips(self, ids):
        ordered = [self.chip(i) for i in ids if self.chip(i) is not None]
        for chip in list(self.chips):
            self.lay.removeWidget(chip)
        self.chips = ordered
        for i, chip in enumerate(ordered):
            self.lay.insertWidget(i, chip)
        self._relayout()

    def retheme(self):
        self.plus.setIcon(icons.icon("plus", 14, T["ink2"]))
        for chip in self.chips:
            chip.close_btn.setIcon(icons.icon("close", 12, T["ink2"]))
            chip.audio_btn.setIcon(icons.icon("volume", 12, T["ink2"]))
            chip.refresh()

    def wheelEvent(self, event):
        bar = self.scroll.horizontalScrollBar()
        delta = event.angleDelta().y() or event.angleDelta().x()
        bar.setValue(bar.value() - delta)
        event.accept()

    def ensure_visible(self, tab_id):
        chip = self.chip(tab_id)
        if chip is not None:
            self.scroll.ensureWidgetVisible(chip, 40, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self):
        pinned = [c for c in self.chips if c.pinned]
        free = [c for c in self.chips if not c.pinned]
        for chip in pinned:
            chip.setFixedWidth(46)
        n = len(free)
        avail = (self.scroll.viewport().width() - 44
                 - 4 * max(len(self.chips), 1) - 16 - 46 * len(pinned))
        width = 230 if n == 0 else max(120, min(230, avail // n))
        for chip in free:
            chip.setFixedWidth(width)
        total = sum(c.width() for c in self.chips) + \
            4 * len(self.chips) + 44 + 16
        self.inner.setFixedWidth(max(total, self.scroll.viewport().width()))
        self.inner.setFixedHeight(40)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("sb/tab"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        tid = int(bytes(event.mimeData().data("sb/tab")).decode())
        chip = self.chip(tid)
        if not chip or chip.pinned:
            return
        x = event.position().x() + self.scroll.horizontalScrollBar().value()
        index = 0
        for i, other in enumerate(self.chips):
            mid = other.mapTo(self.inner, QPoint(0, 0)).x() + other.width() / 2
            if x > mid:
                index = i + 1
        self.lay.removeWidget(chip)
        self.chips.remove(chip)
        index = min(index, len(self.chips))
        self.chips.insert(index, chip)
        self.lay.insertWidget(index, chip)
        self._relayout()
        self.order_changed.emit([c.tab_id for c in self.chips])
        event.acceptProposedAction()


ERROR_TITLE = "Can’t reach this page"


class TabManager(QObject):
    current_changed = Signal()
    url_changed = Signal(str)
    title_changed = Signal(str)
    loading_changed = Signal(bool)
    progress_changed = Signal(int)
    icon_changed = Signal(object)
    count_changed = Signal(int)
    note_from_selection = Signal(str)
    search_selection = Signal(str)
    duplicate_detected = Signal(int, int, str)
    link_hovered = Signal(str)
    fullscreen_requested = Signal(object)
    cert_error = Signal(object)
    auth_needed = Signal(object, object, object)   # tab, url, authenticator
    open_link = Signal(str, bool, bool)
    save_link = Signal(str, str)
    page_loaded = Signal(object)                   # tab

    GROUP_COLORS = ["#E5484D", "#30A46C", "#3E63DD", "#F5D90A",
                    "#8E4EC6", "#F76B15"]

    def __init__(self, stacked, strip, profiles, storage, session, on_action):
        super().__init__()
        self.stacked = stacked
        self.strip = strip
        self.profiles = profiles
        self.storage = storage
        self.session = session
        self.on_action = on_action
        self.tabs = []
        self.groups = {}
        self._next_id = 1
        self._next_gid = 1
        self._closing = False
        self._dup_shown = set()
        self.zoom_for = lambda url: 100
        self.dark_get = lambda: False
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(110)
        self._spin_idx = 0
        self.sleep_after_min = 0
        self._sleep_timer = QTimer(self)
        self._sleep_timer.setInterval(30000)
        self._sleep_timer.timeout.connect(self.sleep_idle)
        self._sleep_timer.start()
        self._spin_timer.timeout.connect(self._tick_spin)
        strip.chip_clicked.connect(self.activate)
        strip.chip_close.connect(self.close_tab)
        strip.chip_middle.connect(self.close_tab)
        strip.new_tab.connect(lambda private: self.new_tab(private=private))
        strip.order_changed.connect(self.reorder)

    # ---------------------------------------------------------- groups
    def create_group(self, name):
        gid = self._next_gid
        self._next_gid += 1
        color = self.GROUP_COLORS[(gid - 1) % len(self.GROUP_COLORS)]
        group = {"id": gid, "name": name or f"Group {gid}", "color": color}
        self.groups[gid] = group
        return group

    def set_tab_group(self, tab_id, group):
        tab = self.by_id(tab_id)
        if not tab:
            return
        tab.group = group
        tab.chip.set_group(group["color"] if group else None)
        tab.chip.setToolTip(group["name"] if group else "")

    # ---------------------------------------------------------- pin/mute
    def pin_tab(self, tab_id, pinned=True):
        tab = self.by_id(tab_id)
        if not tab:
            return
        tab.pinned = pinned
        tab.chip.set_pinned(pinned)
        self._sort_and_sync()

    def toggle_mute(self, tab_id):
        tab = self.by_id(tab_id)
        if tab and tab.page is not None:
            tab.page.setAudioMuted(not tab.page.isAudioMuted())

    def _sort_and_sync(self):
        self.tabs.sort(key=lambda t: 0 if t.pinned else 1)
        self.strip.reorder_chips([t.id for t in self.tabs])
        self._refresh_chips()

    # ---------------------------------------------------------- lifecycle
    def new_tab(self, url=None, private=False, foreground=True):
        view = FolioView(self.stacked)
        profile = self.profiles.private if private else self.profiles.main
        page = StudyPage(profile, view, self.on_action, self._spawn_popup,
                         self.profiles.policy)
        view.setPage(page)
        view.setStyleSheet("background:#FFFFFF;")
        from PySide6.QtGui import QColor as _QC
        page.setBackgroundColor(_QC("#FFFFFF"))
        view.setZoomFactor(1.0)
        self.stacked.addWidget(view)
        tab = Tab(self._next_id, view, page, None, private)
        self._next_id += 1
        self.tabs.append(tab)
        tab.chip = self.strip.add_chip(tab.id)
        tab.chip.set_state(private=private)
        self._wire(tab)
        self.load(tab, url)
        self.count_changed.emit(len(self.tabs))
        if foreground:
            self.set_current(tab)
        else:
            self._refresh_chips()
        return tab

    def _spawn_popup(self, window_type=None):
        private = bool(self.current and self.current.private)
        bg = False
        try:
            bg = window_type == QWebEnginePage.WebWindowType.WebBrowserBackgroundTab
        except Exception:
            pass
        return self.new_tab(private=private, foreground=not bg).page

    def _wire(self, tab):
        page = tab.page
        page.titleChanged.connect(lambda t, tb=tab: self._on_title(tb, t))
        page.urlChanged.connect(lambda u, tb=tab: self._on_url(tb, u))
        page.loadStarted.connect(lambda tb=tab: self._on_load_start(tb))
        page.loadFinished.connect(
            lambda ok, tb=tab: self._on_load_finish(tb, ok))
        page.loadProgress.connect(lambda v, tb=tab: self._on_progress(tb, v))
        page.iconChanged.connect(lambda *_a, tb=tab: self._on_icon(tb))
        page.audioMutedChanged.connect(
            lambda m, tb=tab: self._on_audio(tb, m))
        page.recentlyAudibleChanged.connect(
            lambda a, tb=tab: self._on_audible(tb, a))
        page.loadingChanged.connect(
            lambda info, tb=tab: self._on_loading_info(tb, info))
        page.permissionRequested.connect(
            lambda perm, tb=tab: ask_permission(
                self.stacked.window(), perm, self.storage))
        page.linkHovered.connect(lambda u, tb=tab: self._on_hover(tb, u))
        page.fullScreenRequested.connect(
            lambda req, tb=tab: self.fullscreen_requested.emit(req))
        page.certificateError.connect(lambda err: self.cert_error.emit(err))
        page.authenticationRequired.connect(
            lambda url, auth, tb=tab: self.auth_needed.emit(tb, url, auth))
        page.proxyAuthenticationRequired.connect(
            lambda url, auth, host, tb=tab: self.auth_needed.emit(tb, url, auth))
        tab.view.open_link.connect(self.open_link)
        tab.view.save_link_as_source.connect(self.save_link)
        tab.view.note_from_selection.connect(
            lambda text: self.note_from_selection.emit(text))
        tab.view.search_selection.connect(
            lambda text: self.search_selection.emit(text))

    def _on_hover(self, tab, url):
        if tab is self.current:
            self.link_hovered.emit(url)

    # ---------------------------------------------------------- sleeping
    def sleep_tab(self, tab):
        if tab is self.current or tab.page is None or tab.sleeping \
                or tab.loading or tab.audible:
            return False
        try:
            tab.page.setLifecycleState(QWebEnginePage.LifecycleState.Discarded)
        except Exception:
            return False
        tab.sleeping = True
        tab.chip.set_sleeping(True)
        return True

    def wake_tab(self, tab):
        if tab.page is not None and tab.sleeping:
            try:
                tab.page.setLifecycleState(QWebEnginePage.LifecycleState.Active)
            except Exception:
                pass
        tab.sleeping = False
        tab.chip.set_sleeping(False)

    def sleep_idle(self, force=False):
        """Discard background tabs idle longer than the configured limit."""
        if not force and self.sleep_after_min <= 0:
            return 0
        limit = self.sleep_after_min * 60
        n = 0
        now = time.time()
        for tab in self.tabs:
            if tab is self.current:
                continue
            if force or now - tab.last_active >= limit:
                n += 1 if self.sleep_tab(tab) else 0
        return n

    def _on_audible(self, tab, audible):
        tab.audible = bool(audible)
        tab.chip.set_audio(bool(audible), tab.page.isAudioMuted()
                           if tab.page is not None else False)

    def _on_audio(self, tab, muted):
        tab.chip.set_audio(tab.audible, muted)

    def _on_loading_info(self, tab, info):
        """Show our own error page for real network failures only.

        HTTP 4xx/5xx keep the site's own page; user aborts (ERR_ABORTED) and
        downloads are ignored.
        """
        try:
            S, D = info.LoadStatus, info.ErrorDomain
            if info.status() != S.LoadFailedStatus:
                tab.error = ""
                return
            if info.errorCode() == -3:
                tab.error = ""
                return
            if info.errorDomain() not in (D.ConnectionErrorDomain, D.DnsErrorDomain,
                                          D.CertificateErrorDomain):
                tab.error = ""
                return
            tab.error = f"{info.errorString()} ({info.errorCode()})"
            failed_url = info.url().toString()
        except Exception:
            tab.error = ""
            return
        if tab.view is None or not failed_url.startswith(("http://", "https://")):
            return
        QTimer.singleShot(0, lambda tb=tab, u=failed_url: self._show_error(tb, u))

    def _show_error(self, tab, url):
        if tab.view is None or not tab.error:
            return
        from ui.home import error_html
        tab.view.setHtml(error_html(url, self.dark_get(), tab.error), QUrl(url))
        tab.title = ERROR_TITLE
        tab.chip.set_title(tab.title)

    def _destroy(self, tab):
        if tab.view is not None:
            tab.view.stop()
            self.stacked.removeWidget(tab.view)
            tab.view.deleteLater()
        tab.view = None
        tab.page = None

    def close_tab(self, tab_id):
        tab = self.by_id(tab_id)
        if not tab:
            return
        was_current = self.current is tab
        idx = self.tabs.index(tab)
        self.session.push_closed(tab.url, tab.title, tab.private)
        self.tabs.remove(tab)
        self.strip.remove_chip(tab_id)
        self._destroy(tab)
        self.count_changed.emit(len(self.tabs))
        if not self.tabs:
            if self._closing:
                return
            self.new_tab()
            return
        if was_current:
            self.set_current(self.tabs[min(idx, len(self.tabs) - 1)])

    def close_others(self, tab_id):
        for other in [t for t in self.tabs
                      if t.id != tab_id and not t.pinned]:
            self.close_tab(other.id)

    def close_right(self, tab_id):
        if self.by_id(tab_id) is None:
            return
        idx = self.tabs.index(self.by_id(tab_id))
        for other in [t for t in self.tabs[idx + 1:] if not t.pinned]:
            self.close_tab(other.id)

    def duplicate_tab(self, tab_id):
        tab = self.by_id(tab_id)
        if tab:
            self.new_tab(tab.url, private=tab.private)

    def close_all(self):
        self._closing = True
        for tab in list(self.tabs):
            self.session.push_closed(tab.url, tab.title, tab.private)
            self.strip.remove_chip(tab.id)
            self._destroy(tab)
        self.tabs.clear()
        self.strip.clear()

    def by_id(self, tab_id):
        for tab in self.tabs:
            if tab.id == tab_id:
                return tab
        return None

    @property
    def current(self):
        if self.tabs and 0 <= self.stacked.currentIndex() < len(self.tabs):
            return self.tabs[self.stacked.currentIndex()]
        return None

    def set_current(self, tab):
        if tab in self.tabs:
            prev = self.current
            if prev is not None and prev is not tab:
                prev.last_active = time.time()
            if tab.sleeping:
                self.wake_tab(tab)
            tab.last_active = time.time()
            self.stacked.setCurrentWidget(tab.view)
            self._emit_current()
            self.strip.ensure_visible(tab.id)

    def activate(self, tab_id):
        tab = self.by_id(tab_id)
        if tab:
            self.set_current(tab)

    def reorder(self, ids):
        ordered = []
        for tid in ids:
            tab = self.by_id(tid)
            if tab and tab not in ordered:
                ordered.append(tab)
        for tab in self.tabs:
            if tab not in ordered:
                ordered.append(tab)
        pinned = [t for t in ordered if t.pinned]
        free = [t for t in ordered if not t.pinned]
        self.tabs = pinned + free

    def find_duplicate(self, url, exclude_id):
        if not url or not url.startswith("http"):
            return None
        norm = url.rstrip("/")
        for tab in self.tabs:
            if tab.id != exclude_id and tab.url.rstrip("/") == norm:
                return tab
        return None

    def _refresh_chips(self):
        for tab in self.tabs:
            tab.chip.set_state(active=tab is self.current,
                               private=tab.private)

    def _emit_current(self):
        tab = self.current
        if not tab:
            return
        self._refresh_chips()
        self.current_changed.emit()
        self.url_changed.emit(tab.url)
        self.title_changed.emit(tab.title)
        self.loading_changed.emit(tab.loading)
        if tab.view is not None:
            self.icon_changed.emit(tab.view.icon())

    # ---------------------------------------------------------- page events
    def _on_title(self, tab, title):
        if not title:
            return
        tab.title = title
        tab.chip.set_title(title)
        if tab is self.current:
            self.title_changed.emit(title)

    def _on_url(self, tab, url):
        tab.url = url.toString()
        if tab is self.current:
            self.url_changed.emit(tab.url)

    def _on_load_start(self, tab):
        tab.loading = True
        if not self._spin_timer.isActive():
            self._spin_timer.start()
        if tab is self.current:
            self.loading_changed.emit(True)
        other = self.find_duplicate(tab.url, tab.id)
        key = (tab.id, tab.url)
        if other is not None and key not in self._dup_shown:
            self._dup_shown.add(key)
            self.duplicate_detected.emit(tab.id, other.id, tab.url)

    def _on_load_finish(self, tab, ok):
        tab.loading = False
        if tab.view is not None:
            ic = tab.view.icon()
            if not ic.isNull():
                tab.chip.set_icon_pixmap(ic.pixmap(16, 16))
            else:
                tab.chip.set_icon_pixmap(None)
        if not any(t.loading for t in self.tabs):
            self._spin_timer.stop()
        if tab is self.current:
            self.loading_changed.emit(False)
            self.progress_changed.emit(100)
        self.page_loaded.emit(tab)
        if ok and not tab.private and tab.title != ERROR_TITLE:
            qurl = QUrl(tab.url)
            if qurl.scheme() in ("http", "https"):
                self.storage.add_visit(tab.url, tab.title or qurl.host())

    def _on_progress(self, tab, value):
        if tab is self.current:
            self.progress_changed.emit(value)

    def _on_icon(self, tab):
        if tab.view is None:
            return
        ic = tab.view.icon()
        if not ic.isNull() and not tab.loading:
            tab.chip.set_icon_pixmap(ic.pixmap(16, 16))
        if tab is self.current:
            self.icon_changed.emit(ic)

    def _tick_spin(self):
        self._spin_idx = (self._spin_idx + 1) % 8
        frames = icons.spinner_frames(14, T["ink2"])
        for tab in self.tabs:
            if tab.loading:
                tab.chip.icon_label.setPixmap(frames[self._spin_idx])
        if not any(t.loading for t in self.tabs):
            self._spin_timer.stop()

    # ---------------------------------------------------------- navigation
    def load(self, tab, url=None):
        if tab.view is None:
            return
        if not url or url == HOME_URL:
            from ui.home import home_html
            tab.view.setHtml(
                home_html(self.storage, tab.private, self.session,
                          self.dark_get()), QUrl(HOME_URL))
            tab.url = HOME_URL
            tab.title = "Home"
            tab.chip.set_title("Home")
            if tab is self.current:
                self.url_changed.emit(HOME_URL)
                self.title_changed.emit("Home")
        else:
            tab.view.setUrl(QUrl(url))

    def session_snapshot(self):
        active = self.tabs.index(self.current) if self.current else 0
        return ([{"url": t.url, "title": t.title, "private": t.private,
                  "pinned": t.pinned, "group": t.group}
                 for t in self.tabs], active)