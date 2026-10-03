import re

from PySide6.QtCore import QObject, QUrl, QStandardPaths
from PySide6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineProfile, QWebEngineSettings)

from browser.omni import HOME_URL, ENGINES, engine_url  # noqa: F401  (re-export)

SEARCH_URL = engine_url("duckduckgo")

_WA = QWebEngineSettings.WebAttribute


def _attr(name):
    """Look up a WebAttribute that may not exist on older Qt builds."""
    return getattr(_WA, name, None)


class BrowserPolicy:
    """Mutable, shared rule-set consulted on every main-frame navigation.

    Lives on the GUI thread (acceptNavigationRequest is a GUI-thread call), so
    plain attributes are safe here.
    """

    def __init__(self):
        self.https_only = False
        self.focus_blocked = lambda host: False    # -> bool
        self.http_allowed = set()                  # hosts the user overrode
        self.on_focus_block = lambda page, host: None


class ProfileManager(QObject):
    """Owns both WebEngine profiles.

    Lifecycle rule: every QWebEngineView/QWebEnginePage must be deleted
    (and events processed) BEFORE shutdown() is called.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.policy = BrowserPolicy()
        self._main = QWebEngineProfile("StudyBrowse", self)
        self._private = QWebEngineProfile(self)
        dl = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation)
        for prof in (self._main, self._private):
            prof.setDownloadPath(dl) if hasattr(prof, "setDownloadPath") else None
            st = prof.settings()
            for name, val in (
                ("PluginsEnabled", True),
                ("LocalStorageEnabled", True),
                ("ScrollAnimatorEnabled", True),
                ("FullScreenSupportEnabled", True),
                ("PdfViewerEnabled", True),
                ("JavascriptCanAccessClipboard", True),
                ("JavascriptCanPaste", True),
                ("WebRTCPublicInterfacesOnly", True),   # no LAN IP leaks
                ("ScreenCaptureEnabled", True),
                ("DnsPrefetchEnabled", True),
                ("ErrorPageEnabled", False),             # we draw our own
                ("FocusOnNavigationEnabled", True),
            ):
                a = _attr(name)
                if a is not None:
                    st.setAttribute(a, val)
            self._compatible_user_agent(prof)
        try:
            self._private.setHttpCacheType(
                QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        except Exception:
            pass

    @staticmethod
    def _compatible_user_agent(prof):
        """Drop the ``QtWebEngine/x.y`` token.

        Google sign-in and a number of web apps refuse embedded-webview user
        agents; the Chromium token alone is what regular Chrome sends.
        """
        ua = prof.httpUserAgent()
        cleaned = re.sub(r"\s*QtWebEngine/\S+", "", ua).strip()
        if cleaned and cleaned != ua:
            prof.setHttpUserAgent(cleaned)

    def apply_settings(self, storage):
        """Re-read user preferences that map to profile-level settings."""
        block_autoplay = storage.get_setting("block_autoplay", "1") == "1"
        force_dark = storage.get_setting("force_dark_pages", "0") == "1"
        spell = storage.get_setting("spellcheck", "1") == "1"
        for prof in self.all_profiles():
            st = prof.settings()
            a = _attr("PlaybackRequiresUserGesture")
            if a is not None:
                st.setAttribute(a, block_autoplay)
            a = _attr("ForceDarkMode")
            if a is not None:
                st.setAttribute(a, force_dark)
            try:
                prof.setSpellCheckEnabled(spell)
                if spell:
                    prof.setSpellCheckLanguages(["en-US"])
            except Exception:
                pass
        self.policy.https_only = storage.get_setting("https_only", "0") == "1"

    @property
    def main(self) -> QWebEngineProfile:
        return self._main

    @property
    def private(self) -> QWebEngineProfile:
        return self._private

    def all_profiles(self):
        return (self._main, self._private)

    def shutdown(self):
        for prof in (self._private, self._main):
            try:
                prof.setUrlRequestInterceptor(None)
            except Exception:
                pass
            prof.deleteLater()


def _is_local_host(host: str) -> bool:
    return (host in ("localhost", "127.0.0.1", "::1", "[::1]")
            or host.endswith((".local", ".localhost"))
            or host.startswith(("192.168.", "10.", "127.")))


class StudyPage(QWebEnginePage):
    """Page handling the studybrowse:// scheme, popups and browsing policy."""

    def __init__(self, profile, view, on_action, on_new_window, policy=None):
        super().__init__(profile, view)
        self._on_action = on_action
        self._on_new_window = on_new_window
        self.policy = policy or BrowserPolicy()

    def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame):
        scheme = url.scheme()
        if scheme == "studybrowse":
            host = url.host()
            if host == "home":
                self._on_action("home", "")
            elif host == "action":
                query = url.query()
                self._on_action("action",
                                url.path() + ("?" + query if query else ""))
            return False
        if is_main_frame and scheme in ("http", "https"):
            host = url.host().lower()
            if self.policy.focus_blocked(host):
                self.policy.on_focus_block(self, host)
                return False
            if (scheme == "http" and self.policy.https_only
                    and not _is_local_host(host)
                    and host not in self.policy.http_allowed):
                secure = QUrl(url)
                secure.setScheme("https")
                if secure.port() == 80:
                    secure.setPort(-1)
                self.setUrl(secure)
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    def createWindow(self, window_type):
        try:
            return self._on_new_window(window_type)
        except TypeError:
            return self._on_new_window()
