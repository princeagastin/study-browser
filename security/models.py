from dataclasses import dataclass, field
from enum import Enum
from typing import List


class Verdict(Enum):
    UNKNOWN = "unknown"
    SAFE = "safe"
    CAUTION = "caution"
    DANGER = "danger"


class PrivacyMode(Enum):
    OFF = "off"
    STANDARD = "standard"
    STRICT = "strict"


class VpnMode(Enum):
    OFF = "off"
    SYSTEM = "system"
    MANUAL = "manual"


@dataclass
class SiteReport:
    url: str
    host: str
    verdict: Verdict
    https: bool
    reasons: List[str] = field(default_factory=list)
    trackers_blocked: int = 0


@dataclass
class VpnConfig:
    mode: VpnMode = VpnMode.OFF
    proxy_type: str = "socks5"   # "socks5" | "http"
    host: str = "127.0.0.1"
    port: int = 9050