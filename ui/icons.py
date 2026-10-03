"""Bundled SVG icon system.

SVG sources live here as strings and are ALSO written to
assets/icons/*.svg on first launch (sync_assets), so the project ships a
real vector asset folder while rendering stays dependency-light (QtSvg).
"""
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtSvg import QSvgRenderer

_SVG_WRAP = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
             'fill="none" stroke="@C" stroke-width="1.7" stroke-linecap="round" '
             'stroke-linejoin="round">@B</svg>')

BODIES = {
    "back": '<path d="M15 5l-7 7 7 7"/>',
    "forward": '<path d="M9 5l7 7-7 7"/>',
    "reload": '<path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v5h-5"/>',
    "stop": '<path d="M6 6l12 12"/><path d="M18 6L6 18"/>',
    "home": '<path d="M4 11l8-7 8 7"/><path d="M6 9.5V20h12V9.5"/>',
    "external": ('<path d="M14 4h6v6"/><path d="M20 4L10 14"/>'
                 '<path d="M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7'
                 'a1 1 0 0 1 1-1h6"/>'),
    "dots": ('<circle cx="12" cy="5" r="1.4" fill="@C" stroke="none"/>'
             '<circle cx="12" cy="12" r="1.4" fill="@C" stroke="none"/>'
             '<circle cx="12" cy="19" r="1.4" fill="@C" stroke="none"/>'),
    "plus": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "close": '<path d="M6 6l12 12"/><path d="M18 6L6 18"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
    "star": ('<path d="M12 4l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5'
             '.9-5.4-3.9-3.8 5.4-.8z"/>'),
    "star_fill": ('<path d="M12 4l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5'
                  '.9-5.4-3.9-3.8 5.4-.8z" fill="@C"/>'),
    "note_add": ('<path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4"/>'
                 '<path d="M12 11v6"/><path d="M9 14h6"/>'),
    "notes": ('<path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4"/>'
              '<path d="M9 12h7"/><path d="M9 16h7"/>'),
    "saved": '<path d="M6 3h12v18l-6-4-6 4z"/>',
    "history": '<circle cx="12" cy="12" r="8"/><path d="M12 7.5V12l3 2"/>',
    "mask": ('<path d="M3 10c3-1.5 6-2 9-2s6 .5 9 2c-.4 4-2 6.5-4.5 6.5'
             '-1.8 0-2.7-1.2-4.5-1.2s-2.7 1.2-4.5 1.2C5 16.5 3.4 14 3 10z"/>'),
    "pdf": ('<path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4"/>'
            '<path d="M9 17v-4h1.6a1.4 1.4 0 0 1 0 2.8H9"/>'),
    "full": ('<path d="M4 9V4h5"/><path d="M20 9V4h-5"/><path d="M4 15v5h5"/>'
             '<path d="M20 15v5h-5"/>'),
    "full_exit": ('<path d="M9 4v5H4"/><path d="M15 4v5h5"/><path d="M9 20v-5H4"/>'
                  '<path d="M15 20v-5h5"/>'),
    "zoom_in": ('<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>'
                '<path d="M11 8.5v5"/><path d="M8.5 11h5"/>'),
    "zoom_out": ('<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>'
                 '<path d="M8.5 11h5"/>'),
    "find": ('<circle cx="10" cy="10" r="6"/><path d="M14.5 14.5L20 20"/>'
             '<path d="M8 10h4"/>'),
    "keyboard": ('<rect x="3" y="7" width="18" height="11" rx="2"/>'
                 '<path d="M7 11h.01M11 11h.01M15 11h.01M17 14H7"/>'),
    "trash": ('<path d="M5 7h14"/><path d="M9 7V5h6v2"/>'
              '<path d="M7 7l1 13h8l1-13"/>'),
    "info": ('<circle cx="12" cy="12" r="8"/><path d="M12 11v5"/>'
             '<path d="M12 8h.01"/>'),
    "restore": '<path d="M4 12a8 8 0 1 0 2.34-5.66"/><path d="M4 4v5h5"/>',
    "command": ('<rect x="3" y="6" width="18" height="12" rx="3"/>'
                '<path d="M9 9l-3 3 3 3"/><path d="M15 9l3 3-3 3"/>'),
    "settings": ('<path d="M5 8h9"/><circle cx="17" cy="8" r="2.2"/>'
                 '<path d="M19 16h-9"/><circle cx="7" cy="16" r="2.2"/>'),
    "globe": ('<circle cx="12" cy="12" r="8"/><path d="M4 12h16"/>'
              '<path d="M12 4c2.5 2.4 3.8 5.1 3.8 8s-1.3 5.6-3.8 8'
              'c-2.5-2.4-3.8-5.1-3.8-8S9.5 6.4 12 4z"/>'),
    "tab": ('<rect x="3" y="6" width="18" height="13" rx="2"/>'
            '<path d="M7 6V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v1"/>'),
    "shield": ('<path d="M12 3l7 3v6c0 4.4-3 7.6-7 9-4-1.4-7-4.6-7-9V6z"/>'
               '<path d="M9.5 12l2 2 3.5-4"/>'),
    "lock": ('<rect x="6" y="11" width="12" height="9" rx="2"/>'
             '<path d="M9 11V8a3 3 0 0 1 6 0v3"/>'),
    "vpn": ('<circle cx="12" cy="12" r="8"/><path d="M9 12l2 2 4-5"/>'
            '<path d="M4 12h2M18 12h2"/>'),
}

