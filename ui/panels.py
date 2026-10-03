import time

from PySide6.QtCore import (Qt, Signal, QPropertyAnimation, QEasingCurve,
                            QTimer, QUrl, QRect)
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QToolButton, QLineEdit, QListWidget,
                               QListWidgetItem, QTextEdit, QFrame, QMenu,
                               QMessageBox, QInputDialog)

from database.storage import Storage, epoch
from ui import icons
from ui.quick_apps import FAVICON_CACHE
from ui.theme import TOKENS as T
from ui.widgets import RowDelegate, SUB_ROLE, META_ROLE, CAP_ROLE, qcolor, RoundMenu

PANEL_W = 340
URL_ROLE = Qt.ItemDataRole.UserRole
ROW_ROLE = Qt.ItemDataRole.UserRole + 1


def _host(url):
    return QUrl(url).host() or url


def _ago(ts):
    delta = time.time() - epoch(ts)
    if delta < 0:
        return ""
    if delta < 3600:
        return f"{max(1, int(delta / 60))}m ago"
    if delta < 86400:
        return f"{int(delta / 3600)}h ago"
    return f"{int(delta / 86400)}d ago"


def _site_icon(host):
    px = QPixmap(str(FAVICON_CACHE / f"fav_{host}.png"))
    if not px.isNull():
        return QIcon(px)
    return QIcon()


class BasePanel(QFrame):
    open_url = Signal(str)
    request_close = Signal()

    def __init__(self, storage: Storage, title, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.storage = storage
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        head = QHBoxLayout()
        head.setSpacing(8)
        label = QLabel(title)
        label.setStyleSheet(
            f"font-size:15px;font-weight:600;color:{T['ink1']};")
        self.count = QLabel("")
        self.count.setStyleSheet(
            f"color:{T['ink3']};font-size:10px;font-weight:600;")
        close = QToolButton(self)
        close.setObjectName("tiny")
        close.setIcon(icons.icon("close", 13, T["ink2"]))
        close.clicked.connect(lambda _c=False: self.request_close.emit())
        head.addWidget(label)
        head.addWidget(self.count, 1)
        head.addWidget(close)
        lay.addLayout(head)
        self.search = QLineEdit(self)
        self.search.setObjectName("panelSearch")
        self.search.setPlaceholderText("Search…")
        self.search.textChanged.connect(lambda _t: self.reload())
        lay.addWidget(self.search)
        self.list = QListWidget(self)
        self.list.setObjectName("panelList")
        self.list.setItemDelegate(RowDelegate(self.list, row_h=54, icon=20))
        self.list.setMouseTracking(True)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        lay.addWidget(self.list, 1)
        self._footer(lay)

    def _footer(self, lay):
        pass

    def reload(self):
        pass

    def _plain_item(self, text):
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.list.addItem(item)
        return item

    def _cap_item(self, text):
        cap = QListWidgetItem(text)
        cap.setFlags(Qt.ItemFlag.NoItemFlags)
        cap.setData(CAP_ROLE, True)
        self.list.addItem(cap)
        return cap


def save_text_file(parent, title, default_name, text, flt="All files (*)"):
    from PySide6.QtWidgets import QFileDialog
    import os
    start = os.path.join(os.path.expanduser("~"), default_name)
    path, _ = QFileDialog.getSaveFileName(parent, title, start, flt)
    if not path:
        return None
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class SavedPanel(BasePanel):
    def __init__(self, storage, parent=None):
        super().__init__(storage, "Saved Pages", parent)
        self.search.setPlaceholderText("Search saved… (#tag to filter)")
        exp = QToolButton(self)
        exp.setObjectName("link")
        exp.setText("Export bookmarks")
        exp.setCursor(Qt.CursorShape.PointingHandCursor)
        exp.clicked.connect(lambda _c=False: save_text_file(
            self, "Export saved pages", "folio-bookmarks.html",
            self.storage.export_saved_html(), "HTML (*.html)"))
        self.layout().addWidget(exp, 0, Qt.AlignmentFlag.AlignLeft)
        self.list.itemDoubleClicked.connect(self._open_item)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._ctx)
        self.reload()

    def reload(self):
        rows = self.storage.list_saved(self.search.text().strip())
        self.count.setText(f"{len(rows)} SAVED")
        self.list.clear()
        if not rows:
            self._plain_item("Nothing saved yet\n"
                             "Press Ctrl+D or the star in the address bar.")
            return
        for row in rows:
            host = _host(row["url"])
            tag = f"  #{row['tag']}" if row["tag"] else ""
            item = QListWidgetItem(
                f"{row['title'] or host}\n{host}  ·  "
                f"{_ago(row['created_at'])}{tag}")
            icon = _site_icon(host)
            if not icon.isNull():
                item.setIcon(icon)
            item.setData(URL_ROLE, row["url"])
            item.setData(ROW_ROLE, row["id"])
            self.list.addItem(item)

    def _open_item(self, item):
        url = item.data(URL_ROLE)
        if url:
            self.open_url.emit(url)

    def _ctx(self, pos):
        item = self.list.itemAt(pos)
        if item is None or not item.data(URL_ROLE):
            return
        menu = QMenu(self)
        open_act = menu.addAction("Open")
        new_act = menu.addAction("Open in New Tab")
        tag_act = menu.addAction("Add Tag…")
        menu.addSeparator()
        del_act = menu.addAction(icons.icon("trash", 15, T["danger"]),
                                 "Remove")
        chosen = menu.exec(self.list.viewport().mapToGlobal(pos))
        url = item.data(URL_ROLE)
        if chosen == open_act:
            self.open_url.emit(url)
        elif chosen == new_act:
            self.open_url.emit(url + "\tNEW")
        elif chosen == tag_act:
            text, ok = QInputDialog.getText(self, "Tag", "Tag name:")
            if ok:
                self.storage.set_saved_tag(url, text.strip())
                self.reload()
        elif chosen == del_act:
            self.storage.delete_saved(item.data(ROW_ROLE))
            self.reload()


