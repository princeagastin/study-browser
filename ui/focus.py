"""Focus mode: a Pomodoro-style timer that can block distracting sites.

The manager owns all state; the UI (top-bar pill, start page card, settings)
only observes signals. Blocking itself is enforced in StudyPage's
acceptNavigationRequest through ``is_blocked``.
"""
import time

from PySide6.QtCore import QObject, QTimer, Signal

DEFAULT_BLOCKLIST = [
    "youtube.com", "instagram.com", "facebook.com", "twitter.com", "x.com",
    "reddit.com", "tiktok.com", "netflix.com", "twitch.tv", "snapchat.com",
    "9gag.com", "primevideo.com", "hotstar.com", "discord.com",
]

PRESETS = [(25, 5, "Pomodoro"), (50, 10, "Deep work"), (90, 20, "Marathon")]


def fmt(seconds: int) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def parse_blocklist(text: str):
    out = []
    for line in (text or "").replace(",", "\n").splitlines():
        host = line.strip().lower()
        for prefix in ("https://", "http://", "www."):
            if host.startswith(prefix):
                host = host[len(prefix):]
        host = host.split("/")[0]
        if host and host not in out:
            out.append(host)
    return out


class FocusManager(QObject):
    tick = Signal(int, int)          # remaining, total
    state_changed = Signal(str)      # idle | focus | break | paused
    session_finished = Signal(bool)  # completed?

    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.state = "idle"
        self._remaining = 0
        self._total = 0
        self._started = 0.0
        self._resume_state = "focus"
        self._break_minutes = 5
        self._label = ""
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)
        self.reload_blocklist()

    # ------------------------------------------------------------ config
    def reload_blocklist(self):
        raw = self.storage.get_setting("focus_blocklist", None)
        if raw in (None, ""):
            self.blocklist = list(DEFAULT_BLOCKLIST)
        else:
            self.blocklist = parse_blocklist(raw)
        self.enabled_blocking = self.storage.get_setting("focus_block", "1") == "1"

    # ------------------------------------------------------------ queries
    @property
    def active(self):
        return self.state in ("focus", "break", "paused")

    @property
    def remaining(self):
        return self._remaining

    @property
    def total(self):
        return self._total

    def is_blocked(self, host: str) -> bool:
        if self.state not in ("focus", "paused") or not self.enabled_blocking:
            return False
        host = (host or "").lower()
        return any(host == d or host.endswith("." + d) for d in self.blocklist)

    # ------------------------------------------------------------ control
    def start(self, minutes=25, break_minutes=5, label=""):
        self.stop(completed=False, silent=True)
        self._total = self._remaining = int(minutes) * 60
        self._break_minutes = int(break_minutes)
        self._label = label
        self._started = time.time()
        self._set_state("focus")
        self._timer.start()
        self.tick.emit(self._remaining, self._total)

    def pause_toggle(self):
        if self.state in ("focus", "break"):
            self._resume_state = self.state
            self._timer.stop()
            self._set_state("paused")
        elif self.state == "paused":
            self._timer.start()
            self._set_state(self._resume_state)

    def add_minutes(self, minutes=5):
        if self.active:
            self._remaining += minutes * 60
            self._total += minutes * 60
            self.tick.emit(self._remaining, self._total)

    def stop(self, completed=False, silent=False):
        if not self.active:
            return
        was = self.state if self.state != "paused" else self._resume_state
        self._timer.stop()
        if was == "focus":
            spent = int(time.time() - self._started)
            if spent >= 60:
                self.storage.add_focus_session(
                    self._started, min(spent, self._total), completed, self._label)
        self._remaining = self._total = 0
        self._set_state("idle")
        if not silent:
            self.session_finished.emit(completed)

    def _set_state(self, state):
        self.state = state
        self.state_changed.emit(state)

    def _on_tick(self):
        self._remaining -= 1
        self.tick.emit(self._remaining, self._total)
        if self._remaining > 0:
            return
        if self.state == "focus":
            self.storage.add_focus_session(
                self._started, self._total, True, self._label)
            self.session_finished.emit(True)
            if self._break_minutes > 0:
                self._total = self._remaining = self._break_minutes * 60
                self._started = time.time()
                self._set_state("break")
                self.tick.emit(self._remaining, self._total)
            else:
                self._timer.stop()
                self._set_state("idle")
        else:
            self._timer.stop()
            self._remaining = self._total = 0
            self._set_state("idle")
            self.session_finished.emit(True)
