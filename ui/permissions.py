from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QCheckBox, QPushButton)
from PySide6.QtWebEngineCore import QWebEnginePermission

from ui import icons
from ui.theme import TOKENS as T

_PT = QWebEnginePermission.PermissionType


def _build_labels():
    mapping = [
        ("Geolocation", "see your location"),
        ("Location", "see your location"),
        ("MediaAudioCapture", "use your microphone"),
        ("MediaVideoCapture", "use your camera"),
        ("MediaAudioVideoCapture", "use your camera and microphone"),
        ("DesktopVideoCapture", "record your screen"),
        ("DesktopAudioVideoCapture", "record your screen and audio"),
        ("Notifications", "show notifications"),
        ("ClipboardReadWrite", "access your clipboard"),
        ("ClipboardSanitizedRead", "read your clipboard"),
        ("ClipboardSanitizedWrite", "write to your clipboard"),
    ]
    labels = {}
    for name, text in mapping:
        member = getattr(_PT, name, None)
        if member is not None:
            labels[member] = text
    return labels


LABELS = _build_labels()


def type_name(permission) -> str:
    return str(permission.permissionType()).split(".")[-1]


class PermissionDialog(QDialog):
    def __init__(self, host, label, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Permission request")
        self.setFixedWidth(360)
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        head = QHBoxLayout()
        ic = QLabel(self)
        ic.setPixmap(icons.pixmap("shield", 20, T["accent"]))
        text = QLabel(f"<b>{host}</b><br>"
                      f"<span style='color:{T['ink2']}'>wants to {label}"
                      "</span>", self)
        head.addWidget(ic)
        head.addWidget(text, 1)
        lay.addLayout(head)
        self.remember = QCheckBox("Remember this decision", self)
        self.remember.setChecked(True)
        lay.addWidget(self.remember)
        row = QHBoxLayout()
        row.addStretch(1)
        deny = QPushButton("Deny", self)
        allow = QPushButton("Allow", self)
        allow.setDefault(True)
        deny.clicked.connect(self.reject)
        allow.clicked.connect(self.accept)
        row.addWidget(deny)
        row.addWidget(allow)
        lay.addLayout(row)


def ask_permission(parent, permission: QWebEnginePermission,
                   storage=None) -> None:
    ptype = type_name(permission)
    host = permission.origin().host() or permission.origin().toString()
    if storage is not None:
        saved = storage.get_permission(host, ptype)
        if saved is not None:
            if saved:
                permission.grant()
            else:
                permission.deny()
            return
    label = LABELS.get(permission.permissionType(), ptype.lower())
    dialog = PermissionDialog(host, label, parent)
    granted = dialog.exec() == QDialog.DialogCode.Accepted
    if dialog.remember.isChecked() and storage is not None:
        storage.set_permission(host, ptype, granted)
    if granted:
        permission.grant()
    else:
        permission.deny()