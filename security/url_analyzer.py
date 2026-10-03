import re
from urllib.parse import urlparse

from security.models import Verdict

_SUS_TLDS = {".zip", ".mov", ".country", ".party", ".review", ".science",
             ".work", ".click", ".link", ".gq", ".cf", ".tk", ".ml", ".ga",
             ".top", ".xyz", ".icu", ".rest", ".monster", ".cam"}
_SAFE_DOMAINS = {
    "google.com", "youtube.com", "github.com", "wikipedia.org", "duckduckgo.com",
    "microsoft.com", "mozilla.org", "python.org", "qt.io", "pypi.org",
    "spotify.com", "gmail.com", "stackoverflow.com", "reddit.com",
    "amazon.com", "netflix.com", "apple.com", "cloudflare.com", "openai.com",
    "anthropic.com", "wikimedia.org", "arxiv.org", "nature.com", "mit.edu",
    "stanford.edu", "harvard.edu", "khanacademy.org", "coursera.org",
    "linkedin.com", "notion.so", "pesuacademy.com", "office.com", "live.com",
    "outlook.com", "bing.com", "brave.com", "proton.me", "gitlab.com",
}
# brand token -> official domains
_BRANDS = {
    "google": ("google.com", "google.co.in", "gstatic.com", "googleapis.com",
               "youtube.com", "gmail.com", "goo.gl", "googleusercontent.com"),
    "paypal": ("paypal.com", "paypal.me"),
    "microsoft": ("microsoft.com", "live.com", "office.com", "outlook.com",
                  "microsoftonline.com", "windows.com", "azure.com", "msn.com"),
    "apple": ("apple.com", "icloud.com"),
    "amazon": ("amazon.com", "amazon.in", "amazon.co.uk", "amazon.de",
               "amazonaws.com"),
    "facebook": ("facebook.com", "fb.com", "facebook.net"),
    "instagram": ("instagram.com",),
    "netflix": ("netflix.com",),
    "github": ("github.com", "githubusercontent.com", "github.io"),
    "whatsapp": ("whatsapp.com", "whatsapp.net"),
    "dropbox": ("dropbox.com",),
    "linkedin": ("linkedin.com",),
    "binance": ("binance.com",),
    "coinbase": ("coinbase.com",),
    "steam": ("steampowered.com", "steamcommunity.com"),
    "discord": ("discord.com", "discord.gg", "discordapp.com"),
    "spotify": ("spotify.com",),
    "paytm": ("paytm.com",),
    "sbi": ("sbi.co.in", "onlinesbi.sbi"),
}
_BAIT = {"login", "signin", "secure", "verify", "account", "update",
         "support", "wallet", "confirm", "billing", "recover", "unlock",
         "password", "auth", "reset"}
_IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_CYRILLIC = re.compile(r"[а-яА-Я]")
_LATIN = re.compile(r"[a-zA-Z]")


def host_of(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def _is_private(host: str) -> bool:
    if host in ("localhost", "::1") or host.endswith((".local", ".localhost")):
        return True
    if not _IP_RE.match(host):
        return False
    a, b = (int(x) for x in host.split(".")[:2])
    return a in (10, 127) or (a == 192 and b == 168) or (a == 172 and 16 <= b <= 31)


def _endswith(host, domain):
    return host == domain or host.endswith("." + domain)


def is_known_safe(host: str) -> bool:
    return any(_endswith(host, d) for d in _SAFE_DOMAINS)


def _impersonated(host: str):
    """Return (brand, has_bait) if host uses a brand name it doesn't own."""
    tokens = set(re.split(r"[.\-_]", host))
    for brand, official in _BRANDS.items():
        if brand in tokens and not any(_endswith(host, d) for d in official):
            return brand, bool(tokens & _BAIT)
    return None, False


def analyze(url: str):
    """Return (Verdict, reasons). Pure heuristics, no network calls."""
    reasons = []
    strong = False
    try:
        parts = urlparse(url)
    except ValueError:
        return Verdict.UNKNOWN, ["Unparsable address"]
    host = (parts.hostname or "").lower()
    if not host:
        return Verdict.UNKNOWN, ["No host in address"]
    if _is_private(host):
        return Verdict.UNKNOWN, ["Local network address"]
    if parts.scheme == "http":
        reasons.append("Connection is not encrypted (http)")
    if parts.username or "@" in (parts.netloc or ""):
        reasons.append("Address hides the real site behind a username")
        strong = True
    if _IP_RE.match(host):
        reasons.append("Site is addressed by raw IP")
    if any(host.endswith(t) for t in _SUS_TLDS):
        reasons.append("High-risk top-level domain")
    if "xn--" in host:
        reasons.append("Internationalised (punycode) host — check the spelling")
    if _CYRILLIC.search(host) and _LATIN.search(host):
        reasons.append("Mixed-script host (possible homograph spoof)")
        strong = True
    if host.count("-") >= 3 and len(host) > 24:
        reasons.append("Unusually long hyphenated host")
    if host.count(".") >= 5:
        reasons.append("Unusually many subdomains")
    brand, bait = _impersonated(host)
    if brand and not is_known_safe(host):
        reasons.append(f"Uses the “{brand}” name but isn’t {brand}’s site")
        strong = strong or bait
        if bait:
            reasons.append("Contains account-takeover wording (login/verify…)")
    if is_known_safe(host) and not strong:
        return Verdict.SAFE, ["Well-known domain"] + reasons
    if strong or len(reasons) >= 2:
        return Verdict.DANGER, reasons
    if reasons:
        return Verdict.CAUTION, reasons
    return Verdict.UNKNOWN, reasons
