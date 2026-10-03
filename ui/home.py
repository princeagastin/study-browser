"""Start page + error page, rendered as self-contained HTML.

Security notes
* every dynamic string passes through ``html.escape`` — page titles and URLs
  come from the web and must never be interpreted as markup;
* favicons are inlined from the local cache as data URIs, so opening a new
  tab makes zero third-party requests.
"""
import base64
import html
import time
from datetime import datetime
from urllib.parse import quote

from PySide6.QtCore import QUrl

from browser import omni
from database.storage import epoch
from ui import brand
from ui.theme import TOKENS as T, is_dark

_TIPS = [
    "Press Ctrl+K to open the command palette — every action is one keystroke away.",
    "Type “yt lofi” or “!gh pyside6” in the address bar to search a site directly.",
    "Type a sum like 18*4.5 in the address bar — the answer appears instantly.",
    "Press Ctrl+Alt+R on an article for a distraction-free Reader view.",
    "Start a Focus session and Folio blocks your distracting sites until it ends.",
    "Right-click a tab to pin, group, mute or put it to sleep.",
    "Select text on any page, right-click, and turn it straight into a note.",
    "Ctrl+D saves a page to your library; notes keep their source attached.",
    "Alt+Enter in the address bar opens the result in a new tab.",
]

_icon_cache = {}


def _fav_uri(host: str):
    if not host:
        return ""
    if host in _icon_cache:
        return _icon_cache[host]
    uri = ""
    try:
        from ui.quick_apps import FAVICON_CACHE
        path = FAVICON_CACHE / f"fav_{host}.png"
        if path.exists():
            uri = "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
    except OSError:
        pass
    if uri:
        _icon_cache[host] = uri
    return uri


def _esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def _letter(text) -> str:
    text = (text or "?").strip()
    return _esc(text[:1].upper() or "?")


def _icon(host: str, label: str, cls="ico") -> str:
    uri = _fav_uri(host)
    if uri:
        return f'<span class="{cls}"><img src="{uri}" alt=""></span>'
    return f'<span class="{cls} fb">{_letter(label or host)}</span>'


def _greeting() -> str:
    h = datetime.now().hour
    return ("Good morning" if 5 <= h < 12 else
            "Good afternoon" if 12 <= h < 17 else "Good evening")


