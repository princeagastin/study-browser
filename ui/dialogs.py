"""Dialogs: quick-app editor, tunnel config, settings, shortcuts, about."""
import os

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QRadioButton, QListWidget,
                               QListWidgetItem, QDialogButtonBox, QCheckBox,
                               QButtonGroup, QMessageBox, QComboBox,
                               QSpinBox, QWidget, QPushButton, QFrame,
                               QStackedWidget, QScrollArea, QTextEdit, QSizePolicy,
                               QFileDialog, QGridLayout)

from ui import brand, icons
from ui.theme import (TOKENS as T, ACCENTS, current_accent)
from ui.widgets import Switch, Segmented, qcolor, caption

EMOJI_CHOICES = ["📚", "🎓", "🧠", "▶️", "🎵", "🎮", "📰", "📧", "💻", "☁️",
                 "🌐", "🗺️", "📝", "📊", "🧪", "⏰", "📅", "💬", "🎬", "🛒",
                 "🏠", "💡", "☕", "🔒", "⭐", "🔧", "📷", "✈️", "🍔", "💰"]


class QuickAppDialog(QDialog):
    def __init__(self, parent=None, name="", url="", icon_field="letter",
                 favicon_available=False):
        super().__init__(parent)
        self.setWindowTitle("Quick App")
        self.resize(380, 470)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addWidget(QLabel("Name"))
        self.name = QLineEdit(name, self)
        lay.addWidget(self.name)
        lay.addWidget(QLabel("URL"))
        self.url = QLineEdit(url, self)
        self.url.setPlaceholderText("https://…")
        lay.addWidget(self.url)
        lay.addWidget(QLabel("Icon"))
        self.group = QButtonGroup(self)
        self.r_emoji = QRadioButton("Emoji", self)
        self.r_letter = QRadioButton("Letter tile", self)
        self.r_fav = QCheckBox("Use site favicon (captured from open tab)",
                               self)
        self.r_fav.setEnabled(favicon_available)
        self.group.addButton(self.r_emoji, 1)
        self.group.addButton(self.r_letter, 2)
        self.group.addButton(self.r_fav, 3)
        row = QHBoxLayout()
        row.addWidget(self.r_emoji)
        row.addWidget(self.r_letter)
        lay.addLayout(row)
        lay.addWidget(self.r_fav)
        self.grid = QListWidget(self)
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setIconSize(QSize(24, 24))
        self.grid.setFixedHeight(150)
        for char in EMOJI_CHOICES:
            item = QListWidgetItem(char)
            item.setData(Qt.ItemDataRole.UserRole, char)
            self.grid.addItem(item)
        lay.addWidget(self.grid)
        if icon_field.startswith("emoji:"):
            self.r_emoji.setChecked(True)
            for i in range(self.grid.count()):
                if self.grid.item(i).data(Qt.ItemDataRole.UserRole) == \
                        icon_field[6:]:
                    self.grid.setCurrentRow(i)
        elif icon_field.startswith("file:"):
            self.r_fav.setChecked(True)
        else:
            self.r_letter.setChecked(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def result_icon(self, favicon_path=None):
        if self.r_fav.isChecked() and favicon_path:
            return "file:" + favicon_path
        if self.r_emoji.isChecked():
            item = self.grid.currentItem()
            char = item.data(Qt.ItemDataRole.UserRole) if item else "🌐"
            return "emoji:" + char
        return "letter"


class VpnDialog(QDialog):
    def __init__(self, parent=None, proxy_type="socks5", host="127.0.0.1",
                 port=9050):
        super().__init__(parent)
        self.setWindowTitle("Custom Tunnel (proxy architecture)")
        self.resize(340, 200)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addWidget(QLabel(
            f"<span style='color:#5C6470;font-size:12px'>{brand.NAME} routes "
            "all WebEngine traffic through a local tunnel endpoint "
            "(Tor, WireGuard-socks, corporate proxy…).</span>"))
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type"))
        self.type_box = QComboBox(self)
        self.type_box.addItems(["socks5", "http"])
        self.type_box.setCurrentText(proxy_type)
        type_row.addWidget(self.type_box, 1)
        lay.addLayout(type_row)
        host_row = QHBoxLayout()
        host_row.addWidget(QLabel("Host"))
        self.host_edit = QLineEdit(host, self)
        host_row.addWidget(self.host_edit, 1)
        host_row.addWidget(QLabel("Port"))
        self.port_spin = QSpinBox(self)
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(port)
        host_row.addWidget(self.port_spin)
        lay.addLayout(host_row)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)



# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
class _Page(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setAutoFillBackground(False)
        self.body = QWidget()
        self.body.setObjectName("settingsPage")
        self.body.setAutoFillBackground(False)
        self.v = QVBoxLayout(self.body)
        self.v.setContentsMargins(28, 22, 28, 28)
        self.v.setSpacing(4)
        self.setWidget(self.body)

    def title(self, text, sub=""):
        lab = QLabel(text)
        lab.setObjectName("h1")
        self.v.addWidget(lab)
        if sub:
            s = QLabel(sub)
            s.setObjectName("muted")
            s.setWordWrap(True)
            self.v.addWidget(s)
        self.v.addSpacing(10)

    def group(self, text):
        self.v.addSpacing(14)
        self.v.addWidget(caption(text))
        self.v.addSpacing(4)

    def row(self, title, desc, widget):
        card = QFrame()
        card.setObjectName("cardField")
        h = QHBoxLayout(card)
        h.setContentsMargins(14, 11, 14, 11)
        h.setSpacing(14)
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet("font-weight:600;")
        col.addWidget(t)
        if desc:
            d = QLabel(desc)
            d.setObjectName("faint")
            d.setWordWrap(True)
            col.addWidget(d)
        h.addLayout(col, 1)
        widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        h.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        self.v.addWidget(card)
        self.v.addSpacing(6)
        return card

    def end(self):
        self.v.addStretch(1)


class SettingsDialog(QDialog):
    """Sidebar settings. Every change is persisted *and applied* immediately."""
    changed = Signal(str)

    def __init__(self, storage, parent=None, on_clear_cookies=None,
                 on_clear_cache=None, start_page=0):
        super().__init__(parent)
        self.storage = storage
        self._clear_cookies = on_clear_cookies
        self._clear_cache = on_clear_cache
        self.setWindowTitle(f"{brand.NAME} Settings")
        self.resize(820, 600)
        self.setMinimumSize(700, 500)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = QFrame()
        side.setObjectName("settingsSide")
        side.setFixedWidth(210)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(12, 18, 12, 14)
        head = QLabel(f"<b style='font-size:15px'>Settings</b>")
        sv.addWidget(head)
        sv.addSpacing(8)
        self.nav = QListWidget()
        self.nav.setObjectName("settingsNav")
        sv.addWidget(self.nav, 1)
        self.stack = QStackedWidget()
        root.addWidget(side)
        root.addWidget(self.stack, 1)

        for name, icon, builder in (
                ("General", "home", self._general),
                ("Appearance", "palette", self._appearance),
                ("Privacy & security", "shield", self._privacy),
                ("Focus", "focus", self._focus),
                ("Data & export", "export", self._data),
                ("About", "sparkle", self._about)):
            item = QListWidgetItem(icons.icon(icon, 16, T["ink2"]), name)
            self.nav.addItem(item)
            self.stack.addWidget(builder())
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(start_page)

    # ------------------------------------------------------------ helpers
    def _get(self, key, default=""):
        return self.storage.get_setting(key, default)

    def _set(self, key, value):
        self.storage.set_setting(key, value)
        self.changed.emit(key)

    def _switch(self, key, default="0"):
        sw = Switch(self._get(key, default) == "1")
        sw.toggled.connect(lambda on, k=key: self._set(k, "1" if on else "0"))
        return sw

    def _combo(self, key, options, default):
        box = QComboBox()
        box.setMinimumWidth(170)
        cur = self._get(key, default)
        for value, label in options:
            box.addItem(label, value)
        idx = box.findData(cur)
        box.setCurrentIndex(max(0, idx))
        box.currentIndexChanged.connect(
            lambda _i, k=key, b=box: self._set(k, b.currentData()))
        return box

    # ------------------------------------------------------------ pages
    def _general(self):
        from browser.omni import ENGINES
        p = _Page()
        p.title("General", "How the browser starts, searches and downloads.")
        p.group("Search")
        p.row("Search engine", "Used for the address bar and start page.",
              self._combo("search_engine",
                          [(k, v[0]) for k, v in ENGINES.items()], "duckduckgo"))
        p.row("Search suggestions", "Send what you type to your search engine "
              "for live suggestions. Never used in private tabs.",
              self._switch("search_suggestions", "1"))
        p.row("Inline autocomplete", "Complete site names in the address bar as you type.",
              self._switch("inline_complete", "1"))
        p.group("Startup & tabs")
        p.row("Restore tabs on startup", "Reopen the tabs from your last session.",
              self._switch("restore_on_start", "0"))
        p.row("Warn about duplicate tabs", "Offer to switch to a tab that is already open.",
              self._switch("dup_warn", "1"))
        p.row("Sleep inactive tabs", "Free memory by discarding background tabs "
              "you haven't used for a while. Audio tabs are never slept.",
              self._combo("sleep_tabs_min",
                          [("0", "Never"), ("5", "After 5 min"), ("15", "After 15 min"),
                           ("30", "After 30 min"), ("60", "After 1 hour")], "0"))
        p.row("Show bookmarks bar", "Your saved pages, one click away under the address bar.",
              self._switch("bookmarks_bar", "0"))
        p.group("Downloads")
        self.dl_label = QLabel(self._get("download_dir", "") or "System default")
        self.dl_label.setObjectName("faint")
        pick = QPushButton("Change…")
        pick.clicked.connect(self._pick_dir)
        box = QWidget()
        bl = QHBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(pick)
        p.row("Download location", "", box)
        p.v.insertWidget(p.v.count() - 2, self.dl_label)
        p.row("Ask where to save each file", "", self._switch("ask_download", "0"))
        p.end()
        return p

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Download folder",
                                             self._get("download_dir", "") or os.path.expanduser("~"))
        if d:
            self.dl_label.setText(d)
            self._set("download_dir", d)

    def _appearance(self):
        p = _Page()
        p.title("Appearance", "Make it yours. Changes apply instantly.")
        p.group("Theme")
        seg = Segmented([("light", "Light"), ("dark", "Dark"), ("system", "System")],
                        self._get("theme", "light"))
        seg.changed.connect(lambda v: self._set("theme", v))
        p.row("Colour scheme", "System follows your operating-system setting.", seg)
        p.group("Accent colour")
        wrap = QWidget()
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(8)
        self._swatches = {}
        for name, vals in ACCENTS.items():
            b = QPushButton()
            b.setFixedSize(26, 26)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(name.title())
            b.clicked.connect(lambda _c=False, n=name: self._pick_accent(n))
            self._swatches[name] = (b, vals[0])
            wl.addWidget(b)
        self._paint_swatches()
        p.row("Accent", "Buttons, highlights, focus rings and the start page.", wrap)
        p.group("Web content")
        p.row("Dark mode for websites", "Ask sites to render dark where possible. "
              "Takes effect on the next page load.", self._switch("force_dark_pages", "0"))
        p.row("Default page zoom", "Per-site zoom is remembered separately.",
              self._combo("default_zoom",
                          [(str(z), f"{z}%") for z in (80, 90, 100, 110, 125, 150, 175)], "100"))
        p.end()
        return p

    def _pick_accent(self, name):
        self._set("accent", name)
        self._paint_swatches()

    def _paint_swatches(self):
        cur = self._get("accent", "blue")
        for name, (btn, col) in self._swatches.items():
            ring = T["ink1"] if name == cur else "transparent"
            btn.setStyleSheet(f"QPushButton{{background:{col};border-radius:13px;"
                              f"border:2px solid {ring};}}")

    def _privacy(self):
        p = _Page()
        p.title("Privacy & security", "Folio Shield blocks trackers and flags suspicious sites.")
        p.group("Shield")
        seg = Segmented([("off", "Off"), ("standard", "Standard"), ("strict", "Strict")],
                        self._get("shield_mode", "standard"))
        seg.changed.connect(lambda v: self._set("shield_mode", v))
        p.row("Tracker protection", "Standard blocks ad networks. Strict also blocks analytics, "
              "cross-site tracking and third-party cookies.", seg)
        p.row("Send Global Privacy Control", "Tells sites not to sell or share your data "
              "(Sec-GPC and Do-Not-Track headers).", self._switch("send_gpc", "1"))
        p.row("HTTPS-only mode", "Upgrade every http:// address to https:// "
              "(local network addresses are exempt).", self._switch("https_only", "0"))
        p.group("Browsing")
        p.row("Block autoplay", "Media needs a click before it plays.",
              self._switch("block_autoplay", "1"))
        p.row("Spell check", "Underline mistakes in text fields.", self._switch("spellcheck", "1"))
        p.group("Site permissions")
        self.perm_list = QListWidget()
        self.perm_list.setFixedHeight(130)
        self._load_perms()
        p.v.addWidget(self.perm_list)
        r = QHBoxLayout()
        a = QPushButton("Forget selected")
        a.clicked.connect(self._forget_perm)
        b = QPushButton("Forget all")
        b.clicked.connect(self._clear_perms)
        r.addWidget(a)
        r.addWidget(b)
        r.addStretch(1)
        p.v.addLayout(r)
        p.end()
        return p

    def _load_perms(self):
        self.perm_list.clear()
        for row in self.storage.list_permissions():
            it = QListWidgetItem(f"{row['host']}  —  {row['ptype']}  "
                                 f"({'allowed' if row['granted'] else 'blocked'})")
            it.setData(Qt.ItemDataRole.UserRole, (row["host"], row["ptype"]))
            self.perm_list.addItem(it)
        if not self.perm_list.count():
            it = QListWidgetItem("No saved permissions")
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.perm_list.addItem(it)

    def _forget_perm(self):
        item = self.perm_list.currentItem()
        data = item.data(Qt.ItemDataRole.UserRole) if item else None
        if data:
            self.storage.delete_permission(*data)
            self._load_perms()

    def _clear_perms(self):
        self.storage.clear_permissions()
        self._load_perms()

    def _focus(self):
        from ui.focus import DEFAULT_BLOCKLIST
        p = _Page()
        p.title("Focus", "Pomodoro-style sessions that keep you off distracting sites.")
        p.group("Sessions")
        p.row("Block distracting sites during focus", "Navigation to blocked sites is "
              "stopped until the session ends.", self._switch("focus_block", "1"))
        p.group("Blocked sites")
        self.block_edit = QTextEdit()
        self.block_edit.setFixedHeight(190)
        self.block_edit.setPlainText(self._get("focus_blocklist", "") or
                                     "\n".join(DEFAULT_BLOCKLIST))
        self.block_edit.textChanged.connect(
            lambda: self._set("focus_blocklist", self.block_edit.toPlainText()))
        p.v.addWidget(self.block_edit)
        hint = QLabel("One domain per line. Subdomains are included automatically.")
        hint.setObjectName("faint")
        p.v.addWidget(hint)
        p.end()
        return p

    def _data(self):
        p = _Page()
        p.title("Data & export", "Your data is stored locally and is yours to take with you.")
        p.group("Export")
        for title, desc, label, fn in (
                ("Notes", "All notes as a single Markdown file, with sources.",
                 "Export .md", self._export_notes),
                ("Saved pages", "A standard bookmarks file importable by any browser.",
                 "Export .html", self._export_saved)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            p.row(title, desc, b)
        p.group("Clear data")
        for title, desc, label, fn in (
                ("Browsing history", "Pages you've visited.", "Clear…", self._clear_history),
                ("Cookies & site data", "Signs you out of most sites.", "Clear…", self._do_cookies),
                ("Cache", "Cached images and files.", "Clear…", self._do_cache),
                ("Download list", "Removes entries, not the files.", "Clear", self._clear_dl)):
            b = QPushButton(label)
            b.setProperty("danger", "true")
            b.clicked.connect(fn)
            p.row(title, desc, b)
        p.end()
        return p

    def _export_notes(self):
        from ui.panels import save_text_file
        save_text_file(self, "Export notes", "folio-notes.md",
                       self.storage.export_notes_markdown(), "Markdown (*.md)")

    def _export_saved(self):
        from ui.panels import save_text_file
        save_text_file(self, "Export saved pages", "folio-bookmarks.html",
                       self.storage.export_saved_html(), "HTML (*.html)")

    def _clear_history(self):
        if confirm(self, "Clear history", "Delete all browsing history?"):
            self.storage.clear_history()
            self.changed.emit("history")

    def _do_cookies(self):
        if self._clear_cookies and confirm(self, "Clear cookies",
                                           "Delete all cookies and site data? You'll be signed out of sites."):
            self._clear_cookies()

    def _do_cache(self):
        if self._clear_cache and confirm(self, "Clear cache", "Delete the HTTP cache?"):
            self._clear_cache()

    def _clear_dl(self):
        self.storage.clear_downloads()
        self.changed.emit("downloads")

    def _about(self):
        p = _Page()
        p.title(brand.NAME, brand.TAGLINE)
        info = QLabel(
            f"<span style='color:{T['ink2']}'>Version 2.0 · Qt WebEngine · PySide6 · SQLite<br><br>"
            "Browser, research workspace, notes, focus timer, reader mode, "
            "privacy shield and tunnel — in one window.</span>")
        info.setWordWrap(True)
        p.v.addWidget(info)
        p.v.addSpacing(10)
        b = QPushButton("Keyboard shortcuts")
        b.clicked.connect(lambda: ShortcutsDialog(self).exec())
        p.v.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        p.end()
        return p


SHORTCUTS = [
    ("Tabs", [
        ("Ctrl+T", "New tab"), ("Ctrl+Shift+P", "New private tab"),
        ("Ctrl+W", "Close tab"), ("Ctrl+Shift+T", "Reopen closed tab"),
        ("Ctrl+Tab / Ctrl+Shift+Tab", "Next / previous tab"),
        ("Ctrl+1 … 9", "Jump to tab"), ("Ctrl+Shift+A", "Search open tabs")]),
    ("Navigate", [
        ("Ctrl+L", "Focus address bar"), ("Alt+Enter", "Open address in new tab"),
        ("Alt+← / Alt+→", "Back / forward"), ("Ctrl+R / F5", "Reload"),
        ("Ctrl+K", "Command palette")]),
    ("Page", [
        ("Ctrl+F", "Find in page"), ("Ctrl+D", "Save / unsave page"),
        ("Ctrl+Alt+R", "Reader mode"), ("Ctrl+U", "View source"),
        ("Ctrl+P", "Save page as PDF"), ("F12", "Developer tools"),
        ("Ctrl++ / Ctrl+- / Ctrl+0", "Zoom in / out / reset"), ("F11", "Full screen")]),
    ("Library", [
        ("Ctrl+Shift+B", "Saved pages"), ("Ctrl+H", "History"),
        ("Ctrl+J", "Downloads"), ("Ctrl+Alt+N", "Notes"),
        ("Ctrl+Shift+F", "Start / stop focus session"), ("Ctrl+,", "Settings")]),
]


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(520, 560)
        lay = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        body = QWidget()
        body.setAutoFillBackground(False)
        g = QGridLayout(body)
        g.setHorizontalSpacing(24)
        g.setVerticalSpacing(7)
        r = 0
        for section, rows in SHORTCUTS:
            g.addWidget(caption(section), r, 0, 1, 2)
            r += 1
            for keys, desc in rows:
                k = QLabel(keys)
                k.setStyleSheet(f"font-family:{T['mono']};font-size:12px;font-weight:600;")
                d = QLabel(desc)
                d.setObjectName("muted")
                g.addWidget(k, r, 0)
                g.addWidget(d, r, 1)
                r += 1
            g.setRowMinimumHeight(r, 12)
            r += 1
        g.setColumnStretch(1, 1)
        scroll.setWidget(body)
        lay.addWidget(scroll)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {brand.NAME}")
        self.setFixedSize(420, 250)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(14)
        logo = QLabel(self)
        logo.setPixmap(brand.app_icon().pixmap(46, 46))
        texts = QLabel(
            f"<b style='font-size:22px;letter-spacing:-.02em'>{brand.NAME}"
            f"<span style='color:{T['accent']}'>.</span></b>"
            f"<br><span style='color:{T['ink2']};font-size:13px'>"
            f"{brand.TAGLINE}</span>", self)
        head.addWidget(logo)
        head.addWidget(texts, 1)
        lay.addLayout(head)
        lay.addWidget(QLabel(
            f"<span style='color:{T['ink3']};font-size:12px'>"
            "Version 2.0 · Qt WebEngine · PySide6 · SQLite<br>"
            "Browser · Research Workspace · Focus · Reader · Shield · Tunnel"
            "</span>", self))
        lay.addStretch(1)


def confirm(parent, title, text):
    return QMessageBox.question(
        parent, title, text,
        QMessageBox.StandardButton.Yes |
        QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
