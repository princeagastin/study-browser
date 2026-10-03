from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QWidgetAction, QWidget, QHBoxLayout, QToolButton,
                               QLabel)

from ui import icons, brand
from ui.theme import TOKENS as T
from ui.widgets import RoundMenu


class MenuContext:
    def __init__(self):
        self.actions = {}
        self.zoom_get = lambda: 100
        self.fullscreen = False
        self.rail_visible = True
        self.bookmarks_bar = False
        self.recent_closed = []
        self.shield_mode = "standard"
        self.vpn_state = "Disconnected"
        self.dark = False
        self.reader_ok = False
        self.focus_active = False
        self.devtools = False


def popup_under_menu(menu, anchor):
    hint = menu.sizeHint()
    bottom_left = anchor.mapToGlobal(QPoint(0, anchor.height()))
    bottom_right = anchor.mapToGlobal(QPoint(anchor.width(), anchor.height()))
    pos = QPoint(bottom_right.x() - hint.width(), bottom_left.y() + 2)
    screen = QGuiApplication.screenAt(
        anchor.mapToGlobal(QPoint(anchor.width() // 2, anchor.height() // 2)))
    if screen is not None:
        geo = screen.availableGeometry()
        pos.setX(min(max(pos.x(), geo.left() + 8),
                     max(geo.left() + 8, geo.right() - hint.width() - 8)))
        pos.setY(min(pos.y(), max(geo.top() + 8, geo.bottom() - hint.height() - 8)))
    return menu.exec(pos)


def build_overflow_menu(ctx: MenuContext) -> RoundMenu:
    menu = RoundMenu()
    a = ctx.actions

    def item(icon_name, label, key, shortcut="", checkable=False, checked=False,
             enabled=True, target=None):
        fn = a.get(key)
        if fn is None:
            return None
        act = (target or menu).add(icon_name, label, fn, shortcut, enabled)
        if checkable:
            act.setCheckable(True)
            act.setChecked(checked)
        return act

    menu.section("Tabs")
    item("plus", "New Tab", "new_tab", "Ctrl+T")
    item("mask", "New Private Tab", "new_private", "Ctrl+Shift+P")
    item("restore", "Reopen Closed Tab", "reopen", "Ctrl+Shift+T")
    open_url = a.get("open_url")
    if ctx.recent_closed and open_url is not None:
        sub = menu.submenu("history", "Recently Closed")
        for entry in ctx.recent_closed:
            act = sub.addAction((entry["title"] or entry["url"])[:52].replace("&", "&&"),
                                lambda _c=False, u=entry["url"],
                                p=entry["private"]: open_url(u, p))
            act.setToolTip(entry["url"])
    item("sleep", "Put Background Tabs to Sleep", "sleep_tabs")
    menu.addSeparator()

    menu.section("Page")
    item("star", "Save / Unsave Page", "toggle_save", "Ctrl+D")
    item("note_add", "Create Note from Page", "create_note", "Ctrl+Alt+N")
    item("reader", "Reader Mode", "reader", "Ctrl+Alt+R", enabled=ctx.reader_ok)
    item("find", "Find in Page", "find", "Ctrl+F")
    sub = menu.submenu("export", "Save && Share")
    item("pdf", "Save Page as PDF", "pdf", "Ctrl+P", target=sub)
    item("camera", "Screenshot Visible Area", "screenshot", target=sub)
    item("copy", "Copy Page Address", "copy_url", target=sub)
    item("external", "Open in External Browser", "external", target=sub)
    sub = menu.submenu("code", "Developer")
    item("code", "View Page Source", "view_source", "Ctrl+U", target=sub)
    item("devtools", "Developer Tools", "devtools", "F12", checkable=True,
         checked=ctx.devtools, target=sub)
    menu.addSeparator()

    menu.section("Workspace")
    sub = menu.submenu("saved", "Library")
    item("saved", "Saved Pages", "panel_saved", "Ctrl+Shift+B", target=sub)
    item("notes", "Study Notes", "panel_notes", "Ctrl+Alt+N", target=sub)
    item("history", "Browsing History", "panel_history", "Ctrl+H", target=sub)
    item("download", "Downloads", "downloads", "Ctrl+J", target=sub)
    item("focus", "Stop Focus Session" if ctx.focus_active else "Start Focus Session",
         "focus_toggle", "Ctrl+Shift+F")

    sub = menu.submenu("shield", "Privacy && Security")
    shield_fn = a.get("shield_mode")
    if shield_fn is not None:
        ssub = sub.submenu("shield", f"Shield: {ctx.shield_mode.capitalize()}")
        for mode in ("standard", "strict", "off"):
            act = ssub.addAction(mode.capitalize(),
                                 lambda _c=False, m=mode: shield_fn(m))
            act.setCheckable(True)
            act.setChecked(ctx.shield_mode == mode)
    item("info", "Site && Privacy Report", "site_info", target=sub)
    vpn_fn = a.get("vpn_mode")
    if vpn_fn is not None:
        vsub = sub.submenu("vpn", f"Tunnel: {ctx.vpn_state}")
        for key, label, state in (("off", "Off", "Disconnected"),
                                  ("system", "System Proxy", "System proxy"),
                                  ("manual", "Custom Tunnel…", None)):
            act = vsub.addAction(label, lambda _c=False, k=key: vpn_fn(k))
            act.setCheckable(True)
            act.setChecked(state is not None and ctx.vpn_state == state)

    view = menu.submenu("full", "View")
    zoom_in = a.get("zoom_in", lambda: None)
    zoom_out = a.get("zoom_out", lambda: None)
    zoom_reset = a.get("zoom_reset", lambda: None)
    zw = QWidget(view)
    zl = QHBoxLayout(zw)
    zl.setContentsMargins(12, 4, 12, 4)
    zl.setSpacing(6)
    zl.addWidget(QLabel("Zoom"), 1)
    zout = QToolButton(zw)
    zout.setObjectName("tiny")
    zout.setIcon(icons.icon("zoom_out", 14, T["ink2"]))
    zout.clicked.connect(lambda _c=False: zoom_out())
    zpct = QToolButton(zw)
    zpct.setObjectName("link")
    zpct.setText(f"{ctx.zoom_get()}%")
    zpct.setMinimumWidth(48)
    zpct.setToolTip("Reset zoom")
    zpct.clicked.connect(lambda _c=False: (zoom_reset(), zpct.setText("100%")))
    zin = QToolButton(zw)
    zin.setObjectName("tiny")
    zin.setIcon(icons.icon("zoom_in", 14, T["ink2"]))
    zin.clicked.connect(lambda _c=False: zoom_in())
    for w in (zout, zpct, zin):
        zl.addWidget(w)
    za = QWidgetAction(view)
    za.setDefaultWidget(zw)
    view.addAction(za)
    view.addSeparator()
    item("moon", "Dark Mode", "toggle_dark", checkable=True, checked=ctx.dark, target=view)
    item("full_exit" if ctx.fullscreen else "full",
         "Exit Full Screen" if ctx.fullscreen else "Full Screen", "fullscreen", "F11",
         target=view)
    item("bar", "Bookmarks Bar", "toggle_bookmarks", "Ctrl+Shift+O",
         checkable=True, checked=ctx.bookmarks_bar, target=view)
    item("grid", "Quick Apps Rail", "toggle_rail", checkable=True,
         checked=ctx.rail_visible, target=view)
    menu.addSeparator()

    item("command", "Command Palette", "palette", "Ctrl+K")
    item("settings", "Settings…", "settings", "Ctrl+,")
    sub = menu.submenu("info", "Help && Data")
    item("keyboard", "Keyboard Shortcuts", "shortcuts", target=sub)
    item("trash", "Clear History…", "clear_history", target=sub)
    item("info", f"About {brand.NAME}", "about", target=sub)
    return menu