def _fmt_dur(seconds: int) -> str:
    m = int(seconds // 60)
    return f"{m // 60}h {m % 60}m" if m >= 60 else f"{m}m"


def _rgba(color: str, a: float) -> str:
    c = color.lstrip("#")
    if len(c) == 6:
        return f"rgba({int(c[0:2], 16)},{int(c[2:4], 16)},{int(c[4:6], 16)},{a})"
    return color


_CSS = """
:root{--bg:@surface;--card:@elev;--field:@field;--line:@hairline;--ink1:@ink1;--ink2:@ink2;--ink3:@ink3;
--acc:@accent;--acch:@accent_hover;--tint:@tint;--font:@font}
*{box-sizing:border-box;margin:0;font-family:var(--font)}
html{color-scheme:@scheme}
body{background:var(--bg);color:var(--ink1);min-height:100vh;padding:0 5vw 64px;
background-image:radial-gradient(900px 380px at 50% -140px,@glow,transparent)}
a{color:inherit;text-decoration:none}
.wrap{max-width:1040px;margin:0 auto}
.top{display:flex;justify-content:space-between;align-items:center;padding:22px 0 0;
color:var(--ink3);font-size:12px}
.chip{display:inline-flex;gap:6px;align-items:center;padding:4px 10px;border-radius:999px;
background:var(--field);font-weight:600}
.hero{text-align:center;padding:46px 0 10px}
.mark{width:54px;height:54px;border-radius:16px;margin:0 auto 16px;display:grid;place-items:center;
background:linear-gradient(140deg,var(--acc),@accent2);color:@accent_ink;font-weight:800;font-size:26px;
box-shadow:0 10px 30px -8px @markglow}
.clock{font-size:54px;font-weight:300;letter-spacing:-.04em;line-height:1}
.greet{color:var(--ink2);font-size:15px;margin-top:8px}
.search{display:flex;align-items:center;gap:10px;max-width:640px;margin:26px auto 0;
background:var(--card);border:1.5px solid var(--line);border-radius:16px;padding:8px 8px 8px 18px;
box-shadow:@shadow;transition:border-color .15s,box-shadow .15s}
.search:focus-within{border-color:var(--acc);box-shadow:@shadowfocus}
.search svg{flex:none;color:var(--ink3)}
.search input{flex:1;border:0;outline:0;background:transparent;color:var(--ink1);font-size:16px;padding:9px 0}
.search input::placeholder{color:var(--ink3)}
.eng{flex:none;font-size:11px;color:var(--ink3);background:var(--field);padding:4px 9px;border-radius:8px;font-weight:600}
.go{width:38px;height:38px;border-radius:11px;border:0;background:var(--acc);color:@accent_ink;font-size:17px;
cursor:pointer;transition:transform .1s,background .15s}
.go:hover{background:var(--acch)}.go:active{transform:scale(.93)}
.hint{color:var(--ink3);font-size:12px;margin-top:12px}
.hint b{font-weight:600;color:var(--ink2)}
.cols{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:26px;margin-top:38px;align-items:start}
@media(max-width:900px){.cols{grid-template-columns:1fr}}
.cap{color:var(--ink3);font-size:10.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin:0 0 11px}
.sec+.sec{margin-top:26px}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:10px}
.tile{display:flex;flex-direction:column;align-items:center;gap:9px;padding:15px 8px 12px;
background:var(--card);border:1px solid var(--line);border-radius:14px;transition:transform .12s,border-color .12s,box-shadow .12s}
.tile:hover{transform:translateY(-2px);border-color:var(--acc);box-shadow:@shadow}
.tile .lbl{font-size:12px;font-weight:600;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ico{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;flex:none;overflow:hidden;background:var(--field)}
.ico img{width:22px;height:22px;object-fit:contain}
.ico.fb{background:var(--tint);color:var(--acc);font-weight:700;font-size:15px}
.ico.sm{width:26px;height:26px;border-radius:8px;font-size:12px}.ico.sm img{width:16px;height:16px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:620px){.grid{grid-template-columns:1fr}}
.card{display:flex;gap:11px;align-items:center;background:var(--card);border:1px solid var(--line);
border-radius:13px;padding:11px 13px;min-width:0;transition:border-color .12s,transform .12s}
.card:hover{border-color:var(--acc);transform:translateY(-1px)}
.card .b{min-width:0}.t{font-size:13px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.m{font-size:11.5px;color:var(--ink3);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.side .box{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;margin-bottom:12px}
.box h3{font-size:10.5px;font-weight:700;letter-spacing:.1em;color:var(--ink3);margin-bottom:10px;text-transform:uppercase}
.row{display:flex;gap:9px;align-items:center;padding:6px 4px;border-radius:9px;min-width:0}
.row:hover{background:var(--field)}.row .t{font-size:12.5px;flex:1}.row .meta{font-size:11px;color:var(--ink3);flex:none;max-width:90px;overflow:hidden;text-overflow:ellipsis}
.empty{color:var(--ink3);font-size:12.5px;line-height:1.5;padding:2px 2px}
.focus .big{font-size:26px;font-weight:650;letter-spacing:-.02em}
.focus .sub{color:var(--ink3);font-size:12px;margin:2px 0 12px}
.btns{display:flex;gap:7px;flex-wrap:wrap}
.btn{border:1px solid var(--line);background:var(--field);color:var(--ink1);border-radius:9px;padding:7px 11px;
font-size:12px;font-weight:600;cursor:pointer}
.btn:hover{border-color:var(--acc);color:var(--acc)}
.btn.p{background:var(--acc);border-color:var(--acc);color:@accent_ink}.btn.p:hover{background:var(--acch);color:@accent_ink}
.stats{display:flex;text-align:center}.stats a{flex:1;padding:4px;border-radius:9px}.stats a:hover{background:var(--field)}
.stats b{display:block;font-size:20px}.stats span{font-size:11px;color:var(--ink3)}
.tip{background:var(--tint);border-radius:13px;padding:13px 15px;font-size:12.5px;color:var(--ink2);line-height:1.55}
.tip b{color:var(--acc)}
.banner{margin:20px auto 0;max-width:640px;text-align:center;padding:10px 14px;border-radius:12px;
background:@privbg;color:@privtext;font-size:12.5px}
"""


def _css(private: bool) -> str:
    dark = is_dark() or private
    acc = T["priv_accent"] if private else T["accent"]
    hov = T["priv_accent"] if private else T["accent_hover"]
    surface = "#1A1D29" if private else T["surface"]
    values = {
        "@surface": surface, "@elev": "#232838" if private else T["elev"],
        "@field": "#2A2F42" if private else T["field"],
        "@hairline": "#343A52" if private else T["hairline"],
        "@ink1": "#E6E9F5" if private else T["ink1"],
        "@ink2": "#AAB1CC" if private else T["ink2"],
        "@ink3": "#767E9C" if private else T["ink3"],
        "@accent_hover": hov, "@accent_ink": "#0B0E14" if dark else "#FFFFFF",
        "@accent2": _rgba(acc, 0.65) if False else acc,
        "@accent": acc,
        "@tint": _rgba(acc, 0.16),
        "@glow": _rgba(acc, 0.13 if dark else 0.10),
        "@markglow": _rgba(acc, 0.45),
        "@scheme": "dark" if dark else "light",
        "@privbg": T["priv_bg"], "@privtext": T["priv_text"],
        "@shadow": "0 1px 2px rgba(0,0,0,.25)" if dark else
                   "0 1px 2px rgba(15,23,42,.05),0 6px 18px rgba(15,23,42,.06)",
        "@shadowfocus": f"0 10px 34px {_rgba(acc, 0.22)}",
        "@font": T["font"],
    }
    css = _CSS
    for key in sorted(values, key=len, reverse=True):
        css = css.replace(key, values[key])
    return css


_SEARCH_ICON = ("<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
                "stroke-width='1.9' stroke-linecap='round'><circle cx='11' cy='11' r='6.5'/>"
                "<path d='M16 16l4.5 4.5'/></svg>")


def home_html(storage, private: bool, session, dark: bool = False, focus_state=None) -> str:
    engine = storage.get_setting("search_engine", omni.DEFAULT_ENGINE)
    apps = storage.list_apps()
    recent = storage.recent_history(4) if not private else []
    saved = storage.list_saved()[:5]
    counts = storage.library_counts()
    sess = None if private else session.load_session()
    fstats = storage.focus_stats()
    tip = _TIPS[int(time.time() // 86400) % len(_TIPS)]
    now = datetime.now()

    p = [f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
         f"<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; "
         f"img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'\">"
         f"<title>New tab</title><style>{_css(private)}</style></head><body><div class='wrap'>"]
    p.append(f"<div class='top'><span class='chip'>{'🕶 Private session' if private else _esc(now.strftime('%A, %d %B'))}</span>"
             f"<span>{_esc(brand.NAME)}</span></div>")
    if private:
        p.append("<div class='banner'>History, cookies and cache from this tab are not kept. "
                 "Downloads and saved pages are.</div>")
    p.append(
        "<div class='hero'><div class='mark'>" + _esc(brand.NAME[:1]) + "</div>"
        f"<div class='clock' id='clk'>{now.strftime('%H:%M')}</div>"
        f"<div class='greet'>{_greeting()}</div>"
        f"<form class='search' onsubmit='return go()'>{_SEARCH_ICON}"
        f"<input id='q' autofocus autocomplete='off' spellcheck='false' "
        f"placeholder='Search {_esc(omni.engine_label(engine))} or type an address'>"
        f"<span class='eng'>{_esc(omni.engine_label(engine))}</span>"
        f"<button class='go' type='submit'>→</button></form>"
        "<div class='hint'>Try <b>yt lofi</b> · <b>!gh pyside6</b> · <b>18*4.5</b> · press <b>/</b> to search</div></div>")

    p.append("<div class='cols'><div class='main'>")
    if sess and sess.get("tabs"):
        n = len(sess["tabs"])
        p.append("<div class='sec'><div class='cap'>Previous session</div><div class='grid'>"
                 "<a class='card' href='studybrowse://action/restore'><span class='ico fb'>↺</span>"
                 f"<div class='b'><div class='t'>Restore {n} tab{'s' if n != 1 else ''}</div>"
                 "<div class='m'>Pick up where you left off</div></div></a></div></div>")

    p.append("<div class='sec'><div class='cap'>Quick access</div><div class='tiles'>")
    for app in apps[:14]:
        host = QUrl(app["url"]).host()
        field = app["icon"] or "letter"
        if field.startswith("emoji:"):
            ico = f"<span class='ico fb' style='font-size:18px'>{_esc(field[6:])}</span>"
        else:
            ico = _icon(host, app["name"])
        p.append(f"<a class='tile' href='{_esc(app['url'])}'>{ico}<span class='lbl'>{_esc(app['name'])}</span></a>")
    if not apps:
        p.append("<div class='empty'>No quick apps yet — add one with the + on the left rail.</div>")
    p.append("</div></div>")

    p.append("<div class='sec'><div class='cap'>Continue browsing</div>")
    if recent:
        p.append("<div class='grid'>")
        for row in recent:
            host = QUrl(row["url"]).host()
            when = time.strftime("%H:%M", time.localtime(epoch(row["visit_time"])))
            p.append(f"<a class='card' href='{_esc(row['url'])}'>{_icon(host, row['title'])}"
                     f"<div class='b'><div class='t'>{_esc(row['title'] or host)}</div>"
                     f"<div class='m'>{_esc(host)} · {when}</div></div></a>")
        p.append("</div>")
    else:
        p.append("<div class='empty'>Pages you visit show up here so you can pick up where you left off.</div>")
    p.append("</div></div>")

    p.append("<div class='side'>")
    today = _fmt_dur(fstats["today_seconds"]) if fstats["today_seconds"] else "0m"
    p.append("<div class='box focus'><h3>Focus</h3>"
             f"<div class='big'>{today}</div>"
             f"<div class='sub'>focused today · {fstats['today_sessions']} session"
             f"{'s' if fstats['today_sessions'] != 1 else ''}</div><div class='btns'>"
             "<a class='btn p' href='studybrowse://action/focus?min=25&brk=5'>25 min</a>"
             "<a class='btn' href='studybrowse://action/focus?min=50&brk=10'>50 min</a>"
             "<a class='btn' href='studybrowse://action/focus?min=90&brk=20'>90 min</a></div></div>")
    p.append("<div class='box'><h3>Recent sources</h3>")
    if saved:
        for row in saved:
            host = QUrl(row["url"]).host()
            p.append(f"<a class='row' href='{_esc(row['url'])}'>{_icon(host, row['title'], 'ico sm')}"
                     f"<span class='t'>{_esc(row['title'] or host)}</span>"
                     f"<span class='meta'>{_esc(host)}</span></a>")
    else:
        p.append("<div class='empty'>Nothing saved yet — press Ctrl+D on any page to keep it.</div>")
    p.append("</div>")
    p.append("<div class='box'><h3>Library</h3><div class='stats'>"
             f"<a href='studybrowse://action/saved'><b>{counts['saved']}</b><span>Saved</span></a>"
             f"<a href='studybrowse://action/notes'><b>{counts['notes']}</b><span>Notes</span></a>"
             f"<a href='studybrowse://action/history'><b>{counts['history']}</b><span>Visits</span></a>"
             "</div></div>")
    p.append(f"<div class='tip'><b>Tip —</b> {_esc(tip)}</div></div></div></div>")
    p.append("""<script>
function go(){var v=document.getElementById('q').value.trim();if(!v)return false;
location.href='studybrowse://action/search?q='+encodeURIComponent(v);return false}
document.addEventListener('keydown',function(e){if(e.key==='/'&&document.activeElement.id!=='q'){e.preventDefault();document.getElementById('q').focus()}});
setInterval(function(){var d=new Date(),c=document.getElementById('clk');if(c)c.textContent=('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2)},10000);
</script></body></html>""")
    return "".join(p)


def error_html(url: str, dark: bool = False, reason: str = "") -> str:
    host = html.escape(url.split("//", 1)[1].split("/", 1)[0] if "//" in url else url)
    reason = html.escape(reason or "")
    title, advice = "This page didn’t load", "Check your connection, then try again."
    low = reason.lower()
    if "name_not_resolved" in low:
        title, advice = "Can’t find that site", f"“{host}” doesn’t seem to exist, or your DNS isn’t responding. Check the spelling."
    elif "internet_disconnected" in low or "network_changed" in low:
        title, advice = "You’re offline", "Reconnect to a network and try again."
    elif "connection_refused" in low or "connection_reset" in low or "connection_closed" in low:
        title, advice = "The site refused the connection", "The server may be down or blocking requests."
    elif "timed_out" in low:
        title, advice = "The site took too long to respond", "It might be down or your connection is slow."
    elif "cert" in low or "ssl" in low:
        title, advice = "Secure connection failed", "The site’s security certificate could not be verified."
    css = _css(False)
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>Can’t reach this page</title><style>{css}
body{{display:flex;align-items:center;justify-content:center;height:100vh;padding:0}}
.box{{text-align:center;max-width:460px;padding:0 20px}}
h2{{font-size:21px;font-weight:650;margin:18px 0 8px}}p{{color:var(--ink2);font-size:14px;line-height:1.6}}
code{{display:inline-block;margin-top:14px;font-size:11.5px;color:var(--ink3);background:var(--field);padding:4px 9px;border-radius:7px}}
.btns{{margin-top:22px;display:flex;gap:8px;justify-content:center}}
.btns a{{padding:9px 20px;border-radius:10px;font-size:13px;font-weight:600;border:1px solid var(--line);background:var(--field)}}
.btns a.p{{background:var(--acc);border-color:var(--acc);color:{T['accent_ink']}}}
</style></head><body><div class='box'>
<svg width='54' height='54' viewBox='0 0 24 24' fill='none' stroke='{T['danger']}' stroke-width='1.6' stroke-linecap='round'>
<circle cx='12' cy='12' r='8.5'/><path d='M12 7.5v5.2M12 16.3h.01'/></svg>
<h2>{title}</h2><p>{advice}</p>{f'<code>{reason}</code>' if reason else ''}
<div class='btns'><a class='p' href='studybrowse://action/retry?url={quote(url)}'>Try again</a>
<a href='studybrowse://home'>Go to start page</a></div></div></body></html>"""
