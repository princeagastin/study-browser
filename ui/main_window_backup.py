import os
import time
import traceback
from urllib.parse import unquote
from ui.study_panel import StudyPanel

from PySide6.QtCore import Qt, QUrl, QTimer, QRect, QStandardPaths
from PySide6.QtGui import QShortcut, QKeySequence, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QStackedWidget, QFileDialog, QMessageBox,
                               QApplication, QInputDialog, QDialog, QLineEdit,
                               QLabel, QDialogButtonBox, QFormLayout)

from browser import omni
from browser.engine import HOME_URL
from browser.session import SessionManager
from security.models import PrivacyMode, Verdict, VpnConfig, VpnMode
from security.privacy import PrivacyManager
from security.safety_engine import SafetyEngine
from security.vpn import VpnManager
from security.warnings import SecurityBanner, SiteInfoDialog, verdict_color
from ui import icons, dialogs, brand, theme
from ui import reader as reader_mod
from ui.command_palette import PaletteDialog, PaletteItem
from ui.downloads import DownloadManager, DownloadsPanel, reveal
from ui.focus import FocusManager, fmt as fmt_clock
from ui.menus import build_overflow_menu, popup_under_menu, MenuContext
from ui.motion import ClickMotion
from ui.overlays import (FindBar, DuplicateBar, StatusBubble, BookmarksBar,
                         DevToolsDock)
from ui.panels import PanelHost, SavedPanel, HistoryPanel, NotesPanel, PANEL_W
from ui.quick_apps import QuickAppsRail
from ui.suggest import SuggestController, SuggestionProvider
from ui.tabs import TabManager, TabStrip
from ui.theme import TOKENS as T, build_qss
from ui.topbar import TopBar
from ui.widgets import Toast, RoundMenu

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_READ_CHECK_JS = ("(function(){var p=document.querySelectorAll('p').length;"
                  "return p>=5&&(document.body?document.body.innerText.length:0)>2500;})()")


class AuthDialog(QDialog):
    def __init__(self, parent, host, realm):
        super().__init__(parent)
        self.setWindowTitle("Sign in")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        lab = QLabel(f"<b>{host}</b> requires a username and password."
                     + (f"<br><span style='color:{T['ink3']}'>{realm}</span>" if realm else ""))
        lab.setWordWrap(True)
        lay.addWidget(lab)
        form = QFormLayout()
        self.user = QLineEdit(self)
        self.pw = QLineEdit(self)
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Username", self.user)
        form.addRow("Password", self.pw)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel, self)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


