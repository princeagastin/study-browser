import math
from pathlib import Path

from PySide6.QtCore import (Qt, QRect, QSize, QUrl, Signal, QObject,
                            Property, QPropertyAnimation, QEasingCurve)
from PySide6.QtGui import QPainter, QColor, QPixmap, QFont, QImage
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QListWidget,
                               QListWidgetItem, QStyledItemDelegate,
                               QStyle, QMenu, QLabel, QToolButton)
from PySide6.QtNetwork import (QNetworkAccessManager, QNetworkRequest,
                               QNetworkReply)

from database.storage import Storage
from ui import icons, brand
from ui.theme import TOKENS as T
from ui.widgets import qcolor

ROOT = Path(__file__).resolve().parents[1]
FAVICON_CACHE = ROOT / "app_icons"

ID_ROLE = Qt.ItemDataRole.UserRole + 1
PIX_ROLE = Qt.ItemDataRole.UserRole + 2
URL_ROLE = Qt.ItemDataRole.UserRole + 3
HOST_ROLE = Qt.ItemDataRole.UserRole + 4

SOURCES = [
    "https://{h}/favicon.ico",          # the site itself first (no 3rd party)
    "https://icons.duckduckgo.com/ip3/{h}.ico",
]


class FaviconStore(QObject):
    """Multi-source favicon downloader with cache + passive capture."""
    icon_ready = Signal(str, object)   # host, QPixmap

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._nam.finished.connect(self._done)
        self._pending = {}

    def cache_path(self, host: str) -> Path:
        return FAVICON_CACHE / f"fav_{host}.png"

    def cached(self, host: str):
        if not host:
            return None
        path = self.cache_path(host)
        if path.exists():
            px = QPixmap(str(path))
            if not px.isNull():
                return px
        return None

    def request(self, host: str, index=0):
        if not host or index >= len(SOURCES):
            return
        url = QUrl(SOURCES[index].format(h=host))
        req = QNetworkRequest(url)
        req.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        reply = self._nam.get(req)
        self._pending[reply] = (host, index)

    def retry_all(self, hosts):
        for host in hosts:
            if self.cached(host) is None:
                self.request(host, 0)

    def _done(self, reply):
        entry = self._pending.pop(reply, None)
        if entry is None:
            reply.deleteLater()
            return
        host, index = entry
        ok = False
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                img = QImage()
                if img.loadFromData(bytes(reply.readAll())):
                    if img.width() >= 8 and img.height() >= 8:
                        px = QPixmap.fromImage(img)
                        FAVICON_CACHE.mkdir(parents=True, exist_ok=True)
                        px.save(str(self.cache_path(host)))
                        self.icon_ready.emit(host, px)
                        ok = True
        finally:
            reply.deleteLater()
        if not ok:
            self.request(host, index + 1)

    def store(self, host: str, px: QPixmap):
        """Passive capture from an open tab (any site)."""
        if not host or px is None or px.isNull():
            return
        FAVICON_CACHE.mkdir(parents=True, exist_ok=True)
        px.save(str(self.cache_path(host)))


class RailDelegate(QStyledItemDelegate):
    def __init__(self, rail, parent=None):
        super().__init__(parent)
        self.rail = rail

    def sizeHint(self, option, index):
        return QSize(40, 40)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(4, 2, -4, -2)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(T["hover"]))
            painter.drawRoundedRect(rect, 10, 10)
        px = index.data(PIX_ROLE)
        if px is not None:
            host = index.data(HOST_ROLE)
            scale = 1.0
            if host and host == self.rail.pulse_host:
                scale = 1.0 + 0.18 * math.sin(math.pi * self.rail.pulse_value)
            side = int(22 * scale)
            target = QRect(rect.center().x() - side // 2,
                           rect.center().y() - side // 2, side, side)
            painter.drawPixmap(target, px)
        host = index.data(HOST_ROLE)
        if host and host == self.rail.active_host:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(T["accent"]))
            painter.drawRoundedRect(option.rect.x() + 1,
                                    option.rect.center().y() - 8, 3, 16, 2, 2)
        painter.restore()


