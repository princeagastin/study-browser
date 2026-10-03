"""Download manager: live progress, history in SQLite, a side panel UI."""
import os
import time

from PySide6.QtCore import Qt, Signal, QObject, QUrl, QTimer, QStandardPaths
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest as DL
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QToolButton, QProgressBar, QFileDialog, QFrame,
                               QScrollArea, QSizePolicy)

from ui import icons
from ui.panels import BasePanel
from ui.theme import TOKENS as T


def human(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def safe_name(name):
    name = os.path.basename(name or "download").strip().strip(".") or "download"
    return "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in name)


def unique_path(folder, name):
    base, ext = os.path.splitext(name)
    path, i = os.path.join(folder, name), 1
    while os.path.exists(path):
        path = os.path.join(folder, f"{base} ({i}){ext}")
        i += 1
    return path


def default_folder():
    return QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DownloadLocation) or os.path.expanduser("~")


class DownloadItem(QObject):
    changed = Signal()

    def __init__(self, req, db_id, parent=None):
        super().__init__(parent)
        self.req, self.db_id = req, db_id
        self.name = os.path.basename(req.downloadFileName() or "download")
        self.url = req.url().toString()
        self.state = "progress"
        self.received = self.total = 0
        self.speed = 0.0
        self._last = (time.time(), 0)
        req.receivedBytesChanged.connect(self._progress)
        req.stateChanged.connect(self._state)

    @property
    def path(self):
        try:
            return os.path.join(self.req.downloadDirectory(), self.req.downloadFileName())
        except RuntimeError:
            return ""

    def _progress(self):
        try:
            self.received, self.total = self.req.receivedBytes(), self.req.totalBytes()
        except RuntimeError:
            return
        now = time.time()
        dt = now - self._last[0]
        if dt >= 0.6:
            inst = (self.received - self._last[1]) / dt
            self.speed = inst if not self.speed else self.speed * 0.6 + inst * 0.4
            self._last = (now, self.received)
        self.changed.emit()

    def _state(self, state):
        S = DL.DownloadState
        self.state = {S.DownloadCompleted: "done", S.DownloadCancelled: "cancelled",
                      S.DownloadInterrupted: "failed",
                      S.DownloadInProgress: "progress",
                      S.DownloadRequested: "progress"}.get(state, "progress")
        self.changed.emit()

    def eta(self):
        if self.speed > 1 and self.total > self.received > 0:
            s = int((self.total - self.received) / self.speed)
            return f"{s // 60}m {s % 60:02d}s left" if s >= 60 else f"{s}s left"
        return ""

    def cancel(self):
        try:
            self.req.cancel()
        except RuntimeError:
            pass

    def toggle_pause(self):
        try:
            if self.req.isPaused():
                self.req.resume()
            else:
                self.req.pause()
        except RuntimeError:
            pass
        self.changed.emit()

    @property
    def paused(self):
        try:
            return self.req.isPaused()
        except RuntimeError:
            return False


class DownloadManager(QObject):
    activity = Signal(int, float)          # active count, 0..1 progress
    finished = Signal(object)              # DownloadItem
    started = Signal(object)
    list_changed = Signal()

    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.items = []
        self.ask_where = False
        self.parent_window = None

    def folder(self):
        saved = self.storage.get_setting("download_dir", "")
        return saved if saved and os.path.isdir(saved) else default_folder()

    def handle(self, req):
        try:
            if req.state() != DL.DownloadState.DownloadRequested:
                return                      # already handled (or cancelled)
        except RuntimeError:
            return
        name = safe_name(req.downloadFileName() or req.suggestedFileName())
        folder = self.folder()
        if self.storage.get_setting("ask_download", "0") == "1":
            path, _ = QFileDialog.getSaveFileName(
                self.parent_window, "Save file", os.path.join(folder, name))
            if not path:
                req.cancel()
                return
            folder, name = os.path.dirname(path), os.path.basename(path)
        else:
            name = os.path.basename(unique_path(folder, name))
        req.setDownloadDirectory(folder)
        req.setDownloadFileName(name)
        db_id = self.storage.add_download(name, req.url().toString(),
                                          os.path.join(folder, name))
        item = DownloadItem(req, db_id, self)
        item.changed.connect(lambda it=item: self._on_change(it))
        self.items.insert(0, item)
        req.accept()
        self.started.emit(item)
        self.list_changed.emit()
        self._emit_activity()

    def _on_change(self, item):
        if item.state != "progress" and not getattr(item, "_recorded", False):
            item._recorded = True
            self.storage.finish_download(item.db_id, item.state, item.received)
            if item.state == "done":
                self.finished.emit(item)
        self._emit_activity()

    def active(self):
        return [i for i in self.items if i.state == "progress"]

    def _emit_activity(self):
        act = self.active()
        total = sum(i.total for i in act if i.total > 0)
        got = sum(i.received for i in act if i.total > 0)
        self.activity.emit(len(act), (got / total) if total else 0.03)

    def cancel_all(self):
        for i in self.active():
            i.cancel()