class HistoryPanel(BasePanel):
    def __init__(self, storage, parent=None):
        super().__init__(storage, "Browsing History", parent)
        self.search.setPlaceholderText("Search history…")
        self.list.itemDoubleClicked.connect(self._open_item)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._ctx)
        self.reload()

    def _footer(self, lay):
        row = QHBoxLayout()
        row.addStretch(1)
        clear = QToolButton(self)
        clear.setObjectName("tiny")
        clear.setIcon(icons.icon("trash", 14, T["danger"]))
        clear.setToolTip("Clear all history")
        clear.clicked.connect(lambda _c=False: self._clear())
        row.addWidget(clear)
        lay.addLayout(row)

    def _clear(self):
        if QMessageBox.question(
                self, "Clear history", "Delete all browsing history?",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No) == \
                QMessageBox.StandardButton.Yes:
            self.storage.clear_history()
            self.reload()

    def reload(self):
        query = self.search.text().strip()
        rows = (self.storage.search_history(query) if query
                else self.storage.recent_history(60))
        self.count.setText(f"{len(rows)} VISITS")
        self.list.clear()
        if not rows and not query:
            pass
        if not query:
            top = self.storage.top_sites(4)
            if top:
                self._cap_item("Top sites this week")
                for row in top:
                    item = QListWidgetItem(
                        f"{row['title'] or _host(row['url'])}  —  "
                        f"{row['hits']} visits")
                    icon = _site_icon(_host(row["url"]))
                    if not icon.isNull():
                        item.setIcon(icon)
                    item.setData(URL_ROLE, row["url"])
                    self.list.addItem(item)
        if not rows:
            self._plain_item("No history yet\nPages you visit appear here.")
            return
        last_day = None
        for row in rows:
            stamp = epoch(row["visit_time"])
            day = time.strftime("%A %d %b", time.localtime(stamp))
            if day != last_day:
                last_day = day
                self._cap_item(day)
            count = row["visit_count"] or 1
            extra = f"  ·  ×{count}" if count > 1 else ""
            item = QListWidgetItem(
                f"{row['title'] or _host(row['url'])}\n"
                f"{_host(row['url'])}  ·  "
                f"{time.strftime('%H:%M', time.localtime(stamp))}{extra}")
            icon = _site_icon(_host(row["url"]))
            if not icon.isNull():
                item.setIcon(icon)
            item.setData(URL_ROLE, row["url"])
            item.setData(ROW_ROLE, row["id"])
            self.list.addItem(item)

    def _open_item(self, item):
        url = item.data(URL_ROLE)
        if url:
            self.open_url.emit(url)

    def _ctx(self, pos):
        item = self.list.itemAt(pos)
        if item is None or not item.data(URL_ROLE):
            return
        menu = QMenu(self)
        open_act = menu.addAction("Open")
        del_act = menu.addAction(icons.icon("trash", 15, T["danger"]),
                                 "Delete Entry")
        chosen = menu.exec(self.list.viewport().mapToGlobal(pos))
        if chosen == open_act:
            self.open_url.emit(item.data(URL_ROLE))
        elif chosen == del_act:
            self.storage.delete_history(item.data(ROW_ROLE))
            self.reload()


