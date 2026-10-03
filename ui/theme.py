"""Design tokens + the application stylesheet.

Everything visual flows from this file:

* ``LIGHT`` / ``DARK``       – base palettes
* ``ACCENTS``                – user-selectable accent presets
* ``set_mode`` / ``set_accent`` – mutate ``TOKENS`` *in place*, so every module
  that did ``from ui.theme import TOKENS as T`` sees the change immediately
* ``build_qss()``            – renders the stylesheet from the live tokens
"""
from ui import icons as _icons

FONT = "'Segoe UI Variable Text','Segoe UI','SF Pro Text','Inter',sans-serif"
MONO = "'Cascadia Code','JetBrains Mono','Consolas',monospace"

LIGHT = {
    "surface": "#FFFFFF",
    "shelf": "#EDEFF4",
    "field": "#F1F3F8",
    "field_hover": "#E9ECF3",
    "hairline": "#E1E5EC",
    "ink1": "#0F1419",
    "ink2": "#535E6D",
    "ink3": "#8892A2",
    "elev": "#FFFFFF",
    "scrim": "rgba(15,20,25,0.35)",
    "priv_bg": "#232838",
    "priv_text": "#E6E9F5",
    "priv_accent": "#8C95FF",
    "success": "#1F9D62",
    "warn": "#B7791F",
    "danger": "#D0443B",
    "hover": "rgba(15,23,42,0.055)",
    "pressed": "rgba(15,23,42,0.105)",
    "font": FONT,
    "mono": MONO,
}

DARK = {
    "surface": "#171A21",
    "shelf": "#0F1116",
    "field": "#20242D",
    "field_hover": "#282D38",
    "hairline": "#2A2F3A",
    "ink1": "#ECEFF5",
    "ink2": "#A4ADBC",
    "ink3": "#6F7A8C",
    "elev": "#1D2129",
    "scrim": "rgba(0,0,0,0.55)",
    "priv_bg": "#232838",
    "priv_text": "#E6E9F5",
    "priv_accent": "#8C95FF",
    "success": "#3DBE85",
    "warn": "#E0A93B",
    "danger": "#EE6B62",
    "hover": "rgba(255,255,255,0.07)",
    "pressed": "rgba(255,255,255,0.13)",
    "font": FONT,
    "mono": MONO,
}

# name -> (light accent, light hover, light tint, dark accent, dark hover, dark tint)
ACCENTS = {
    "blue":   ("#2F5FE0", "#264DBA", "#E8EEFE", "#7C9CFF", "#9BB2FF", "rgba(124,156,255,0.16)"),
    "violet": ("#6B4FE0", "#573FBA", "#EEEAFE", "#A08CFF", "#B9A9FF", "rgba(160,140,255,0.16)"),
    "teal":   ("#0E8F86", "#0B736C", "#E1F5F3", "#3CCFC3", "#65DDD3", "rgba(60,207,195,0.15)"),
    "green":  ("#2E8B57", "#256F46", "#E4F4EB", "#55C58A", "#7AD5A5", "rgba(85,197,138,0.15)"),
    "amber":  ("#C27A0E", "#9C6109", "#FCF1DC", "#F0B54A", "#F5C976", "rgba(240,181,74,0.15)"),
    "rose":   ("#D6336C", "#B02857", "#FCE7EF", "#FF7BA6", "#FF9BBB", "rgba(255,123,166,0.16)"),
}

TOKENS = dict(LIGHT)
_MODE = "light"
_ACCENT = "blue"


def current_mode() -> str:
    return _MODE


def current_accent() -> str:
    return _ACCENT


def is_dark() -> bool:
    return _MODE == "dark"


def _refresh():
    base = DARK if _MODE == "dark" else LIGHT
    TOKENS.clear()
    TOKENS.update(base)
    a = ACCENTS.get(_ACCENT, ACCENTS["blue"])
    if _MODE == "dark":
        acc, hov, tint = a[3], a[4], a[5]
        acc_ink = "#0B0E14"
    else:
        acc, hov, tint = a[0], a[1], a[2]
        acc_ink = "#FFFFFF"
    TOKENS.update({"accent": acc, "accent_hover": hov, "accent_tint": tint,
                   "accent_ink": acc_ink})