_CACHE = {}


def svg_string(name: str, color: str = "#5C6470") -> str:
    body = BODIES.get(name, BODIES["globe"]).replace("@C", color)
    return _SVG_WRAP.replace("@C", color).replace("@B", body)


def sync_assets(folder) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in BODIES:
        path = folder / f"{name}.svg"
        if not path.exists():
            path.write_text(svg_string(name, "#5C6470"), encoding="utf-8")


def _render(svg: str, size: int) -> QPixmap:
    dpr = 2
    px = QPixmap(size * dpr, size * dpr)
    px.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    painter = QPainter(px)
    renderer.render(painter)
    painter.end()
    return px


def icon(name: str, size: int = 16, color: str = "#5C6470") -> QIcon:
    key = (name, size, color)
    if key not in _CACHE:
        _CACHE[key] = QIcon(_render(svg_string(name, color), size))
    return _CACHE[key]


def pixmap(name: str, size: int = 16, color: str = "#5C6470") -> QPixmap:
    return _render(svg_string(name, color), size)


def app_icon() -> QIcon:
    px = QPixmap(64, 64)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#2F5FE0"))
    p.drawRoundedRect(0, 0, 64, 64, 16, 16)
    p.setPen(QColor("#FFFFFF"))
    p.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "SB")
    p.end()
    return QIcon(px)


_SPIN_CACHE = {}


def spinner_frames(size: int = 14, color: str = "#5C6470"):
    key = (size, color)
    if key not in _SPIN_CACHE:
        frames = []
        for i in range(8):
            svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
                   f'<g transform="rotate({i * 45} 12 12)">'
                   f'<path d="M12 4a8 8 0 0 1 8 8" fill="none" stroke="{color}" '
                   'stroke-width="2.4" stroke-linecap="round"/></g></svg>')
            frames.append(_render(svg, size))
        _SPIN_CACHE[key] = frames
    return _SPIN_CACHE[key]


def emoji_pixmap(char: str, size: int = 20) -> QPixmap:
    px = QPixmap(size * 2, size * 2)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setFont(QFont("Segoe UI Emoji", int(size * 1.5)))
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, char)
    p.end()
    return px


def letter_pixmap(char: str, size: int = 20, bg: str = "#E8EEFC",
                  fg: str = "#2F5FE0") -> QPixmap:
    px = QPixmap(size * 2, size * 2)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(bg))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size * 2, size * 2, 8, 8)
    p.setFont(QFont("Segoe UI", int(size * 1.1), QFont.Weight.Bold))
    p.setPen(QColor(fg))
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, (char or "?")[:1].upper())
    p.end()
    return px