class DownloadRow(QFrame):
    remove_requested = Signal(object)

    def __init__(self, item, db_row=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.item = item
        self.db = db_row
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 10, 10)
        lay.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.icon = QLabel(self)
        self.icon.setFixedSize(20, 20)
        self.name = QLabel(self)
        self.name.setStyleSheet("font-weight:600;")
        self.name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.btn_a = self._tb("pause")
        self.btn_b = self._tb("close")
        top.addWidget(self.icon)
        top.addWidget(self.name, 1)
        top.addWidget(self.btn_a)
        top.addWidget(self.btn_b)
        lay.addLayout(top)
        self.bar = QProgressBar(self)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        lay.addWidget(self.bar)
        self.status = QLabel(self)
        self.status.setObjectName("faint")
        lay.addWidget(self.status)
        if item is not None:
            item.changed.connect(self.refresh)
        self.refresh()

    def _tb(self, icon):
        b = QToolButton(self)
        b.setObjectName("tiny")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setIcon(icons.icon(icon, 14, T["ink2"]))
        return b

    def _path(self):
        return self.item.path if self.item is not None else (self.db["path"] or "")

    def _state(self):
        return self.item.state if self.item is not None else (self.db["state"] or "done")

    def refresh(self):
        name = self.item.name if self.item is not None else self.db["name"]
        st = self._state()
        self.name.setText(name)
        exists = os.path.exists(self._path())
        self.icon.setPixmap(icons.pixmap(
            "check" if st == "done" else "download", 16,
            T["success"] if st == "done" else T["accent"]))
        for b in (self.btn_a, self.btn_b):
            try:
                b.clicked.disconnect()
            except RuntimeError:
                pass
        if st == "progress":
            it = self.item
            self.bar.setVisible(True)
            if it.total > 0:
                self.bar.setRange(0, 1000)
                self.bar.setValue(int(1000 * it.received / it.total))
            else:
                self.bar.setRange(0, 0)
            bits = [f"{human(it.received)} of {human(it.total)}" if it.total > 0
                    else human(it.received)]
            if it.paused:
                bits.append("Paused")
            else:
                if it.speed:
                    bits.append(f"{human(it.speed)}/s")
                if it.eta():
                    bits.append(it.eta())
            self.status.setText("  ·  ".join(bits))
            self.btn_a.setVisible(True)
            self.btn_a.setIcon(icons.icon("play" if it.paused else "pause", 14, T["ink2"]))
            self.btn_a.setToolTip("Resume" if it.paused else "Pause")
            self.btn_a.clicked.connect(lambda _c=False: it.toggle_pause())
            self.btn_b.setIcon(icons.icon("close", 14, T["ink2"]))
            self.btn_b.setToolTip("Cancel")
            self.btn_b.clicked.connect(lambda _c=False: it.cancel())
        else:
            self.bar.setVisible(False)
            if st == "done":
                size = self.item.received if self.item is not None else self.db["size"]
                msg = human(size) + ("" if exists else "  ·  File moved or deleted")
            else:
                msg = "Cancelled" if st == "cancelled" else "Failed"
            self.status.setText(msg)
            self.btn_a.setVisible(exists and st == "done")
            self.btn_a.setIcon(icons.icon("folder", 14, T["ink2"]))
            self.btn_a.setToolTip("Show in folder")
            self.btn_a.clicked.connect(lambda _c=False: reveal(self._path()))
            self.btn_b.setIcon(icons.icon("trash", 14, T["ink2"]))
            self.btn_b.setToolTip("Remove from list")
            self.btn_b.clicked.connect(
                lambda _c=False: self.remove_requested.emit(self))

    def mouseDoubleClickEvent(self, e):
        if self._state() == "done" and os.path.exists(self._path()):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._path()))


def reveal(path):
    if not path:
        return
    folder = os.path.dirname(path)
    if os.name == "nt" and os.path.exists(path):
        import subprocess
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


class DownloadsPanel(BasePanel):
    def __init__(self, storage, manager, parent=None):
        super().__init__(storage, "Downloads", parent)
        self.manager = manager
        self.search.hide()
        self.list.hide()
        self._rows = []
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.body.setStyleSheet("background:transparent;")
        self.vbox = QVBoxLayout(self.body)
        self.vbox.setContentsMargins(0, 0, 4, 0)
        self.vbox.setSpacing(8)
        self.vbox.addStretch(1)
        scroll.setWidget(self.body)
        self.layout().insertWidget(1, scroll, 1)
        self.empty = QLabel("No downloads yet.\nFiles you download appear here.", self)
        self.empty.setObjectName("faint")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout().insertWidget(1, self.empty, 1)
        foot = QHBoxLayout()
        clear = QToolButton(self)
        clear.setObjectName("link")
        clear.setText("Clear finished")
        clear.clicked.connect(lambda _c=False: self.clear_finished())
        opn = QToolButton(self)
        opn.setObjectName("link")
        opn.setText("Open folder")
        opn.clicked.connect(lambda _c=False: QDesktopServices.openUrl(
            QUrl.fromLocalFile(self.manager.folder())))
        foot.addWidget(clear)
        foot.addStretch(1)
        foot.addWidget(opn)
        self.layout().addLayout(foot)
        manager.list_changed.connect(self.reload)
        self.reload()

    def reload(self):
        for row in self._rows:
            self.vbox.removeWidget(row)
            row.deleteLater()
        self._rows = []
        live_ids = {i.db_id for i in self.manager.items}
        entries = [(i, None) for i in self.manager.items]
        for r in self.storage.list_downloads(60):
            if r["id"] not in live_ids and r["state"] != "progress":
                entries.append((None, r))
        for item, db in entries:
            row = DownloadRow(item, db, self.body)
            row.remove_requested.connect(self.remove)
            self.vbox.insertWidget(self.vbox.count() - 1, row)
            self._rows.append(row)
        self.empty.setVisible(not entries)
        self.count.setText(f"{len(entries)} FILES" if entries else "")

    def remove(self, row):
        if row.item is not None:
            self.manager.items = [i for i in self.manager.items if i is not row.item]
            self.storage.delete_download(row.item.db_id)
        elif row.db is not None:
            self.storage.delete_download(row.db["id"])
        self.reload()

    def clear_finished(self):
        self.manager.items = [i for i in self.manager.items if i.state == "progress"]
        self.storage.clear_downloads()
        self.reload()