class NotesPanel(BasePanel):
    def __init__(self, storage, parent=None):
        super().__init__(storage, "Study Notes", parent)
        self.search.setPlaceholderText("Search notes…")
        self._current_id = None
        self._loading_note = False
        self.list.setMaximumHeight(150)
        self.list.itemClicked.connect(self._select_item)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self._flush)
        self.source_chip = QFrame(self)
        self.source_chip.setObjectName("omniBox")
        self.source_chip.setFixedHeight(30)
        chip_lay = QHBoxLayout(self.source_chip)
        chip_lay.setContentsMargins(8, 0, 8, 0)
        chip_lay.setSpacing(6)
        self.src_icon = QLabel(self.source_chip)
        self.src_icon.setFixedSize(16, 16)
        self.src_icon.setPixmap(icons.pixmap("globe", 14, T["ink3"]))
        self.src_title = QLabel("No source attached", self.source_chip)
        self.src_title.setStyleSheet(f"color:{T['ink2']};font-size:12px;")
        self.src_open = QToolButton(self.source_chip)
        self.src_open.setObjectName("tiny")
        self.src_open.setIcon(icons.icon("external", 13, T["ink2"]))
        self.src_open.clicked.connect(lambda _c=False: self._open_source())
        chip_lay.addWidget(self.src_icon)
        chip_lay.addWidget(self.src_title, 1)
        chip_lay.addWidget(self.src_open)
        self.source_chip.hide()
        self.layout().addWidget(self.source_chip)
        self.editor = QTextEdit(self)
        self.editor.setObjectName("noteEditor")
        self.editor.setPlaceholderText("Write your note…")
        self.editor.textChanged.connect(self._queue_save)
        self.layout().addWidget(self.editor, 3)
        self.status = QLabel("", self)
        self.status.setStyleSheet(
            f"color:{T['ink3']};font-size:10px;font-weight:600;")
        self.layout().addWidget(self.status)
        row = QHBoxLayout()
        new_btn = QToolButton(self)
        new_btn.setObjectName("chrome")
        new_btn.setIcon(icons.icon("note_add", 16, T["accent"]))
        new_btn.setToolTip("New note")
        new_btn.clicked.connect(lambda _c=False: self.new_note())
        del_btn = QToolButton(self)
        del_btn.setObjectName("chrome")
        del_btn.setIcon(icons.icon("trash", 16, T["ink2"]))
        del_btn.setToolTip("Delete note")
        del_btn.clicked.connect(lambda _c=False: self._delete())
        exp_btn = QToolButton(self)
        exp_btn.setObjectName("link")
        exp_btn.setText("Export Markdown")
        exp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exp_btn.clicked.connect(lambda _c=False: save_text_file(
            self, "Export notes", "folio-notes.md",
            self.storage.export_notes_markdown(), "Markdown (*.md)"))
        row.addWidget(new_btn)
        row.addWidget(del_btn)
        row.addStretch(1)
        row.addWidget(exp_btn)
        self.layout().addLayout(row)
        self.reload()

    def reload(self):
        rows = self.storage.list_notes(self.search.text().strip())
        self.count.setText(f"{len(rows)} NOTES")
        self.list.clear()
        if not rows:
            self._plain_item("No notes yet\nCreate one from any page.")
            return
        for row in rows:
            item = QListWidgetItem(
                f"{row['title'] or 'Untitled'}\n{_ago(row['updated_at'])}")
            item.setData(ROW_ROLE, row["id"])
            self.list.addItem(item)

    def new_note(self, source_url="", source_title=""):
        note_id = self.storage.create_note("Untitled note", "",
                                           source_url, source_title)
        self.reload()
        self._select_id(note_id)

    def create_from_page(self, url, title):
        self.new_note(url, title)

    def _select_item(self, item):
        note_id = item.data(ROW_ROLE)
        if note_id is not None:
            self._select_id(note_id)

    def _select_id(self, note_id):
        self._flush()
        self._current_id = note_id
        row = self.storage.get_note(note_id)
        if not row:
            return
        self._loading_note = True
        self.editor.setPlainText(row["content"] or "")
        self._loading_note = False
        if row["source_url"]:
            self.source_chip.show()
            self.src_title.setText(row["source_title"] or
                                   _host(row["source_url"]))
            self.src_title.setToolTip(row["source_url"])
            self.source_chip.setProperty("src_url", row["source_url"])
        else:
            self.source_chip.hide()
        self.status.setText("")

    def _queue_save(self):
        if self._loading_note or self._current_id is None:
            return
        self.status.setText("SAVING…")
        self._timer.start()

    def _flush(self):
        if self._current_id is None:
            return
        row = self.storage.get_note(self._current_id)
        if not row:
            return
        lines = self.editor.toPlainText().strip().splitlines()
        title = lines[0][:60] if lines else "Untitled note"
        self.storage.update_note(self._current_id, title,
                                 self.editor.toPlainText())
        self.status.setText("SAVED · " + time.strftime("%H:%M"))
        self.reload()

    def _delete(self):
        if self._current_id is None:
            return
        self.storage.delete_note(self._current_id)
        self._current_id = None
        self._loading_note = True
        self.editor.setPlainText("")
        self._loading_note = False
        self.source_chip.hide()
        self.status.setText("")
        self.reload()

    def _open_source(self):
        url = self.source_chip.property("src_url")
        if url:
            self.open_url.emit(url)