class MainWindow(QMainWindow):
    def __init__(self, storage, profiles):
        super().__init__()
        self.storage = storage
        self.profiles = profiles
        self.session = SessionManager()
        self.safety = SafetyEngine(self)
        self.privacy = PrivacyManager(self)
        self.vpn = VpnManager(self)
        self.focus = FocusManager(storage, self)
        self.downloads = DownloadManager(storage, self)
        self.downloads.parent_window = self
        self._fullscreen = False
        self._web_fullscreen = False
        self._dismissed_hosts = set()
        self._reader_expect = {}
        self._dup_tab_id = None
        self._dup_other_id = None
        self._load_prefs()
        self._resolve_theme()
        # Theme must be live *before* any widget is built so icons and the
        # stylesheet agree with the saved preference.
        icons.clear_cache()
        QApplication.instance().setStyleSheet(build_qss())
        self.setWindowTitle(brand.NAME)
        self.resize(1360, 860)

        self.motion = ClickMotion(self)
        self.motion.install(QApplication.instance())

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.strip = TabStrip(central)
        root.addWidget(self.strip)
        self.topbar = TopBar(central)
        root.addWidget(self.topbar)
        self.bookmarks_bar = BookmarksBar(storage, central)
        self.bookmarks_bar.open_url.connect(lambda u, _n: self._open_from_panel(u))
        root.addWidget(self.bookmarks_bar)

        self.content = QWidget(central)
        crow = QHBoxLayout(self.content)
        crow.setContentsMargins(0, 0, 0, 0)
        crow.setSpacing(0)
        self.rail = QuickAppsRail(storage, self.content)
        crow.addWidget(self.rail)
        self.web_area = QWidget(self.content)
        wlay = QVBoxLayout(self.web_area)
        wlay.setContentsMargins(0, 0, 0, 0)
        wlay.setSpacing(0)
        self.stacked = QStackedWidget(self.web_area)
        wlay.addWidget(self.stacked, 1)
        self.devtools = DevToolsDock(self.web_area)
        self.devtools.closed.connect(self.toggle_devtools)
        self.devtools.hide()
        wlay.addWidget(self.devtools)
        crow.addWidget(self.web_area, 1)

        # AI Study Assistant
        self.study_panel = StudyPanel(self.content)
        self.study_panel.hide()
        crow.addWidget(self.study_panel)
        self.study_panel.request_close.connect(self.study_panel.hide)

        root.addWidget(self.content, 1)

        self.banner = SecurityBanner(self.web_area)
        self.banner.proceed_clicked.connect(lambda: self._dismiss_banner(True))
        self.banner.dismiss_clicked.connect(self._back_to_safety)
        self.dup_bar = DuplicateBar(self.web_area)
        self.dup_bar.switch_btn.clicked.connect(self._dup_switch)
        self.dup_bar.anyway_btn.clicked.connect(lambda _c=False: self.dup_bar.hide())
        self.panels = PanelHost(self.web_area)
        self._build_panels()
        self.find_bar = FindBar(self.web_area)
        self.find_bar.hide()
        self.status = StatusBubble(self.web_area)
        self.toast = Toast(self.web_area)

        self.manager = TabManager(self.stacked, self.strip, profiles, storage,
                                  self.session, self._page_action)
        self.manager.dark_get = lambda: theme.is_dark()
        self.manager.current_changed.connect(self._sync_chrome)
        self.manager.url_changed.connect(self._on_url)
        self.manager.title_changed.connect(self._on_title)
        self.manager.loading_changed.connect(self.topbar.set_loading)
        self.manager.progress_changed.connect(self.topbar.progress.set_value)
        self.manager.icon_changed.connect(self._on_icon)
        self.manager.note_from_selection.connect(self._note_from_selection)
        self.manager.search_selection.connect(self._search_selection)
        self.manager.duplicate_detected.connect(self._on_duplicate)
        self.manager.link_hovered.connect(self.status.show_text)
        self.manager.fullscreen_requested.connect(self._on_web_fullscreen)
        self.manager.cert_error.connect(self._on_cert_error)
        self.manager.auth_needed.connect(self._on_auth)
        self.manager.open_link.connect(self._open_link)
        self.manager.save_link.connect(self._save_link)
        self.manager.page_loaded.connect(self._on_page_loaded)
        self.strip.chip_ctx.connect(self._tab_context)
        self.strip.chip_audio.connect(self.manager.toggle_mute)

        for prof in profiles.all_profiles():
            prof.downloadRequested.connect(self.downloads.handle)
        self.downloads.activity.connect(self.topbar.set_download_activity)
        self.downloads.started.connect(self._dl_started)
        self.downloads.finished.connect(self._dl_finished)

        # browsing policy hooks (called from StudyPage on the GUI thread)
        profiles.policy.focus_blocked = self.focus.is_blocked
        profiles.policy.on_focus_block = self._on_focus_block
        self.focus.tick.connect(self._focus_tick)
        self.focus.state_changed.connect(self._focus_state)
        self.focus.session_finished.connect(self._focus_done)

        self._wire_topbar()
        self._wire_rail()
        self._shortcuts()

        self.provider = SuggestionProvider(
            storage, self._tabs_for_suggest, lambda: self._engine, self)
        self.suggest = SuggestController(
            self.topbar.omni, self.provider,
            lambda: bool(self.manager.current and self.manager.current.private),
            lambda: [r["url"].split("://", 1)[-1].split("/", 1)[0]
                     for r in storage.top_hosts(10)], self)
        self.suggest.navigate.connect(self._navigate)
        self.suggest.switch_tab.connect(self.manager.activate)
        self.suggest.copy_text.connect(self._copy_text)
        self.topbar.omni.edit.dismiss.connect(self._omni_escape)

        self.palette = PaletteDialog(self)
        self.palette.provider = self._palette_items
        self.palette.engine_key = lambda: self._engine
        self.palette.go_cb = lambda u: self._navigate(u)
        self.palette.copy_cb = self._copy_text

        self._apply_all_settings(initial=True)

        self._autosave = QTimer(self)
        self._autosave.setInterval(20000)
        self._autosave.timeout.connect(self._save_session_now)
        self._autosave.start()
        self._shield_timer = QTimer(self)
        self._shield_timer.setInterval(1500)
        self._shield_timer.timeout.connect(self._refresh_shield_badge)
        self._shield_timer.start()

        QGuiApplication.styleHints().colorSchemeChanged.connect(
            lambda *_: self._on_system_scheme())

        self.manager.new_tab()
        QTimer.singleShot(0, self._sync_chrome)
        if storage.get_setting("restore_on_start", "0") == "1":
            QTimer.singleShot(300, self._restore_session)

    # ------------------------------------------------------------ prefs
    def _load_prefs(self):
        g = self.storage.get_setting
        self._shield_mode = g("shield_mode", "standard")
        self._engine = g("search_engine", omni.DEFAULT_ENGINE)
        if self._engine not in omni.ENGINES:
            self._engine = omni.DEFAULT_ENGINE
        self._dup_warn = g("dup_warn", "1") == "1"
        self._theme_pref = g("theme", "light")

    @property
    def _search_url(self):
        return omni.engine_url(self._engine)

    def _system_dark(self):
        try:
            return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            return False

    def _resolve_theme(self):
        pref = self._theme_pref
        dark = self._system_dark() if pref == "system" else pref == "dark"
        theme.set_mode("dark" if dark else "light")
        theme.set_accent(self.storage.get_setting("accent", "blue"))

    def _on_system_scheme(self):
        if self._theme_pref == "system":
            self._apply_theme()

    def _apply_all_settings(self, initial=False, key=None):
        g = self.storage.get_setting
        self._load_prefs()
        self.profiles.apply_settings(self.storage)
        self.privacy.apply(self.profiles, PrivacyMode(self._shield_mode),
                           send_gpc=g("send_gpc", "1") == "1")
        self.privacy.set_allow_hosts(self.storage.shield_off_hosts())
        self.manager.sleep_after_min = int(g("sleep_tabs_min", "0") or 0)
        self.provider.remote_enabled = g("search_suggestions", "1") == "1"
        self.suggest.inline_enabled = g("inline_complete", "1") == "1"
        self.focus.reload_blocklist()
        self.bookmarks_bar.setVisible(g("bookmarks_bar", "0") == "1")
        self.topbar.omni.edit.setPlaceholderText(
            f"Search {omni.engine_label(self._engine)} or enter address")
        if key in ("theme", "accent") or (initial and False):
            self._apply_theme()
        if key == "default_zoom":
            tab = self.manager.current
            if tab:
                self._apply_zoom(tab)

    def _on_setting_changed(self, key):
        if key in ("history",):
            self.history_panel.reload()
            return
        if key == "downloads":
            self.downloads_panel.reload()
            return
        self._apply_all_settings(key=key)
        if key == "search_engine":
            self._reload_home_tabs()

    # ------------------------------------------------------------ panels
    def _build_panels(self):
        s = self.storage
        self.saved_panel = SavedPanel(s, self.panels)
        self.history_panel = HistoryPanel(s, self.panels)
        self.notes_panel = NotesPanel(s, self.panels)
        self.downloads_panel = DownloadsPanel(s, self.downloads, self.panels)
        for panel in (self.saved_panel, self.history_panel, self.notes_panel,
                      self.downloads_panel):
            panel.open_url.connect(self._open_from_panel)
            panel.hide()

    def _rebuild_panels(self):
        reopen = self.panels.current
        name = None
        for attr in ("saved_panel", "history_panel", "notes_panel", "downloads_panel"):
            if getattr(self, attr) is reopen and self.panels.isVisible():
                name = attr
        try:
            self.notes_panel._flush()
        except Exception:
            pass
        old = [self.saved_panel, self.history_panel, self.notes_panel,
               self.downloads_panel]
        self.panels.hide()
        self.panels.current = None
        for p in old:
            p.hide()
            p.setParent(None)
            p.deleteLater()
        self._build_panels()
        if name:
            self.panels.show_panel(getattr(self, name))

    # ------------------------------------------------------------ wiring
    def _wire_topbar(self):
        tb = self.topbar
        tb.back_clicked.connect(lambda: self._page().triggerAction(
            self._page().WebAction.Back) if self._page() else None)
        tb.forward_clicked.connect(lambda: self._page().triggerAction(
            self._page().WebAction.Forward) if self._page() else None)
        tb.reload_stop_clicked.connect(self._reload_stop)
        tb.home_clicked.connect(lambda: self.manager.load(self.manager.current))
        tb.shield_clicked.connect(self._show_site_info)
        tb.external_clicked.connect(self._external)
        tb.menu_clicked.connect(self._show_menu)
        tb.downloads_clicked.connect(lambda: self.panels.show_panel(self.downloads_panel))
        tb.library_clicked.connect(self._library_menu)
        tb.focus_clicked.connect(self._focus_menu)
        om = tb.omni
        om.star_clicked.connect(self._toggle_save)
        om.site_clicked.connect(self._show_site_info)
        om.reader_clicked.connect(self._toggle_reader)
        om.zoom_clicked.connect(self._zoom_reset)

    def _wire_rail(self):
        self.rail.app_open.connect(lambda url: self.manager.new_tab(url))
        self.rail.manage_requested.connect(self._manage_app)

    def _shortcuts(self):
        def bind(seq, slot):
            QShortcut(QKeySequence(seq), self).activated.connect(slot)
        m = self.manager
        bind("Ctrl+T", lambda: m.new_tab())
        bind("Ctrl+Shift+P", lambda: m.new_tab(private=True))
        bind("Ctrl+W", lambda: m.close_tab(m.current.id) if m.current else None)
        bind("Ctrl+Shift+T", self._reopen)
        bind("Ctrl+Tab", self._next_tab)
        bind("Ctrl+Shift+Tab", self._prev_tab)
        bind("Ctrl+L", self.topbar.omni.focus_edit)
        bind("Alt+D", self.topbar.omni.focus_edit)
        bind("Ctrl+K", lambda: self.palette.open_palette())
        bind("Ctrl+Shift+A", lambda: self.palette.open_palette())
        bind("Ctrl+D", self._toggle_save)
        bind("Ctrl+Shift+B", lambda: self.panels.show_panel(self.saved_panel))
        bind("Ctrl+H", lambda: self.panels.show_panel(self.history_panel))
        bind("Ctrl+J", lambda: self.panels.show_panel(self.downloads_panel))
        bind("Ctrl+Alt+N", self._notes_hotkey)
        bind("Ctrl+Shift+Y", self.toggle_study_panel)
        bind("Ctrl+F", self._show_find)
        bind("Ctrl+R", self._reload_stop)
        bind("F5", self._reload_stop)
        bind("Ctrl+Shift+R", self._hard_reload)
        bind("Ctrl++", self._zoom_in)
        bind("Ctrl+=", self._zoom_in)
        bind("Ctrl+-", self._zoom_out)
        bind("Ctrl+0", self._zoom_reset)
        bind("F11", self._fullscreen_toggle)
        bind("Alt+Left", lambda: self._page().triggerAction(
            self._page().WebAction.Back) if self._page() else None)
        bind("Alt+Right", lambda: self._page().triggerAction(
            self._page().WebAction.Forward) if self._page() else None)
        bind("Alt+Home", lambda: m.load(m.current))
        bind("Ctrl+Alt+R", self._toggle_reader)
        bind("Ctrl+U", self._view_source)
        bind("F12", self.toggle_devtools)
        bind("Ctrl+P", self._save_pdf)
        bind("Ctrl+Shift+F", self._focus_toggle)
        bind("Ctrl+Shift+O", self._toggle_bookmarks_bar)
        bind("Ctrl+,", self._open_settings)
        bind("Escape", self._escape)
        for i in range(1, 10):
            bind(f"Ctrl+{i}", lambda i=i: self._jump_tab(i))

    def _jump_tab(self, number):
        tabs = self.manager.tabs
        if not tabs:
            return
        self.manager.set_current(tabs[-1] if number == 9 else
                                 tabs[number - 1] if len(tabs) >= number else tabs[-1])

    # ------------------------------------------------------------ helpers
    def toggle_study_panel(self):
        """Show/hide the AI Study Assistant for the current tab."""
        if self.study_panel.isVisible():
            self.study_panel.hide()
            return

        tab = self.manager.current
        if tab and tab.view is not None:
            self.study_panel.set_view(tab.view)

        self.study_panel.show()
        self.study_panel.raise_()

    def _page(self):
        return self.manager.current.page if self.manager.current else None

    def _tabs_for_suggest(self):
        return [(t.id, t.title, t.url, t.private) for t in self.manager.tabs
                if t is not self.manager.current]

    def _copy_text(self, text):
        QApplication.clipboard().setText(text)
        self.toast.show_message("Copied to clipboard", "copy")

    def _navigate(self, text, new_tab=False):
        res = omni.resolve(text, self._search_url)
        if res is None:
            return
        tab = self.manager.current
        if new_tab or tab is None:
            self.manager.new_tab(None if res.url == HOME_URL else res.url)
            return
        if res.url == HOME_URL or res.kind == "internal":
            self.manager.load(tab, HOME_URL if res.url == HOME_URL else res.url)
        elif tab.view is not None:
            self._leave_reader(tab)
            tab.view.setUrl(QUrl(res.url))
            tab.view.setFocus()

    def _omni_escape(self):
        om = self.topbar.omni
        om.edit.setText(om._full)
        tab = self.manager.current
        if tab and tab.view is not None:
            tab.view.setFocus()

    def _reload_stop(self):
        tab = self.manager.current
        if not tab or tab.view is None:
            return
        if tab.loading:
            tab.view.stop()
        elif tab.url == HOME_URL:
            self.manager.load(tab)
        else:
            tab.view.reload()

    def _hard_reload(self):
        page = self._page()
        if page:
            page.triggerAction(page.WebAction.ReloadAndBypassCache)

    def _external(self):
        tab = self.manager.current
        if tab and tab.url.startswith("http"):
            QDesktopServices.openUrl(QUrl(tab.url))

    def _open_link(self, url, background, private):
        cur = self.manager.current
        self.manager.new_tab(url, private=private or bool(cur and cur.private),
                             foreground=not background)

    def _save_link(self, url, text):
        self.storage.save_page(url, text.strip() or url)
        self.saved_panel.reload()
        self.bookmarks_bar.refresh()
        self.toast.show_message("Link saved to your library", "star")

    def _open_from_panel(self, url):
        tab = self.manager.current
        if not tab or tab.view is None:
            return
        if url.endswith("\tNEW"):
            self.manager.new_tab(url[:-4])
        else:
            self._leave_reader(tab)
            tab.view.setUrl(QUrl(url))

    # ------------------------------------------------------------ chrome sync
    def _on_icon(self, ic):
        tab = self.manager.current
        if tab and ic is not None and not ic.isNull():
            host = QUrl(tab.url).host()
            if host:
                self.rail.ingest(host, ic.pixmap(64, 64))

    def _on_url(self, url):
        tab = self.manager.current
        if not tab:
            return
        om = self.topbar.omni
        om.set_url(url)
        om.set_saved(self.storage.is_saved(url))
        host = QUrl(url).host()
        self.rail.update_active(host)
        if tab.view is not None:
            h = tab.view.history()
            self.topbar.set_nav_state(h.canGoBack(), h.canGoForward())
            if tab.reader_src and url != tab.reader_src:
                tab.reader_src = None
            self._apply_zoom(tab)
        self.find_bar.set_page(tab.page)
        self._update_shield(url)
        om.set_reader_available(tab.can_read or bool(tab.reader_src),
                                bool(tab.reader_src))

    def _on_title(self, title):
        self.setWindowTitle(f"{title or 'New Tab'} — {brand.NAME}")

    def _sync_chrome(self):
        tab = self.manager.current
        if not tab:
            return
        self._on_url(tab.url)
        self._on_title(tab.title)
        self.topbar.set_loading(tab.loading)
        self.topbar.omni.set_private(tab.private)

        # Keep Study AI connected to the active browser tab.
        self.study_panel.set_view(tab.view)

        if self.devtools.isVisible():
            self.devtools.inspect(tab.page)

    def _on_page_loaded(self, tab):
        if tab.view is None or tab.page is None:
            return
        if self._reader_expect.get(tab.id):
            self._reader_expect[tab.id] = 0
        elif tab.reader_src:
            tab.reader_src = None
        tab.can_read = False
        if tab.url.startswith("http") and not tab.reader_src:
            def done(ok, tb=tab):
                tb.can_read = bool(ok)
                if tb is self.manager.current:
                    self.topbar.omni.set_reader_available(
                        tb.can_read or bool(tb.reader_src), bool(tb.reader_src))
            tab.page.runJavaScript(_READ_CHECK_JS, done)
        if tab is self.manager.current:
            self.topbar.omni.set_reader_available(False if not tab.reader_src else True,
                                                  bool(tab.reader_src))
            self._refresh_shield_badge()

    # ------------------------------------------------------- tab context
    def _tab_context(self, tab_id, gpos):
        tab = self.manager.by_id(tab_id)
        if tab is None:
            return
        menu = RoundMenu(self)
        chosen = {}

        def add(key, icon, text, enabled=True):
            chosen[menu.add(icon, text, None, "", enabled)] = key

        add("reload", "reload", "Reload")
        add("pin", "pin", "Unpin Tab" if tab.pinned else "Pin Tab")
        add("dup", "copy", "Duplicate Tab")
        add("mute", "volume_off" if not tab.chip.audio_muted else "volume",
            "Unmute Site" if getattr(tab.chip, "audio_muted", False) else "Mute Site",
            tab.audible or getattr(tab.chip, "audio_muted", False))
        add("sleep", "sleep", "Put Tab to Sleep",
            tab is not self.manager.current and not tab.sleeping)
        menu.addSeparator()
        group_menu = menu.submenu("folder", "Add to Group")
        group_acts = {}
        for group in self.manager.groups.values():
            group_acts[group_menu.addAction(group["name"])] = group
        new_group_act = group_menu.addAction("New Group…")
        ungroup_act = menu.add("close", "Remove from Group", None, "", tab.group is not None)
        menu.addSeparator()
        add("close", "close", "Close Tab")
        add("others", "close", "Close Other Tabs")
        add("right", "close", "Close Tabs to the Right")
        picked = menu.exec(gpos)
        if picked is None:
            return
        key = chosen.get(picked)
        m = self.manager
        if key == "reload" and tab.view is not None:
            tab.view.reload() if tab.url != HOME_URL else m.load(tab)
        elif key == "pin":
            m.pin_tab(tab_id, not tab.pinned)
        elif key == "dup":
            m.duplicate_tab(tab_id)
        elif key == "mute":
            m.toggle_mute(tab_id)
        elif key == "sleep":
            m.sleep_tab(tab)
        elif key == "close":
            m.close_tab(tab_id)
        elif key == "others":
            m.close_others(tab_id)
        elif key == "right":
            m.close_right(tab_id)
        elif picked is new_group_act:
            name, ok = QInputDialog.getText(self, "Tab group", "Group name:")
            if ok:
                m.set_tab_group(tab_id, m.create_group(name.strip()))
        elif picked in group_acts:
            m.set_tab_group(tab_id, group_acts[picked])
        elif picked is ungroup_act:
            m.set_tab_group(tab_id, None)

    # ------------------------------------------------------- duplicates
    def _on_duplicate(self, tab_id, other_id, url):
        if not self._dup_warn:
            return
        other = self.manager.by_id(other_id)
        if other is None:
            return
        self._dup_tab_id, self._dup_other_id = tab_id, other_id
        self.dup_bar.text.setText(f"Already open in “{other.title or 'another tab'}”.")
        self.dup_bar.show()
        self.dup_bar.raise_()
        self._place_overlays()

    def _dup_switch(self):
        other = self.manager.by_id(self._dup_other_id or 0)
        dup = self._dup_tab_id
        self.dup_bar.hide()
        if other is not None:
            self.manager.set_current(other)
        if dup is not None:
            self.manager.close_tab(dup)

    # ------------------------------------------------------------ selection
    def _note_from_selection(self, text):
        tab = self.manager.current
        if not tab or not text or not text.strip():
            return
        quote_text = text.strip()
        first = quote_text.splitlines()[0][:60]
        note_id = self.storage.create_note(first or "Quote", f"> {quote_text}\n\n",
                                           tab.url, tab.title)
        self.panels.show_panel(self.notes_panel)
        self.notes_panel.reload()
        self.notes_panel._select_id(note_id)

    def _search_selection(self, text):
        if text and text.strip():
            self.manager.new_tab(omni.search_url(text.strip(), self._search_url))

    # ------------------------------------------------------------ shield
    def _update_shield(self, url):
        report = self.safety.report(url, self.privacy.trackers_blocked)
        internal = (url.startswith("studybrowse") or not url
                    or "Local network address" in report.reasons)
        tab = self.manager.current
        self.topbar.omni.set_security(report.verdict.value, report.https, internal)
        self._refresh_shield_badge(report)
        if report.verdict is Verdict.DANGER and report.host not in self._dismissed_hosts:
            self.banner.show_report(report)
            self._place_overlays()
        else:
            self.banner.hide()

    def _refresh_shield_badge(self, report=None):
        tab = self.manager.current
        if not tab:
            return
        report = report or self.safety.report(tab.url, self.privacy.trackers_blocked)
        host = QUrl(tab.url).host()
        n = self.privacy.stats_for(host)["blocked"] if host else 0
        off = self._shield_mode == "off" or host in self.storage.shield_off_hosts()
        self.topbar.set_shield(T["ink3"] if off else verdict_color(report.verdict), 0 if off else n)

    def _dismiss_banner(self, permanent=False):
        tab = self.manager.current
        if permanent and tab:
            self._dismissed_hosts.add(QUrl(tab.url).host())
        self.banner.hide()

    def _back_to_safety(self):
        self._dismiss_banner(False)
        tab = self.manager.current
        if tab and tab.view is not None:
            if tab.view.history().canGoBack():
                tab.view.back()
            else:
                self.manager.load(tab)

    def _show_site_info(self):
        tab = self.manager.current
        if not tab:
            return
        host = QUrl(tab.url).host()
        report = self.safety.report(tab.url, self.privacy.trackers_blocked)
        perms = [(r["ptype"], bool(r["granted"])) for r in self.storage.list_permissions()
                 if r["host"] == host]
        zoom = round(tab.view.zoomFactor() * 100) if tab.view is not None else 100
        dlg = SiteInfoDialog(report, self._shield_mode, self.vpn.state,
                             self.privacy.stats_for(host) if host else None, self,
                             shield_on=host not in self.storage.shield_off_hosts(),
                             zoom=zoom, perms=perms)

        def toggled(on, h=host):
            self.storage.set_site_shield_off(h, not on)
            self.privacy.set_allow_hosts(self.storage.shield_off_hosts())
            self._refresh_shield_badge()
            if tab.view is not None:
                tab.view.reload()
        dlg.shield_toggled.connect(toggled)
        dlg.reset_zoom.connect(self._zoom_reset)
        dlg.forget_permissions.connect(
            lambda h=host: [self.storage.delete_permission(h, p) for p, _g in perms])
        dlg.exec()

    def _set_shield_mode(self, mode):
        self.storage.set_setting("shield_mode", mode)
        self._apply_all_settings()
        tab = self.manager.current
        if tab:
            self._update_shield(tab.url)
        self.toast.show_message(f"Shield: {mode.capitalize()}", "shield")

    def _vpn_mode(self, mode):
        if mode == "off":
            self.vpn.disconnect_tunnel(self.profiles)
        elif mode == "system":
            self.vpn.connect_tunnel(self.profiles, VpnConfig(mode=VpnMode.SYSTEM))
        else:
            dlg = dialogs.VpnDialog(self, self.vpn.config.proxy_type,
                                    self.vpn.config.host, self.vpn.config.port)
            if dlg.exec():
                self.vpn.connect_tunnel(self.profiles, VpnConfig(
                    mode=VpnMode.MANUAL, proxy_type=dlg.type_box.currentText(),
                    host=dlg.host_edit.text().strip() or "127.0.0.1",
                    port=dlg.port_spin.value()))

    # ------------------------------------------------------------ security prompts
    def _on_cert_error(self, error):
        host = error.url().host()
        if not error.isOverridable():
            error.rejectCertificate()
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Your connection is not private")
        box.setText(f"<b>{host}</b> presented an invalid security certificate.")
        box.setInformativeText(f"{error.description()}\n\nAttackers might be trying to "
                               "steal your information. Continuing is unsafe.")
        back = box.addButton("Back to safety", QMessageBox.ButtonRole.AcceptRole)
        go = box.addButton("Proceed anyway (unsafe)", QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(back)
        box.exec()
        if box.clickedButton() is go:
            error.acceptCertificate()
        else:
            error.rejectCertificate()

    def _on_auth(self, tab, url, authenticator):
        dlg = AuthDialog(self, url.host(), authenticator.realm())
        if dlg.exec():
            authenticator.setUser(dlg.user.text())
            authenticator.setPassword(dlg.pw.text())

    # ------------------------------------------------------------ fullscreen
    def _set_fullscreen(self, on, chrome_hidden=True):
        self._fullscreen = on
        if on:
            self.showFullScreen()
        else:
            self.showNormal()
        for w in (self.strip, self.topbar):
            w.setVisible(not on)
        self.bookmarks_bar.setVisible(
            not on and self.storage.get_setting("bookmarks_bar", "0") == "1")
        self._place_overlays()

    def _fullscreen_toggle(self):
        self._web_fullscreen = False
        self._set_fullscreen(not self.isFullScreen())

    def _on_web_fullscreen(self, request):
        request.accept()
        self._web_fullscreen = request.toggleOn()
        self._set_fullscreen(request.toggleOn())

    def _escape(self):
        if self.palette.isVisible():
            self.palette.hide()
        elif self.find_bar.isVisible():
            self.find_bar.close_bar()
        elif self.panels.isVisible():
            self.panels.close_panel()
        elif self.isFullScreen():
            self._fullscreen_toggle()

    # ------------------------------------------------------------ theme
    def _toggle_dark(self):
        self._theme_pref = "light" if theme.is_dark() else "dark"
        self.storage.set_setting("theme", self._theme_pref)
        self._apply_theme()

    def _apply_theme(self):
        self._load_prefs()
        self._resolve_theme()
        icons.clear_cache()
        QApplication.instance().setStyleSheet(build_qss())
        self.strip.retheme()
        self.rail.retheme()
        self.topbar.retheme()
        self.find_bar.retheme()
        self.dup_bar.retheme()
        self.bookmarks_bar.refresh()
        self._rebuild_panels()
        self._reload_home_tabs()
        tab = self.manager.current
        if tab:
            self._update_shield(tab.url)
            self.topbar.omni.set_saved(self.storage.is_saved(tab.url))

    def _reload_home_tabs(self):
        for tab in self.manager.tabs:
            if tab.url == HOME_URL and tab.view is not None:
                self.manager.load(tab)

    # ------------------------------------------------------------ tabs
    def _next_tab(self):
        if self.manager.tabs and self.manager.current:
            i = self.manager.tabs.index(self.manager.current)
            self.manager.set_current(self.manager.tabs[(i + 1) % len(self.manager.tabs)])

    def _prev_tab(self):
        if self.manager.tabs and self.manager.current:
            i = self.manager.tabs.index(self.manager.current)
            self.manager.set_current(self.manager.tabs[(i - 1) % len(self.manager.tabs)])

    def _reopen(self):
        entry = self.session.pop_closed()
        if entry:
            self.manager.new_tab(entry["url"], private=entry["private"])

    def _save_session_now(self):
        tabs, active = self.manager.session_snapshot()
        self.session.save_session(tabs, active)

    def _restore_session(self):
        sess = self.session.load_session()
        if not sess or not sess.get("tabs"):
            return
        for entry in sess["tabs"]:
            tab = self.manager.new_tab(entry["url"], private=entry.get("private", False),
                                       foreground=False)
            if entry.get("pinned"):
                tab.pinned = True
                tab.chip.set_pinned(True)
            group = entry.get("group")
            if group:
                self.manager.groups[group["id"]] = group
                self.manager._next_gid = max(self.manager._next_gid, group["id"] + 1)
                tab.group = group
                tab.chip.set_group(group["color"])
        self.manager._sort_and_sync()
        active = sess.get("active", 0)
        if 0 <= active < len(self.manager.tabs):
            self.manager.set_current(self.manager.tabs[active])

    # ------------------------------------------------------------ scheme actions
    def _page_action(self, kind, payload):
        if kind == "home":
            self.manager.load(self.manager.current)
            return
        if not payload.startswith("/"):
            payload = "/" + payload
        path, _, query = payload.partition("?")
        path = path.strip("/")
        params = {}
        for part in query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = unquote(v.replace("+", " "))
        if path == "restore":
            self._restore_session()
        elif path == "saved":
            self.panels.show_panel(self.saved_panel)
        elif path == "notes":
            self.panels.show_panel(self.notes_panel)
        elif path == "history":
            self.panels.show_panel(self.history_panel)
        elif path == "retry":
            url = params.get("url", "")
            tab = self.manager.current
            if url and tab and tab.view is not None:
                tab.view.setUrl(QUrl(url))
        elif path == "search":
            self._navigate(params.get("q", ""))
        elif path == "focus":
            self.focus.start(int(params.get("min", 25)), int(params.get("brk", 5)))
        elif path == "focusstop":
            self.focus.stop()
            self._back_to_safety()
        elif path == "exitreader":
            tab = self.manager.current
            if tab:
                self._leave_reader(tab, reload=True)

    # ------------------------------------------------------------ saved/notes
    def _toggle_save(self):
        tab = self.manager.current
        if not tab or not tab.url.startswith("http"):
            return
        if self.storage.is_saved(tab.url):
            self.storage.unsave(tab.url)
            self.toast.show_message("Removed from library", "star")
        else:
            self.storage.save_page(tab.url, tab.title or tab.url)
            self.toast.show_message("Saved to your library", "check",
                                    "Add note", lambda: self._notes_hotkey())
        self.topbar.omni.set_saved(self.storage.is_saved(tab.url))
        self.saved_panel.reload()
        self.bookmarks_bar.refresh()

    def _toggle_bookmarks_bar(self):
        on = not self.bookmarks_bar.isVisible()
        self.storage.set_setting("bookmarks_bar", "1" if on else "0")
        self.bookmarks_bar.setVisible(on)
        self.bookmarks_bar.refresh()

    def _notes_hotkey(self):
        self.panels.show_panel(self.notes_panel)
        tab = self.manager.current
        if tab and tab.url.startswith("http"):
            self.notes_panel.create_from_page(tab.url, tab.title)

    def _library_menu(self):
        menu = RoundMenu(self)
        menu.add("saved", "Saved pages", lambda: self.panels.show_panel(self.saved_panel), "Ctrl+Shift+B")
        menu.add("notes", "Study notes", lambda: self.panels.show_panel(self.notes_panel), "Ctrl+Alt+N")
        menu.add("history", "History", lambda: self.panels.show_panel(self.history_panel), "Ctrl+H")
        menu.add("download", "Downloads", lambda: self.panels.show_panel(self.downloads_panel), "Ctrl+J")
        popup_under_menu(menu, self.topbar.library)

    # ------------------------------------------------------------ zoom
    def _host_zoom(self, host):
        site = self.storage.get_site(host) if host else {"zoom": None}
        if site["zoom"]:
            return int(site["zoom"])
        return int(self.storage.get_setting("default_zoom", "100") or 100)

    def _apply_zoom(self, tab):
        if tab.view is None:
            return
        host = QUrl(tab.url).host() if tab.url.startswith("http") else ""
        pct = self._host_zoom(host) if host else 100
        if abs(tab.view.zoomFactor() * 100 - pct) > 0.5:
            tab.view.setZoomFactor(pct / 100.0)
        if tab is self.manager.current:
            self.topbar.omni.set_zoom(round(pct))

    def _zoom_now(self):
        tab = self.manager.current
        return round(tab.view.zoomFactor() * 100) if tab and tab.view is not None else 100

    def _zoom_in(self):
        self._set_zoom(self._zoom_now() + 10)

    def _zoom_out(self):
        self._set_zoom(self._zoom_now() - 10)

    def _zoom_reset(self):
        tab = self.manager.current
        host = QUrl(tab.url).host() if tab else ""
        if host:
            self.storage.set_site_zoom(host, None)
        self._set_zoom(int(self.storage.get_setting("default_zoom", "100") or 100), persist=False)

    def _set_zoom(self, pct, persist=True):
        pct = max(30, min(300, int(pct)))
        tab = self.manager.current
        if not tab or tab.view is None:
            return
        host = QUrl(tab.url).host() if tab.url.startswith("http") else ""
        if host and persist:
            self.storage.set_site_zoom(host, pct)
            for other in self.manager.tabs:
                if other.view is not None and QUrl(other.url).host() == host:
                    other.view.setZoomFactor(pct / 100.0)
        else:
            tab.view.setZoomFactor(pct / 100.0)
        self.topbar.omni.set_zoom(pct)

    # ------------------------------------------------------------ find
    def _show_find(self):
        tab = self.manager.current
        if not tab:
            return
        self.find_bar.set_page(tab.page)
        self.find_bar.show()
        self.find_bar.raise_()
        self.find_bar.edit.setFocus()
        self.find_bar.edit.selectAll()
        self._place_overlays()

    # ------------------------------------------------------------ reader
    def _toggle_reader(self):
        tab = self.manager.current
        if not tab or tab.page is None or not tab.url.startswith("http") and not tab.reader_src:
            return
        if tab.reader_src:
            self._leave_reader(tab, reload=True)
            return

        def got(raw, tb=tab):
            data = reader_mod.parse_result(raw)
            if tb.view is None:
                return
            if data is None:
                self.toast.show_message("This page doesn't look like an article",
                                        "reader", color=T["warn"])
                return
            src = tb.url
            self._reader_expect[tb.id] = 1
            tb.reader_src = src
            tb.view.setHtml(reader_mod.build_page(data, src, theme.is_dark()), QUrl(src))
            if tb is self.manager.current:
                self.topbar.omni.set_reader_available(True, True)
        tab.page.runJavaScript(reader_mod.EXTRACT_JS, got)

    def _leave_reader(self, tab, reload=False):
        src = tab.reader_src
        tab.reader_src = None
        self._reader_expect[tab.id] = 0
        if reload and src and tab.view is not None:
            tab.view.setUrl(QUrl(src))
        if tab is self.manager.current:
            self.topbar.omni.set_reader_available(tab.can_read, False)

    # ------------------------------------------------------------ dev
    def _view_source(self):
        tab = self.manager.current
        if tab and tab.url.startswith("http"):
            self.manager.new_tab("view-source:" + tab.url)

    def toggle_devtools(self):
        tab = self.manager.current
        if self.devtools.isVisible():
            self.devtools.detach()
            self.devtools.hide()
        elif tab and tab.page is not None:
            self.devtools.show()
            self.devtools.inspect(tab.page)

    # ------------------------------------------------------------ downloads/focus UI
    def _dl_started(self, item):
        self.toast.show_message(f"Downloading {item.name}", "download", "Show",
                                lambda: self.panels.show_panel(self.downloads_panel))

    def _dl_finished(self, item):
        self.toast.show_message(f"Downloaded {item.name}", "check", "Show in folder",
                                lambda p=item.path: reveal(p), ms=5000, color=T["success"])

    def _focus_toggle(self):
        if self.focus.active:
            if dialogs.confirm(self, "End focus session", "Stop the current session?"):
                self.focus.stop()
        else:
            self.focus.start(25, 5)

    def _focus_menu(self):
        menu = RoundMenu(self)
        if self.focus.active:
            menu.add("play" if self.focus.state == "paused" else "pause",
                     "Resume" if self.focus.state == "paused" else "Pause",
                     self.focus.pause_toggle)
            menu.add("plus", "Add 5 minutes", lambda: self.focus.add_minutes(5))
            menu.add("close", "End session", self.focus.stop)
        else:
            for m, b, label in ((25, 5, "Pomodoro · 25 min"), (50, 10, "Deep work · 50 min"),
                                (90, 20, "Marathon · 90 min")):
                menu.add("focus", label, lambda m=m, b=b: self.focus.start(m, b))
        popup_under_menu(menu, self.topbar.focus_pill)

    def _focus_tick(self, remaining, total):
        label = fmt_clock(remaining)
        self.topbar.set_focus_pill(label, self.focus.state)

    def _focus_state(self, state):
        if state == "idle":
            self.topbar.set_focus_pill("", "idle")
        else:
            self.topbar.set_focus_pill(fmt_clock(self.focus.remaining), state)

    def _focus_done(self, completed):
        if completed and self.focus.state == "break":
            self.toast.show_message("Focus session complete — enjoy your break", "check",
                                    ms=6000, color=T["success"])
        elif completed:
            self.toast.show_message("Break over — ready for another round?", "focus",
                                    "Start", lambda: self.focus.start(25, 5), ms=7000)

    def _on_focus_block(self, page, host):
        def show():
            html = (f"<html><body style=\"font-family:{T['font']};display:flex;align-items:center;"
                    f"justify-content:center;height:100vh;margin:0;background:{T['surface']};"
                    f"color:{T['ink1']}\"><div style='text-align:center;max-width:420px'>"
                    f"<div style='font-size:46px'>🎯</div><h2 style='margin:12px 0 6px'>Stay focused</h2>"
                    f"<p style='color:{T['ink2']};line-height:1.6'><b>{host}</b> is blocked until your "
                    f"focus session ends ({fmt_clock(self.focus.remaining)} left).</p>"
                    f"<p><a href='studybrowse://action/focusstop' style='color:{T['accent']}'>"
                    f"End session and continue</a></p></div></body></html>")
            try:
                page.setHtml(html, QUrl("studybrowse://blocked"))
            except RuntimeError:
                pass
        QTimer.singleShot(0, show)

    # ------------------------------------------------------------ settings
    def _clear_cookies(self):
        for prof in self.profiles.all_profiles():
            prof.cookieStore().deleteAllCookies()
        self.toast.show_message("Cookies and site data cleared", "check")

    def _clear_cache(self):
        for prof in self.profiles.all_profiles():
            prof.clearHttpCache()
        self.toast.show_message("Cache cleared", "check")

    def _open_settings(self, page=0):
        dlg = dialogs.SettingsDialog(self.storage, self, self._clear_cookies,
                                     self._clear_cache, start_page=page if isinstance(page, int) else 0)
        dlg.changed.connect(self._on_setting_changed)
        dlg.exec()

    def _show_menu(self):
        try:
            ctx = MenuContext()
            tab = self.manager.current
            ctx.actions = {
                "new_tab": lambda: self.manager.new_tab(),
                "new_private": lambda: self.manager.new_tab(private=True),
                "reopen": self._reopen,
                "open_url": lambda u, p: self.manager.new_tab(u, private=p),
                "sleep_tabs": self._sleep_tabs,
                "toggle_save": self._toggle_save,
                "create_note": self._notes_hotkey,
                "reader": self._toggle_reader,
                "find": self._show_find,
                "pdf": self._save_pdf,
                "screenshot": self._screenshot,
                "copy_url": lambda: self._copy_text(tab.url) if tab else None,
                "external": self._external,
                "view_source": self._view_source,
                "devtools": self.toggle_devtools,
                "panel_saved": lambda: self.panels.show_panel(self.saved_panel),
                "panel_notes": lambda: self.panels.show_panel(self.notes_panel),
                "panel_history": lambda: self.panels.show_panel(self.history_panel),
                "downloads": lambda: self.panels.show_panel(self.downloads_panel),
                "focus_toggle": self._focus_toggle,
                "shield_mode": self._set_shield_mode,
                "site_info": self._show_site_info,
                "vpn_mode": self._vpn_mode,
                "zoom_in": self._zoom_in, "zoom_out": self._zoom_out,
                "zoom_reset": self._zoom_reset,
                "toggle_dark": self._toggle_dark,
                "fullscreen": self._fullscreen_toggle,
                "toggle_bookmarks": self._toggle_bookmarks_bar,
                "toggle_rail": lambda: self.rail.setVisible(not self.rail.isVisible()),
                "palette": lambda: self.palette.open_palette(),
                "settings": self._open_settings,
                "shortcuts": lambda: dialogs.ShortcutsDialog(self).show(),
                "clear_history": self._clear_history,
                "about": lambda: dialogs.AboutDialog(self).show(),
            }
            ctx.zoom_get = self._zoom_now
            ctx.fullscreen = self._fullscreen
            ctx.rail_visible = self.rail.isVisible()
            ctx.bookmarks_bar = self.bookmarks_bar.isVisible()
            ctx.recent_closed = self.session.recent_closed()
            ctx.shield_mode = self._shield_mode
            ctx.vpn_state = self.vpn.state
            ctx.dark = theme.is_dark()
            ctx.reader_ok = bool(tab and (tab.can_read or tab.reader_src))
            ctx.focus_active = self.focus.active
            ctx.devtools = self.devtools.isVisible()
            popup_under_menu(build_overflow_menu(ctx), self.topbar.menu)
        except Exception:
            QMessageBox.critical(self, "Menu failed to open", traceback.format_exc())

    def _sleep_tabs(self):
        n = self.manager.sleep_idle(force=True)
        self.toast.show_message(f"Put {n} tab{'s' if n != 1 else ''} to sleep" if n
                                else "No background tabs to sleep", "sleep")

    def _clear_history(self):
        if dialogs.confirm(self, "Clear history", "Delete all browsing history?"):
            self.storage.clear_history()
            self.history_panel.reload()

    def _save_pdf(self):
        tab = self.manager.current
        if not tab or tab.page is None:
            return
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        safe = "".join(c for c in (tab.title or "page") if c.isalnum() or c in " -_")[:60] or "page"
        path, _ok = QFileDialog.getSaveFileName(self, "Save page as PDF",
                                                f"{base}/{safe}.pdf", "PDF (*.pdf)")
        if not path:
            return
        page = tab.page

        def finished(file_path, ok):
            try:
                page.pdfPrintingFinished.disconnect(finished)
            except (RuntimeError, TypeError):
                pass
            self.toast.show_message("PDF saved" if ok else "Could not save PDF",
                                    "check" if ok else "warning", "Show" if ok else None,
                                    (lambda p=file_path: reveal(p)) if ok else None,
                                    color=T["success"] if ok else T["danger"])
        page.pdfPrintingFinished.connect(finished)
        page.printToPdf(path)

    def _screenshot(self):
        tab = self.manager.current
        if not tab or tab.view is None:
            return
        folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation) \
            or os.path.expanduser("~")
        path = os.path.join(folder, time.strftime("Folio screenshot %Y-%m-%d %H.%M.%S.png"))
        ok = tab.view.grab().save(path)
        self.toast.show_message("Screenshot saved" if ok else "Screenshot failed",
                                "camera" if ok else "warning", "Show" if ok else None,
                                (lambda: reveal(path)) if ok else None)

    def _manage_app(self, app_id=None):
        row = None
        if app_id is not None:
            for candidate in self.storage.list_apps():
                if candidate["id"] == app_id:
                    row = candidate
        fav_ok, fav_path = False, None
        tab = self.manager.current
        if (row is not None and tab is not None and tab.view is not None
                and tab.url.startswith("http")
                and QUrl(tab.url).host() == QUrl(row["url"]).host()):
            ic = tab.view.icon()
            if not ic.isNull():
                folder = os.path.join(ROOT, "app_icons")
                os.makedirs(folder, exist_ok=True)
                fav_path = os.path.join(folder, f"app_{row['id']}.png")
                ic.pixmap(64, 64).save(fav_path)
                fav_ok = True
        current_url = tab.url if tab and tab.url.startswith("http") else ""
        dlg = dialogs.QuickAppDialog(self, name=row["name"] if row else "",
                                     url=row["url"] if row else current_url,
                                     icon_field=row["icon"] if row else "letter",
                                     favicon_available=fav_ok)
        if dlg.exec():
            name = dlg.name.text().strip() or "App"
            url = dlg.url.text().strip()
            if url and "://" not in url:
                url = "https://" + url
            self.storage.save_app(name, url, dlg.result_icon(fav_path),
                                  row["id"] if row else None)
            self.rail.refresh()

    # ------------------------------------------------------------ palette
    def _palette_items(self):
        m = self.manager
        C = PaletteItem
        items = [
            C("plus", "New tab", "Command", lambda: m.new_tab(), "Ctrl+T"),
            C("mask", "New private tab", "Command", lambda: m.new_tab(private=True), "Ctrl+Shift+P"),
            C("restore", "Reopen closed tab", "Command", self._reopen, "Ctrl+Shift+T"),
            C("reload", "Reload page", "Command", self._reload_stop, "Ctrl+R"),
            C("star", "Save / unsave page", "Command", self._toggle_save, "Ctrl+D"),
            C("note_add", "Create note from page", "Command", self._notes_hotkey, "Ctrl+Alt+N"),
            C("reader", "Reader mode", "Command", self._toggle_reader, "Ctrl+Alt+R"),
            C("find", "Find in page", "Command", self._show_find, "Ctrl+F"),
            C("focus", "Start 25-minute focus session", "Focus",
              lambda: self.focus.start(25, 5)),
            C("focus", "Start 50-minute deep-work session", "Focus",
              lambda: self.focus.start(50, 10)),
            C("sleep", "Put background tabs to sleep", "Command", self._sleep_tabs),
            C("moon", "Toggle dark mode", "Appearance", self._toggle_dark),
            C("bar", "Toggle bookmarks bar", "Appearance", self._toggle_bookmarks_bar, "Ctrl+Shift+O"),
            C("full", "Toggle full screen", "Appearance", self._fullscreen_toggle, "F11"),
            C("settings", "Open settings", "Settings", self._open_settings, "Ctrl+,"),
            C("palette", "Change accent colour…", "Settings", lambda: self._open_settings(1)),
            C("shield", "Site & privacy report", "Security", self._show_site_info),
            C("shield", "Shield: Standard", "Security", lambda: self._set_shield_mode("standard")),
            C("shield", "Shield: Strict", "Security", lambda: self._set_shield_mode("strict")),
            C("saved", "Open saved pages", "Library", lambda: self.panels.show_panel(self.saved_panel), "Ctrl+Shift+B"),
            C("notes", "Open study notes", "Library", lambda: self.panels.show_panel(self.notes_panel)),
            C("history", "Open history", "Library", lambda: self.panels.show_panel(self.history_panel), "Ctrl+H"),
            C("download", "Open downloads", "Library", lambda: self.panels.show_panel(self.downloads_panel), "Ctrl+J"),
            C("pdf", "Save page as PDF", "Page", self._save_pdf, "Ctrl+P"),
            C("camera", "Screenshot visible area", "Page", self._screenshot),
            C("code", "View page source", "Developer", self._view_source, "Ctrl+U"),
            C("devtools", "Toggle developer tools", "Developer", self.toggle_devtools, "F12"),
            C("keyboard", "Keyboard shortcuts", "Help", lambda: dialogs.ShortcutsDialog(self).show()),
        ]
        for tab in m.tabs:
            hint = "Open tab" + (" · private" if tab.private else "")
            if tab.group:
                hint += f" · {tab.group['name']}"
            if tab.pinned:
                hint += " · pinned"
            if tab.sleeping:
                hint += " · sleeping"
            items.append(C("mask" if tab.private else "tab", tab.title or "New Tab", hint,
                           lambda t=tab: m.set_current(t), kind="tab"))
        for row in self.storage.list_saved():
            items.append(C("star", row["title"] or row["url"], "Saved · " + row["url"][:60],
                           lambda u=row["url"]: self._open_from_panel(u)))
        for row in self.storage.list_notes():
            items.append(C("notes", row["title"] or "Untitled", "Note",
                           lambda: self.panels.show_panel(self.notes_panel)))
        for row in self.storage.list_apps():
            items.append(C("globe", row["name"], "Quick app",
                           lambda u=row["url"]: m.new_tab(u)))
        for row in self.storage.recent_history(25):
            items.append(C("history", row["title"] or row["url"], "History · " + row["url"][:60],
                           lambda u=row["url"]: self._open_from_panel(u)))
        return items

    # ------------------------------------------------------------ layout
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_overlays()

    def _place_overlays(self):
        width, height = self.web_area.width(), self.web_area.height()
        if self.panels.isVisible():
            self.panels.setGeometry(QRect(width - PANEL_W, 0, PANEL_W, height))
            if self.panels.current is not None:
                self.panels.current.setGeometry(0, 0, PANEL_W, height)
        if self.find_bar.isVisible():
            self.find_bar.move(width - self.find_bar.width() - 16
                               - (PANEL_W if self.panels.isVisible() else 0), 12)
        if self.banner.isVisible():
            w = min(620, width - 32)
            self.banner.setGeometry((width - w) // 2, 12, w, self.banner.sizeHint().height())
        if self.dup_bar.isVisible():
            w = min(520, width - 32)
            y = 12 + (self.banner.height() + 8 if self.banner.isVisible() else 0)
            self.dup_bar.setGeometry((width - w) // 2, y, w, self.dup_bar.sizeHint().height())
        self.toast.reposition()
        self.status.reposition()

    # ------------------------------------------------------------ shutdown
    def closeEvent(self, event):
        self.focus.stop(silent=True)
        self.downloads.cancel_all()
        self._save_session_now()
        try:
            self.notes_panel._flush()
        except Exception:
            pass
        self.devtools.detach()
        self.manager.close_all()
        QApplication.processEvents()
        self.profiles.shutdown()
        QApplication.processEvents()
        event.accept()