# --------------------------------------------------------------------------
# v2 icon additions (kept in one block so the original set stays untouched)
# --------------------------------------------------------------------------
BODIES.update({
    "reader": ('<path d="M4 5.5C6.5 4.5 9.5 4.5 12 6c2.5-1.5 5.5-1.5 8-.5V19'
               'c-2.5-1-5.5-1-8 .5-2.5-1.5-5.5-1.5-8-.5z"/><path d="M12 6v13.5"/>'),
    "focus": ('<circle cx="12" cy="13" r="7"/><path d="M12 9.5V13l2.5 1.5"/>'
              '<path d="M9.5 3.5h5"/>'),
    "play": '<path d="M8 5.5v13l10-6.5z"/>',
    "pause": '<path d="M9 5.5v13"/><path d="M15 5.5v13"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "chevron_down": '<path d="M6 9.5l6 6 6-6"/>',
    "chevron_right": '<path d="M9.5 6l6 6-6 6"/>',
    "warning": ('<path d="M12 4l9 15.5H3z"/><path d="M12 10v4.5"/>'
                '<path d="M12 17.2h.01"/>'),
    "lock_open": ('<rect x="6" y="11" width="12" height="9" rx="2"/>'
                  '<path d="M9 11V8a3 3 0 0 1 5.6-1.5"/>'),
    "copy": ('<rect x="8" y="8" width="11" height="11" rx="2"/>'
             '<path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>'),
    "link": ('<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/>'
             '<path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>'),
    "folder": '<path d="M3.5 7.5a2 2 0 0 1 2-2H10l2 2.5h6.5a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
    "pin": ('<path d="M9 4h6l-1 5 3 3v1.5H7V12l3-3z"/><path d="M12 13.5V20"/>'),
    "sleep": ('<path d="M6 7h5l-5 6h5"/><path d="M14 11h4l-4 5h4"/>'),
    "devtools": '<path d="M8.5 8L4 12l4.5 4"/><path d="M15.5 8L20 12l-4.5 4"/><path d="M13.5 5.5l-3 13"/>',
    "camera": ('<path d="M4 8.5a1.5 1.5 0 0 1 1.5-1.5H8l1.3-2h5.4L16 7h2.5A1.5 1.5 0 0 1 20 8.5V17'
               'a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17z"/><circle cx="12" cy="12.5" r="3"/>'),
    "sun": ('<circle cx="12" cy="12" r="3.6"/><path d="M12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2'
            'M6 6l1.4 1.4M16.6 16.6L18 18M18 6l-1.4 1.4M7.4 16.6L6 18"/>'),
    "bar": '<rect x="3.5" y="5" width="17" height="4" rx="1.5"/><path d="M6 14h4M6 18h8"/>',
    "print": ('<path d="M7 9V4h10v5"/><rect x="4" y="9" width="16" height="7" rx="2"/>'
              '<path d="M7 14h10v6H7z"/>'),
    "code": '<path d="M8.5 8L4 12l4.5 4"/><path d="M15.5 8L20 12l-4.5 4"/>',
    "sparkle": '<path d="M12 4l1.8 5.2L19 11l-5.2 1.8L12 18l-1.8-5.2L5 11l5.2-1.8z"/>',
    "calc": ('<rect x="5" y="3.5" width="14" height="17" rx="2.5"/><path d="M8.5 8h7"/>'
             '<path d="M9 12h.01M12 12h.01M15 12h.01M9 16h.01M12 16h.01M15 16h.01"/>'),
    "bolt": '<path d="M13 3.5L5.5 13.5H11l-1 7 7.5-10H12z"/>',
    "block": '<circle cx="12" cy="12" r="8"/><path d="M6.4 6.4l11.2 11.2"/>',
    "up": '<path d="M12 19V6"/><path d="M6.5 11.5L12 6l5.5 5.5"/>',
    "eye_off": ('<path d="M4 12s3-6 8-6 8 6 8 6-3 6-8 6-8-6-8-6z"/><path d="M4 4l16 16"/>'),
    "grid": ('<rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/>'
             '<rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5"/>'),
    "palette": ('<path d="M12 4a8 8 0 1 0 0 16c1.2 0 1.8-.8 1.8-1.7 0-.6-.4-1-.4-1.6 0-.9.7-1.5 1.6-1.5H17'
                'a3 3 0 0 0 3-3C20 7.2 16.5 4 12 4z"/><path d="M8 11h.01M11 8h.01M15 9h.01"/>'),
    "export": '<path d="M12 15V4"/><path d="M8 8l4-4 4 4"/><path d="M5 13v5a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 18v-5"/>',
    "refresh": '<path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v5h-5"/>',
})

_theme_hooks = []


def register_retheme(fn):
    """Icons are cached per colour, so retheming only needs a cache drop."""
    _theme_hooks.append(fn)


def clear_cache():
    _CACHE.clear()
    _SPIN_CACHE.clear()
