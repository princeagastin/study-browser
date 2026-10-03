"""Reusable, dependency-free building blocks shared by the whole UI."""
from PySide6.QtCore import (Qt, QSize, QRect, QRectF, QPoint, Signal,
                            QPropertyAnimation, QEasingCurve, Property, QTimer)
from PySide6.QtGui import QPainter, QColor, QPen, QFontMetrics, QFont, QIcon
from PySide6.QtWidgets import (QMenu, QAbstractButton, QStyledItemDelegate,
                               QStyle, QWidget, QHBoxLayout, QPushButton,
                               QButtonGroup, QFrame, QLabel, QToolButton,
                               QVBoxLayout)

from ui import icons
from ui.theme import TOKENS as T

SUB_ROLE = Qt.ItemDataRole.UserRole + 20
META_ROLE = Qt.ItemDataRole.UserRole + 21
CAP_ROLE = Qt.ItemDataRole.UserRole + 22
BADGE_ROLE = Qt.ItemDataRole.UserRole + 23


def qcolor(value: str) -> QColor:
    """QColor from '#rrggbb' *or* 'rgba(r,g,b,a)' token strings."""
    value = str(value).strip()
    if value.startswith("rgba"):
        nums = value[value.index("(") + 1:value.index(")")].split(",")
        r, g, b = (int(float(n)) for n in nums[:3])
        a = float(nums[3]) if len(nums) > 3 else 1.0
        return QColor(r, g, b, int(a * 255))
    return QColor(value)


def paint_shadow(painter: QPainter, rect: QRect, radius: int = 14,
                 spread: int = 14, strength: int = 46):
    """Soft drop shadow drawn with stacked translucent rounded rects.

    Deliberately not a QGraphicsEffect: effects are slow and unreliable on top
    of WebEngine surfaces.
    """
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    for i in range(spread, 0, -1):
        alpha = int(strength * (1 - i / (spread + 1)) ** 2.2 / 4)
        painter.setBrush(QColor(0, 0, 0, max(alpha, 1)))
        r = rect.adjusted(-i, -i + 3, i, i + 3)
        painter.drawRoundedRect(r, radius + i, radius + i)
    painter.restore()