def set_mode(mode: str):
    global _MODE
    _MODE = "dark" if mode == "dark" else "light"
    _refresh()


def set_accent(name: str):
    global _ACCENT
    _ACCENT = name if name in ACCENTS else "blue"
    _refresh()


_refresh()

_QSS = """
* { font-family: @font; font-size: 13px; color: @ink1; }
QMainWindow, QWidget#central { background: @surface; }
QDialog, QMessageBox { background: @surface; }
QScrollArea { background: transparent; border: none; }
QStackedWidget { background: transparent; }
QLabel { background: transparent; }
QLabel#muted { color: @ink2; }
QLabel#faint { color: @ink3; font-size: 12px; }
QLabel#h1 { font-size: 20px; font-weight: 650; }
QLabel#h2 { font-size: 15px; font-weight: 600; }
QLabel#caption { color: @ink3; font-size: 10px; font-weight: 700; letter-spacing: 1px; }

/* ---------- buttons ---------- */
QToolButton#chrome {
  background: transparent; border: none; border-radius: 9px;
  min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px;
}
QToolButton#chrome:hover { background: @hover; }
QToolButton#chrome:pressed { background: @pressed; }
QToolButton#chrome:checked { background: @accent_tint; }
QToolButton#chrome:disabled { background: transparent; }
QToolButton#tiny {
  background: transparent; border: none; border-radius: 6px;
  min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px;
}
QToolButton#tiny:hover { background: @hover; }
QToolButton#tiny:pressed { background: @pressed; }
QToolButton#tiny:checked { background: @accent_tint; }
QToolButton#pill {
  background: @field; border: 1px solid transparent; border-radius: 12px;
  padding: 3px 10px; color: @ink2; font-size: 12px; font-weight: 600;
}
QToolButton#pill:hover { background: @field_hover; color: @ink1; }
QToolButton#pill:checked { background: @accent_tint; color: @accent; }
QToolButton#link {
  background: transparent; border: none; color: @accent; padding: 2px 6px;
  border-radius: 6px; font-weight: 600;
}
QToolButton#link:hover { background: @accent_tint; }
QPushButton {
  background: @field; border: 1px solid @hairline; border-radius: 8px;
  padding: 7px 16px; color: @ink1; font-weight: 500;
}
QPushButton:hover { background: @field_hover; }
QPushButton:pressed { background: @pressed; }
QPushButton:disabled { color: @ink3; }
QPushButton:default, QPushButton[primary="true"] {
  background: @accent; border: 1px solid @accent; color: @accent_ink; font-weight: 600;
}
QPushButton:default:hover, QPushButton[primary="true"]:hover {
  background: @accent_hover; border-color: @accent_hover;
}
QPushButton[danger="true"] { color: @danger; }
QPushButton[danger="true"]:hover { background: @field_hover; border-color: @danger; }
QPushButton[ghost="true"] { background: transparent; border-color: transparent; color: @ink2; }
QPushButton[ghost="true"]:hover { background: @hover; color: @ink1; }

/* ---------- inputs ---------- */
QLineEdit {
  background: @field; border: 1.5px solid transparent; border-radius: 8px;
  padding: 7px 10px; selection-background-color: @accent; selection-color: @accent_ink;
}
QLineEdit:hover { background: @field_hover; }
QLineEdit:focus { background: @surface; border: 1.5px solid @accent; }
QLineEdit#omni {
  background: transparent; border: none; font-size: 13px; padding: 0 4px;
  placeholder-text-color: @ink3;
}
QLineEdit#omni:hover, QLineEdit#omni:focus { background: transparent; border: none; }
QFrame#omniBox { background: @field; border: 1.5px solid transparent; border-radius: 11px; }
QFrame#omniBox:hover { background: @field_hover; }
QFrame#omniBox[focused="true"] { background: @surface; border: 1.5px solid @accent; }
QFrame#omniBox[private="true"] { background: @priv_bg; }
QFrame#omniBox[private="true"] QLineEdit#omni { color: @priv_text; placeholder-text-color: #8A93B8; }
QFrame#omniBox[private="true"][focused="true"] { background: @priv_bg; border: 1.5px solid @priv_accent; }
QFrame#omniBox[private="true"] QToolButton#tiny:hover { background: rgba(255,255,255,0.10); }
QLineEdit#panelSearch, QLineEdit#findInput, QLineEdit#paletteInput { font-size: 13px; }
QLineEdit#paletteInput { background: transparent; border: none; font-size: 16px; padding: 6px 4px; }
QLineEdit#paletteInput:focus, QLineEdit#paletteInput:hover { background: transparent; border: none; }
QTextEdit#noteEditor, QTextEdit {
  background: @surface; border: 1px solid @hairline; border-radius: 8px;
  padding: 10px; font-size: 14px; selection-background-color: @accent; selection-color: @accent_ink;
}
QTextEdit#noteEditor:focus, QTextEdit:focus { border: 1px solid @accent; }
QComboBox, QSpinBox {
  background: @field; border: 1px solid @hairline; border-radius: 8px;
  padding: 6px 10px; min-height: 18px;
}
QComboBox:hover, QSpinBox:hover { background: @field_hover; }
QComboBox:focus, QSpinBox:focus { border: 1px solid @accent; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
  background: @elev; border: 1px solid @hairline; border-radius: 8px; padding: 4px;
  selection-background-color: @accent_tint; selection-color: @ink1; outline: none;
}
QCheckBox, QRadioButton { background: transparent; spacing: 8px; }
QCheckBox::indicator {
  width: 16px; height: 16px; border-radius: 4px; border: 1.5px solid @ink3; background: transparent;
}
QCheckBox::indicator:hover { border-color: @accent; }
QCheckBox::indicator:checked { background: @accent; border-color: @accent; }
QRadioButton::indicator {
  width: 16px; height: 16px; border-radius: 9px; border: 1.5px solid @ink3; background: transparent;
}
QRadioButton::indicator:checked { border: 5px solid @accent; background: @surface; }

/* ---------- chrome regions ---------- */
QWidget#tabShelf { background: @shelf; }
QWidget#topBar { background: @surface; border-bottom: 1px solid @hairline; }
QWidget#bookmarksBar { background: @surface; border-bottom: 1px solid @hairline; }
QWidget#rail { background: @shelf; border-right: 1px solid @hairline; }
QListWidget#railList { background: transparent; border: none; outline: none; }
QListWidget#railList::item { background: transparent; border: none; }
QScrollArea#stripScroll, QScrollArea#bmScroll { background: transparent; border: none; }
QScrollArea#stripScroll > QWidget > QWidget { background: transparent; }
QFrame#panel { background: @surface; border-left: 1px solid @hairline; }
QFrame#card { background: @surface; border: 1px solid @hairline; border-radius: 12px; }
QFrame#cardField { background: @field; border: 1px solid transparent; border-radius: 10px; }
QFrame#secBanner { background: @elev; border: 1px solid @danger; border-radius: 12px; }
QFrame#dupBar { background: @accent_tint; border: 1px solid @accent; border-radius: 12px; }
QFrame#findBar { background: @elev; border: 1px solid @hairline; border-radius: 12px; }
QFrame#focusBanner { background: @accent_tint; border: 1px solid @accent; border-radius: 12px; }
QFrame#paletteBox, QFrame#suggestBox, QFrame#toastBox {
  background: @elev; border: 1px solid @hairline; border-radius: 14px;
}
QDialog#palette, QDialog#suggest { background: transparent; }
QFrame#hairline { background: @hairline; max-height: 1px; min-height: 1px; border: none; }

/* ---------- menus ---------- */
QMenu {
  background: @elev; border: 1px solid @hairline; border-radius: 12px; padding: 6px;
}
QMenu::item { padding: 7px 26px 7px 10px; border-radius: 7px; color: @ink1; margin: 1px 0; }
QMenu::item:selected { background: @hover; }
QMenu::item:disabled { color: @ink3; }
QMenu::separator { height: 1px; background: @hairline; margin: 5px 8px; }
QMenu::icon { padding-left: 6px; }
QMenu::indicator { width: 14px; height: 14px; padding-left: 8px; }

/* ---------- lists ---------- */
QListWidget#panelList, QListWidget#paletteList, QListWidget#settingsNav {
  background: transparent; border: none; outline: none;
}
QListWidget#panelList::item, QListWidget#paletteList::item { border-radius: 8px; }
QListWidget#settingsNav::item {
  padding: 9px 12px; border-radius: 8px; color: @ink2; margin: 1px 0;
}
QListWidget#settingsNav::item:hover { background: @hover; }
QListWidget#settingsNav::item:selected { background: @accent_tint; color: @accent; font-weight: 600; }
QListWidget { background: @surface; border: 1px solid @hairline; border-radius: 8px; outline: none; }
QListWidget::item { padding: 6px 8px; border-radius: 6px; }
QListWidget::item:selected { background: @accent_tint; color: @ink1; }
QListWidget::item:hover { background: @hover; }

QProgressBar {
  background: @field; border: none; border-radius: 3px; max-height: 6px;
  text-align: center; font-size: 0px;
}
QProgressBar::chunk { background: @accent; border-radius: 3px; }

QTabWidget::pane { border: 1px solid @hairline; border-radius: 8px; background: @surface; }
QTabBar::tab { padding: 6px 16px; color: @ink2; border: none; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: @ink1; border-bottom: 2px solid @accent; }

QScrollBar:vertical { width: 12px; background: transparent; margin: 0; }
QScrollBar::handle:vertical {
  background: rgba(128,138,160,0.32); border-radius: 4px; min-height: 28px; margin: 2px 3px;
}
QScrollBar::handle:vertical:hover { background: rgba(128,138,160,0.55); }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QScrollBar:horizontal { height: 0; }

QSlider::groove:horizontal { height: 4px; background: @field_hover; border-radius: 2px; }
QSlider::sub-page:horizontal { background: @accent; border-radius: 2px; }
QSlider::handle:horizontal {
  background: @surface; border: 2px solid @accent; width: 12px; height: 12px;
  margin: -6px 0; border-radius: 8px;
}

QPushButton[seg="true"] {
  background: transparent; border: none; border-radius: 7px; padding: 6px 14px;
  color: @ink2; font-weight: 500;
}
QPushButton[seg="true"]:hover { color: @ink1; background: transparent; }
QPushButton[seg="true"]:checked { background: @surface; color: @ink1; font-weight: 600; }
QFrame#segFrame { background: @field; border-radius: 10px; }
QWidget#settingsPage { background: transparent; }
QFrame#settingsSide { background: @shelf; border-right: 1px solid @hairline; }
QFrame#swatch { border-radius: 11px; border: 2px solid transparent; }
QFrame#statTile { background: @field; border-radius: 10px; }

QLabel#statusBubble {
  background: @elev; border: 1px solid @hairline; border-top-right-radius: 8px;
  padding: 4px 10px; color: @ink2; font-size: 12px;
}
QFrame#devDock { background: @surface; border-top: 1px solid @hairline; }
QToolButton#pill { text-align: left; }

QToolTip {
  background: #1B1F29; color: #F2F4F8; border: 1px solid #2E3441; border-radius: 6px;
  padding: 5px 8px; font-size: 12px;
}
"""


def build_qss() -> str:
    qss = _QSS
    for key in sorted(TOKENS, key=len, reverse=True):
        qss = qss.replace("@" + key, str(TOKENS[key]))
    return qss


# Icons the rest of the codebase relied on being registered from here.
for _name, _body in {
    "download": '<path d="M12 4v10"/><path d="M8 10l4 4 4-4"/><path d="M5 19h14"/>',
    "moon": '<path d="M19 14.5A7.5 7.5 0 0 1 10.5 6 7.5 7.5 0 1 0 19 14.5z"/>',
    "volume": '<path d="M4 10v4h3l4 3V7L7 10H4z"/><path d="M15 9a4 4 0 0 1 0 6"/>',
    "volume_off": '<path d="M4 10v4h3l4 3V7L7 10H4z"/><path d="M16 9l4 6M20 9l-4 6"/>',
}.items():
    _icons.BODIES.setdefault(_name, _body)
