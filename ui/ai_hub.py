from PySide6.QtCore import Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineWidgets import QWebEngineView


class AIHub(QFrame):
    """Right-side AI hub with switchable AI websites."""

    request_close = Signal()

    PROVIDERS = [
        ("ChatGPT", "https://chatgpt.com/"),
        ("Gemini", "https://gemini.google.com/"),
        ("Claude", "https://claude.ai/"),
        ("Perplexity", "https://www.perplexity.ai/"),
        ("Microsoft Copilot", "https://copilot.microsoft.com/"),
        ("Hugging Face", "https://huggingface.co/chat/"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aiHub")
        self.setFixedWidth(430)
        self._views = {}
        self._urls = dict(self.PROVIDERS)

        self.setStyleSheet("""
            QFrame#aiHub {
                background: #ffffff;
                border-left: 1px solid #e4e7ec;
            }
            QLabel#aiTitle {
                font-size: 16px;
                font-weight: 700;
                color: #121417;
            }
            QComboBox {
                min-height: 36px;
                border: 1px solid #d9dee8;
                border-radius: 8px;
                padding: 0 10px;
                background: #f8fafc;
            }
            QPushButton {
                min-height: 34px;
                border: 1px solid #d9dee8;
                border-radius: 8px;
                padding: 0 10px;
                background: #f8fafc;
            }
            QPushButton:hover {
                border-color: #2F5FE0;
                color: #2F5FE0;
            }
            QLabel#hint {
                font-size: 11px;
                color: #667085;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("✨ AI Hub")
        title.setObjectName("aiTitle")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(34, 34)
        close_btn.clicked.connect(self.request_close.emit)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_btn)
        root.addLayout(header)

        controls = QHBoxLayout()
        self.provider_box = QComboBox()
        self.provider_box.addItems([name for name, _ in self.PROVIDERS])
        self.provider_box.currentTextChanged.connect(self._switch_provider)

        self.reload_btn = QPushButton("⟳")
        self.reload_btn.setFixedWidth(42)
        self.reload_btn.clicked.connect(self.reload_current)

        self.external_btn = QPushButton("↗")
        self.external_btn.setFixedWidth(42)
        self.external_btn.clicked.connect(self.open_external)

        controls.addWidget(self.provider_box, 1)
        controls.addWidget(self.reload_btn)
        controls.addWidget(self.external_btn)
        root.addLayout(controls)

        hint = QLabel("Switch AI bots without leaving your current webpage.")
        hint.setObjectName("hint")
        root.addWidget(hint)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self._switch_provider(self.provider_box.currentText())

    def _switch_provider(self, name):
        url = self._urls.get(name)
        if not url:
            return

        view = self._views.get(name)
        if view is None:
            view = QWebEngineView(self.stack)
            view.setUrl(QUrl(url))
            self._views[name] = view
            self.stack.addWidget(view)

        self.stack.setCurrentWidget(view)

    def current_name(self):
        return self.provider_box.currentText()

    def current_view(self):
        return self._views.get(self.current_name())

    def reload_current(self):
        view = self.current_view()
        if view is not None:
            view.reload()

    def open_external(self):
        url = self._urls.get(self.current_name())
        if url:
            QDesktopServices.openUrl(QUrl(url))