class QuickAppsRail(QWidget):
    app_open = Signal(str)
    manage_requested = Signal(object)

    def __init__(self, storage: Storage, parent=None):
        super().__init__(parent)
        self.setObjectName("rail")
        self.setFixedWidth(48)
        self.storage = storage
        self.store = FaviconStore(self)
        self.store.icon_ready.connect(self._apply_pix)
        self.active_host = ""
        self.pulse_host = ""
        self._pulse_v = 0.0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(6)
        self.logo = QLabel(self)
        self.logo.setFixedSize(30, 30)
        self.logo.setToolTip(brand.NAME)
        lay.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignHCenter)
        self.list = QListWidget(self)
        self.list.setObjectName("railList")
        self.list.setItemDelegate(RailDelegate(self, self.list))
        self.list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list.setSpacing(2)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context)
        self.list.itemClicked.connect(self._clicked)
        self.list.model().rowsMoved.connect(self._persist_order)
        lay.addWidget(self.list, 1)
        self.add_btn = QToolButton(self)
        self.add_btn.setObjectName("tiny")
        self.add_btn.setIcon(icons.icon("plus", 15, T["ink2"]))
        self.add_btn.setFixedSize(32, 32)
        self.add_btn.setToolTip("Add Quick App")
        self.add_btn.clicked.connect(
            lambda _c=False: self.manage_requested.emit(None))
        lay.addWidget(self.add_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        self.refresh()

    # ---------------------------------------------------------- brand logo
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qcolor(T["accent"]))
        p.drawRoundedRect(9, 10, 30, 30, 8, 8)
        p.setFont(QFont("Segoe UI", 12 if len(brand.MONOGRAM) <= 1 else 9,
                        QFont.Weight.Bold))
        p.setPen(qcolor(T["accent_ink"]))
        p.drawText(QRect(9, 10, 30, 30), Qt.AlignmentFlag.AlignCenter,
                   brand.MONOGRAM)
        p.end()

    # ---------------------------------------------------------- pulse anim
    def _get_pulse(self):
        return self._pulse_v

    def _set_pulse(self, value):
        self._pulse_v = value
        self.list.viewport().update()

    pulse_value = Property(float, _get_pulse, _set_pulse)

    def pulse(self, host):
        if not host:
            return
        self.pulse_host = host
        anim = QPropertyAnimation(self, b"pulse_value", self)
        anim.setDuration(240)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.start()

    # ---------------------------------------------------------- icons
    def _app_pixmap(self, field, name, host):
        if field and field.startswith("emoji:"):
            return icons.emoji_pixmap(field[6:], 20)
        if field and field.startswith("file:"):
            px = QPixmap(field[5:])
            if not px.isNull():
                return px.scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        px = self.store.cached(host)
        if px is not None:
            return px.scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        if host:
            self.store.request(host, 0)
        return icons.letter_pixmap((name or "?")[:1], 20)

    def _apply_pix(self, host, px):
        scaled = px.scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.data(HOST_ROLE) == host:
                item.setData(PIX_ROLE, scaled)
        self.list.viewport().update()

    def ingest(self, host, px):
        """Passive favicon capture from any visited tab."""
        if not host or px is None or px.isNull():
            return
        self.store.store(host, px)
        self._apply_pix(host, px)

    def refresh(self):
        self.list.clear()
        for row in self.storage.list_apps():
            host = QUrl(row["url"]).host()
            item = QListWidgetItem()
            item.setData(ID_ROLE, row["id"])
            item.setData(URL_ROLE, row["url"])
            item.setData(PIX_ROLE, self._app_pixmap(row["icon"] or "letter",
                                                    row["name"], host))
            item.setData(HOST_ROLE, host)
            item.setToolTip(f"<b>{row['name']}</b><br>"
                            f"<span style='color:#9AA3AF;'>{host}</span>")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled |
                          Qt.ItemFlag.ItemIsDropEnabled)
            self.list.addItem(item)

    def update_active(self, host):
        self.active_host = host
        self.list.viewport().update()

    def retheme(self):
        self.add_btn.setIcon(icons.icon("plus", 15, T["ink2"]))
        self.list.viewport().update()

    # ---------------------------------------------------------- interaction
    def _clicked(self, item):
        url = item.data(URL_ROLE)
        if url:
            self.pulse(item.data(HOST_ROLE))
            self.app_open.emit(url)

    def _context(self, pos):
        item = self.list.itemAt(pos)
        menu = QMenu(self)
        if item is not None:
            open_act = menu.addAction(icons.icon("tab", 15, T["ink2"]),
                                      "Open in New Tab")
            edit_act = menu.addAction(icons.icon("settings", 15, T["ink2"]),
                                      "Edit App…")
            menu.addSeparator()
            del_act = menu.addAction(icons.icon("trash", 15, T["danger"]),
                                     "Delete App")
            chosen = menu.exec(self.list.viewport().mapToGlobal(pos))
            if chosen == open_act:
                self.app_open.emit(item.data(URL_ROLE))
            elif chosen == edit_act:
                self.manage_requested.emit(item.data(ID_ROLE))
            elif chosen == del_act:
                self.storage.delete_app(item.data(ID_ROLE))
                self.refresh()
        else:
            add_act = menu.addAction(icons.icon("plus", 15, T["ink2"]),
                                     "Add Quick App…")
            ref_act = menu.addAction(icons.icon("reload", 15, T["ink2"]),
                                     "Refresh Icons")
            chosen = menu.exec(self.list.viewport().mapToGlobal(pos))
            if chosen == add_act:
                self.manage_requested.emit(None)
            elif chosen == ref_act:
                hosts = [self.list.item(i).data(HOST_ROLE)
                         for i in range(self.list.count())]
                self.store.retry_all([h for h in hosts if h])

    def _persist_order(self, *args):
        ids = [self.list.item(i).data(ID_ROLE)
               for i in range(self.list.count())]
        self.storage.reorder_apps(ids)