from PySide6.QtCore import QObject
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor

from security.models import PrivacyMode

# host suffix -> category
CATEGORY = {}


def _add(category, *domains):
    for d in domains:
        CATEGORY[d] = category


_add("ads",
     "doubleclick.net", "adsystem.amazon.com", "amazon-adsystem.com",
     "outbrain.com", "taboola.com", "googlesyndication.com",
     "googleadservices.com", "2mdn.net", "adnxs.com", "adsrvr.org",
     "pubmatic.com", "rubiconproject.com", "criteo.com", "criteo.net",
     "casalemedia.com", "openx.net", "moatads.com", "adform.net",
     "smartadserver.com", "media.net", "teads.tv", "sharethrough.com",
     "triplelift.com", "yieldmo.com", "adcolony.com", "applovin.com",
     "mopub.com", "revcontent.com", "mgid.com", "zemanta.com",
     "advertising.com", "adsafeprotected.com", "serving-sys.com",
     "bidswitch.net", "contextweb.com", "lijit.com", "sovrn.com")
_add("analytics",
     "google-analytics.com", "googletagmanager.com", "scorecardresearch.com",
     "hotjar.com", "clarity.ms", "mixpanel.com", "segment.io", "segment.com",
     "amplitude.com", "fullstory.com", "mouseflow.com", "crazyegg.com",
     "quantserve.com", "chartbeat.com", "chartbeat.net", "optimizely.com",
     "heapanalytics.com", "statcounter.com", "matomo.cloud", "hs-analytics.net",
     "omtrdc.net", "demdex.net", "2o7.net", "luckyorange.com", "inspectlet.com",
     "newrelic.com", "nr-data.net", "sentry-cdn.com")
_add("tracking",
     "facebook.net", "krxd.net", "bluekai.com", "tiktok.com", "ads-twitter.com",
     "bat.bing.com", "snap.licdn.com", "px.ads.linkedin.com", "ct.pinterest.com",
     "analytics.tiktok.com", "adsymptotic.com", "everesttech.net", "rlcdn.com",
     "tapad.com", "agkn.com", "id5-sync.com", "exelator.com", "addthis.com",
     "sharethis.com", "branch.io", "appsflyer.com", "adjust.com", "onetrust.com",
     "cookielaw.org", "pixel.facebook.com", "analytics.twitter.com",
     "connect.facebook.net", "t.co")
TRACKER_DOMAINS = tuple(CATEGORY.keys())

_ZERO = {"blocked": 0, "third": 0, "ads": 0, "analytics": 0, "tracking": 0}
_LOCAL = ("localhost", "127.0.0.1", "[::1]", "::1")


def registrable(host: str) -> str:
    """Cheap eTLD+1 approximation (good enough for first/third-party)."""
    parts = [p for p in host.split(".") if p]
    if len(parts) <= 2:
        return host
    if len(parts[-1]) == 2 and parts[-2] in ("co", "com", "org", "net", "ac",
                                             "gov", "edu"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def is_local(host: str) -> bool:
    return (host in _LOCAL or host.endswith(".local")
            or host.startswith(("192.168.", "10.", "127.")))


class TrackerInterceptor(QWebEngineUrlRequestInterceptor):
    """Runs on the IO thread: keep it allocation-light and Qt-GUI-free."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.blocked = 0
        self.block_cats = frozenset()      # categories actively blocked
        self.send_gpc = True
        self.allow_hosts = frozenset()
        self.stats = {}

    def _bucket(self, host):
        return self.stats.setdefault(host, dict(_ZERO))

    def interceptRequest(self, info):
        try:
            req_host = info.requestUrl().host()
            first = info.firstPartyUrl().host()
        except Exception:
            return
        if not req_host:
            return
        if self.send_gpc:
            try:
                info.setHttpHeader(b"Sec-GPC", b"1")
                info.setHttpHeader(b"DNT", b"1")
            except Exception:
                pass
        if not first or registrable(req_host) == registrable(first):
            return                      # first-party: never touch
        self._bucket(first)["third"] += 1
        match = next((d for d in TRACKER_DOMAINS
                      if req_host == d or req_host.endswith("." + d)), None)
        if match is None:
            return
        cat = CATEGORY[match]
        if first in self.allow_hosts or cat not in self.block_cats:
            return
        bucket = self._bucket(first)
        bucket["blocked"] += 1
        bucket[cat] += 1
        self.blocked += 1
        info.block(True)


class PrivacyManager(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = PrivacyMode.STANDARD
        self.interceptor = TrackerInterceptor(self)
        self._profiles = None

    def apply(self, profiles, mode: PrivacyMode, send_gpc=True):
        self._profiles = profiles
        self.mode = mode
        self.interceptor.block_cats = (
            frozenset({"ads", "analytics", "tracking"}) if mode is PrivacyMode.STRICT
            else frozenset({"ads"}) if mode is PrivacyMode.STANDARD
            else frozenset())
        self.interceptor.send_gpc = bool(send_gpc)
        for prof in profiles.all_profiles():
            # Always installed (it's what carries GPC and stats); the
            # interceptor itself decides whether to block.
            prof.setUrlRequestInterceptor(
                None if mode is PrivacyMode.OFF and not send_gpc
                else self.interceptor)
            store = prof.cookieStore()
            try:
                if mode is PrivacyMode.STRICT:
                    store.setCookieFilter(self._cookie_filter)
                else:
                    store.setCookieFilter(lambda req: True)
            except Exception:
                pass
    def set_allow_hosts(self, hosts):
        self.interceptor.allow_hosts = frozenset(hosts)

    @staticmethod
    def _cookie_filter(request):
        try:
            return not bool(request.thirdParty)
        except AttributeError:
            return True

    @property
    def trackers_blocked(self) -> int:
        return self.interceptor.blocked

    def stats_for(self, host: str):
        return dict(self.interceptor.stats.get(host, _ZERO))
