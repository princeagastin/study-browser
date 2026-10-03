from PySide6.QtCore import QObject

from security.models import SiteReport, Verdict
from security.url_analyzer import analyze, host_of


class SafetyEngine(QObject):
    """Shield brain: caches per-host verdicts for the session."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache = {}

    def report(self, url: str, trackers_blocked: int = 0) -> SiteReport:
        host = host_of(url)
        if not host or url.startswith("studybrowse"):
            return SiteReport(url, host, Verdict.UNKNOWN, False,
                              ["Internal page"], trackers_blocked)
        key = host
        if key in self._cache:
            rep = self._cache[key]
            rep.trackers_blocked = trackers_blocked
            return rep
        verdict, reasons = analyze(url)
        https = url.startswith("https")
        if verdict is Verdict.UNKNOWN and https:
            verdict = Verdict.SAFE
            reasons = ["Encrypted connection"] + reasons
        rep = SiteReport(url=url, host=host, verdict=verdict, https=https,
                         reasons=reasons, trackers_blocked=trackers_blocked)
        self._cache[key] = rep
        return rep