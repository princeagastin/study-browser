# Folio (StudyBrowse) — v2.0

A research-first desktop browser. PySide6 + Qt WebEngine + SQLite.

## Run
    .\venv\Scripts\python.exe main.py          # Windows
    python main.py                              # elsewhere (pip install -r requirements.txt)
    python main.py https://example.com          # open an address on launch

## What's new in 2.0

**Design system** — one token file (`ui/theme.py`) drives everything: light, dark
or follow-the-OS theme, six accent colours, all applied *live* (no restart).
Reusable widgets (`ui/widgets.py`): toggle switches, segmented controls, rounded
menus, soft shadows, toasts, two-line list rows.

**Smarter address bar** (`browser/omni.py`, `ui/suggest.py`)
- Live dropdown: open tabs, saved pages, history (ranked by frecency), quick apps
  and search-engine suggestions; inline autocomplete of sites you visit.
- Inline calculator: type `18*4.5` or `sqrt(144)*3` (safe AST evaluator).
- Search shortcuts: `yt lofi`, `!gh pyside6`, `w python`, `so`, `mdn`, `arxiv`…
- Handles localhost, IPs, ports, unicode domains and local file paths.
- Six search engines; suggestions are never requested from private tabs.

**Focus mode** (`ui/focus.py`) — Pomodoro timer in the toolbar (25/50/90 min) that
blocks distracting sites for the session, tracks daily focus time, editable blocklist.

**Reader mode** (`ui/reader.py`) — Ctrl+Alt+R. Whitelist-sanitised extraction,
font size / width / serif / light-sepia-dark controls, read-time and byline.

**Downloads manager** (`ui/downloads.py`) — live progress, speed and ETA, pause /
resume / cancel, history in SQLite, "show in folder", ask-where option.

**Tabs** — sleeping tabs (auto after N minutes), correct audio indicators,
per-site zoom that is remembered, rich right-click menu (open link in
background/private tab, save link, copy image, view source, inspect), middle-click
background tabs, wheel-scroll tab strip.

**Security** — HTTPS-only mode, certificate-error interstitial (no silent
bypass), HTTP auth dialog, Global Privacy Control header, per-site Shield
exceptions, Shield categories (ads / analytics / cross-site tracking) with
per-site stats, local-network addresses no longer flagged as dangerous,
all start-page text HTML-escaped, favicons served from a local cache.

**More** — bookmarks bar (Ctrl+Shift+O), embedded DevTools (F12), link-hover
status bubble, web-content fullscreen (YouTube etc.), screenshots, PDF export,
notes → Markdown export, bookmarks → HTML export, fuzzy command palette
(Ctrl+K), sidebar Settings (Ctrl+,), keyboard-shortcut sheet.

## Fixes
- Pressed-button opacity effect (could crash next to WebEngine) replaced by QSS states.
- `rgba()` theme colours were invalid `QColor`s (black pinned tabs / hover).
- Error pages now appear for real network failures only (not 404s or aborts).
- Embedded-webview user-agent token removed so Google sign-in works.
- Original start page and error page did not escape page titles / URLs.

## Notes
- `studybrowse.db` is never deleted; new tables are created additively
  (`downloads`, `focus_sessions`, `site_settings`) and existing data is untouched.
- Cookies/logins use the same named WebEngine profile as before.
- `assets/icons/*.svg` are generated on first launch.