class PanelHost(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current = None
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.hide()

    def show_panel(self, panel: BasePanel):
        if self.current is panel and self.isVisible():
            self.close_panel()
            return
        if self.current is not None:
            self.current.hide()
        self.current = panel
        try:
            panel.request_close.disconnect(self.close_panel)
        except RuntimeError:
            pass
        panel.request_close.connect(self.close_panel)
        panel.setParent(self)
        panel.show()
        self.show()
        self.raise_()
        target = self._target_rect()
        panel.setGeometry(0, 0, target.width(), target.height())
        start = QRect(target.x() + target.width(), target.y(),
                      target.width(), target.height())
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(target)
        self._anim.start()

    def close_panel(self):
        if not self.isVisible() or self.current is None:
            return
        target = self._target_rect()
        off = QRect(self.parentWidget().width(), target.y(),
                    target.width(), target.height())
        self._anim.stop()
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(off)
        try:
            self._anim.finished.disconnect(self._after_close)
        except RuntimeError:
            pass
        self._anim.finished.connect(self._after_close)
        self._anim.start()

    def _after_close(self):
        try:
            self._anim.finished.disconnect(self._after_close)
        except RuntimeError:
            pass
        self.hide()

    def _target_rect(self):
        parent = self.parentWidget()
        return QRect(parent.width() - PANEL_W, 0, PANEL_W, parent.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.isVisible() and self._anim.state() != \
                QPropertyAnimation.State.Running:
            rect = self._target_rect()
            self.setGeometry(rect)
            if self.current is not None:
                self.current.setGeometry(0, 0, rect.width(), rect.height())