class RoundMenu(QMenu):
    """QMenu whose QSS border-radius actually renders (translucent window)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def add(self, icon_name, text, slot=None, shortcut="", enabled=True,
            color=None):
        act = self.addAction(icons.icon(icon_name, 15, color or T["ink2"]),
                             text + (("\t" + shortcut) if shortcut else ""))
        act.setEnabled(enabled)
        if slot is not None:
            act.triggered.connect(lambda _c=False, s=slot: s())
        return act

    def submenu(self, icon_name, title):
        sub = RoundMenu(title, self)
        act = self.addMenu(sub)
        act.setIcon(icons.icon(icon_name, 15, T["ink2"]))
        return sub

    def section(self, text):
        act = self.addAction(text.upper())
        act.setEnabled(False)
        f = QFont(T["font"].split(",")[0].strip("'"), 7, QFont.Weight.Bold)
        act.setFont(f)
        return act


class Switch(QAbstractButton):
    """iOS-style toggle. Drop-in for a checkable QCheckBox."""

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(38, 22)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _get_knob(self):
        return self._pos

    def _set_knob(self, v):
        self._pos = v
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def sizeHint(self):
        return QSize(38, 22)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        off = qcolor(T["hairline"]) if not self.underMouse() else qcolor(T["ink3"])
        on = qcolor(T["accent"])
        t = self._pos
        col = QColor(int(off.red() + (on.red() - off.red()) * t),
                     int(off.green() + (on.green() - off.green()) * t),
                     int(off.blue() + (on.blue() - off.blue()) * t))
        if not self.isEnabled():
            col.setAlpha(110)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(0, 0, 38, 22), 11, 11)
        p.setBrush(QColor("#FFFFFF"))
        x = 3 + t * 16
        p.drawEllipse(QRectF(x, 3, 16, 16))
        p.end()


class Segmented(QFrame):
    """Pill-style single-choice selector: Segmented(['light','dark'])."""
    changed = Signal(str)

    def __init__(self, options, current=None, parent=None):
        super().__init__(parent)
        self.setObjectName("segFrame")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = {}
        for key, label in options:
            btn = QPushButton(label, self)
            btn.setCheckable(True)
            btn.setProperty("seg", "true")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumWidth(btn.fontMetrics().horizontalAdvance(label) + 34)
            btn.clicked.connect(lambda _c=False, k=key: self.changed.emit(k))
            self._group.addButton(btn)
            self._buttons[key] = btn
            lay.addWidget(btn)
        if current in self._buttons:
            self._buttons[current].setChecked(True)

    def value(self):
        for key, btn in self._buttons.items():
            if btn.isChecked():
                return key
        return None

    def set_value(self, key):
        if key in self._buttons:
            self._buttons[key].setChecked(True)


class RowDelegate(QStyledItemDelegate):
    """Two-line list row: icon · title/subtitle · right-aligned meta.

    Understands SUB_ROLE / META_ROLE; falls back to splitting DisplayRole on a
    newline so older call-sites keep working. CAP_ROLE renders a section label.
    """

    def __init__(self, parent=None, row_h=52, icon=20):
        super().__init__(parent)
        self.row_h = row_h
        self.icon = icon

    def sizeHint(self, option, index):
        if index.data(CAP_ROLE):
            return QSize(option.rect.width(), 30)
        return QSize(option.rect.width(), self.row_h)

    def paint(self, p: QPainter, option, index):
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(2, 1, -2, -1)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if index.data(CAP_ROLE):
            f = QFont(option.font)
            f.setPixelSize(10)
            f.setBold(True)
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
            p.setFont(f)
            p.setPen(qcolor(T["ink3"]))
            p.drawText(rect.adjusted(10, 8, 0, 0), Qt.AlignmentFlag.AlignLeft |
                       Qt.AlignmentFlag.AlignVCenter, text.upper())
            p.restore()
            return
        sub = index.data(SUB_ROLE)
        if sub is None and "\n" in text:
            text, sub = text.split("\n", 1)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        enabled = bool(index.flags() & Qt.ItemFlag.ItemIsEnabled) and \
            bool(index.flags() & Qt.ItemFlag.ItemIsSelectable)
        if enabled and (selected or hovered):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qcolor(T["accent_tint"] if selected else T["hover"]))
            p.drawRoundedRect(rect, 9, 9)
        x = rect.x() + 10
        deco = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(deco, QIcon) and not deco.isNull():
            deco.paint(p, QRect(x, rect.center().y() - self.icon // 2,
                                self.icon, self.icon))
            x += self.icon + 10
        elif not enabled:
            x += 4
        meta = index.data(META_ROLE)
        right = rect.right() - 10
        if meta:
            f = QFont(option.font)
            f.setPixelSize(11)
            p.setFont(f)
            fm = QFontMetrics(f)
            mw = fm.horizontalAdvance(str(meta))
            p.setPen(qcolor(T["ink3"]))
            p.drawText(QRect(right - mw, rect.y(), mw, rect.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       str(meta))
            right -= mw + 10
        avail = max(20, right - x)
        tf = QFont(option.font)
        tf.setPixelSize(13)
        tf.setWeight(QFont.Weight.DemiBold if enabled else QFont.Weight.Normal)
        p.setFont(tf)
        fm = QFontMetrics(tf)
        col = T["ink1"] if enabled else T["ink3"]
        if sub:
            p.setPen(qcolor(col))
            top = rect.y() + (rect.height() - 36) // 2
            p.drawText(QRect(x, top, avail, 18),
                       Qt.AlignmentFlag.AlignVCenter,
                       fm.elidedText(text, Qt.TextElideMode.ElideRight, avail))
            sf = QFont(option.font)
            sf.setPixelSize(11)
            p.setFont(sf)
            p.setPen(qcolor(T["ink3"]))
            sfm = QFontMetrics(sf)
            first = str(sub).replace("\n", "  ")
            p.drawText(QRect(x, top + 18, avail, 16),
                       Qt.AlignmentFlag.AlignVCenter,
                       sfm.elidedText(first, Qt.TextElideMode.ElideRight, avail))
        else:
            p.setPen(qcolor(col))
            if not enabled:
                p.drawText(rect.adjusted(x - rect.x(), 0, 0, 0),
                           Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                           text)
            else:
                p.drawText(QRect(x, rect.y(), avail, rect.height()),
                           Qt.AlignmentFlag.AlignVCenter,
                           fm.elidedText(text, Qt.TextElideMode.ElideRight, avail))
        p.restore()


class Toast(QFrame):
    """Transient bottom-centre notification, parented to the window so it
    never steals focus or floats over other applications."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toastBox")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 9, 10, 9)
        lay.setSpacing(10)
        self.icon = QLabel(self)
        self.icon.setFixedSize(18, 18)
        self.label = QLabel("", self)
        self.action = QToolButton(self)
        self.action.setObjectName("link")
        self.action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action.clicked.connect(self._fire)
        lay.addWidget(self.icon)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.action)
        self._cb = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def _fire(self):
        cb, self._cb = self._cb, None
        self.hide()
        if cb:
            cb()

    def show_message(self, text, icon="check", action=None, callback=None,
                     ms=3200, color=None):
        self.icon.setPixmap(icons.pixmap(icon, 16, color or T["accent"]))
        self.label.setText(text)
        self._cb = callback
        self.action.setVisible(bool(action))
        self.action.setText(action or "")
        self.adjustSize()
        self.setFixedWidth(min(max(self.sizeHint().width(), 220), 560))
        self.reposition()
        self.show()
        self.raise_()
        self._timer.start(ms)

    def reposition(self):
        par = self.parentWidget()
        if par is None:
            return
        self.move((par.width() - self.width()) // 2,
                  par.height() - self.height() - 28)


def hline(parent=None) -> QFrame:
    f = QFrame(parent)
    f.setObjectName("hairline")
    f.setFrameShape(QFrame.Shape.NoFrame)
    return f


def caption(text: str, parent=None) -> QLabel:
    lab = QLabel(text.upper(), parent)
    lab.setObjectName("caption")
    return lab
