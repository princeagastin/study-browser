"""VPN / tunnel architecture.

Real VPN daemons cannot be embedded without external dependencies, so the
architecture is backend-pluggable:

    VpnBackend (abstract)  ->  provides a local QNetworkProxy endpoint
        ExternalSocksBackend   (local daemon: Tor / WireGuard-socks / etc.)
        SystemProxyBackend     (OS-level proxy configuration)
        OffBackend             (direct connection)

VpnManager applies the backend's proxy to every QWebEngineProfile, which
routes ALL browser traffic (normal + private) through the tunnel. A future
native tunnel only needs a new VpnBackend subclass.
"""
from abc import ABC, abstractmethod

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QNetworkProxy

from security.models import VpnConfig, VpnMode


class VpnBackend(ABC):
    name = "abstract"

    @abstractmethod
    def start(self) -> bool:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...

    @abstractmethod
    def proxy(self) -> QNetworkProxy:
        ...


class OffBackend(VpnBackend):
    name = "off"

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def proxy(self) -> QNetworkProxy:
        return QNetworkProxy(QNetworkProxy.ProxyType.NoProxy)


class SystemProxyBackend(VpnBackend):
    name = "system"

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def proxy(self) -> QNetworkProxy:
        return QNetworkProxy(QNetworkProxy.ProxyType.SystemProxy)


class ExternalSocksBackend(VpnBackend):
    """Tunnel provided by a local daemon listening on host:port."""

    name = "external"

    def __init__(self, config: VpnConfig):
        self.config = config
        self._running = False

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False

    def proxy(self) -> QNetworkProxy:
        ptype = (QNetworkProxy.ProxyType.Socks5Proxy
                 if self.config.proxy_type == "socks5"
                 else QNetworkProxy.ProxyType.HttpProxy)
        return QNetworkProxy(ptype, self.config.host, self.config.port)


class VpnManager(QObject):
    state_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = VpnConfig()
        self.backend = OffBackend()
        self.state = "Disconnected"

    def connect_tunnel(self, profiles, config: VpnConfig):
        self.config = config
        self.backend.stop()
        if config.mode is VpnMode.OFF:
            self.backend = OffBackend()
            self.state = "Disconnected"
        elif config.mode is VpnMode.SYSTEM:
            self.backend = SystemProxyBackend()
            self.state = "System proxy"
        else:
            self.backend = ExternalSocksBackend(config)
            self.state = f"Tunnel {config.host}:{config.port}"
        ok = self.backend.start()
        if not ok:
            self.state = "Error"
        proxy = self.backend.proxy()
        for prof in profiles.all_profiles():
            prof.setProxy(proxy)
        self.state_changed.emit(self.state)
        return ok

    def disconnect_tunnel(self, profiles):
        self.backend.stop()
        self.backend = OffBackend()
        for prof in profiles.all_profiles():
            prof.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        self.state = "Disconnected"
        self.state_changed.emit(self.state)