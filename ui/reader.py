"""Reader mode: extract the main article from a page and re-render it.

Extraction runs *inside* the page (JS) and returns a whitelist-sanitised HTML
string built node-by-node — no innerHTML copying, no attributes other than
href/src/alt survive, and javascript: URLs are dropped. Python then wraps it
in a typography-first template.
"""
import html
import json

EXTRACT_JS = r"""
(function () {
  var ALLOWED = {P:1,H1:1,H2:1,H3:1,H4:1,UL:1,OL:1,LI:1,BLOCKQUOTE:1,PRE:1,CODE:1,
    EM:1,I:1,STRONG:1,B:1,A:1,IMG:1,FIGURE:1,FIGCAPTION:1,BR:1,HR:1,SUB:1,SUP:1,
    TABLE:1,THEAD:1,TBODY:1,TR:1,TD:1,TH:1,SPAN:1,DIV:1,SECTION:1,ARTICLE:1,MARK:1};
  var DROP = {SCRIPT:1,STYLE:1,NOSCRIPT:1,NAV:1,ASIDE:1,FOOTER:1,FORM:1,IFRAME:1,
    BUTTON:1,INPUT:1,SELECT:1,TEXTAREA:1,SVG:1,CANVAS:1,VIDEO:1,AUDIO:1,OBJECT:1,
    EMBED:1,DIALOG:1,TEMPLATE:1,HEADER:1,LINK:1,META:1};
  var JUNK = /(comment|share|social|sidebar|related|promo|advert|sponsor|newsletter|subscribe|cookie|popup|modal|breadcrumb|toolbar|footer|menu|paywall|outbrain|taboola)/i;

  function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  function text(n){return (n.textContent||'').replace(/\s+/g,' ').trim();}
  function linkDensity(n){
    var t=text(n).length; if(!t) return 1;
    var l=0, a=n.getElementsByTagName('a');
    for (var i=0;i<a.length;i++) l+=text(a[i]).length;
    return l/t;
  }
  function junky(n){
    var s=(n.id||'')+' '+(typeof n.className==='string'?n.className:'');
    return JUNK.test(s);
  }
  function score(n){
    var ps=n.querySelectorAll('p'), s=0;
    for (var i=0;i<ps.length;i++){
      var t=text(ps[i]);
      if (t.length<40) continue;
      s += Math.min(t.length,400)/40 + (t.split(',').length-1);
    }
    return s*(1-linkDensity(n)*0.8);
  }
  var pool=document.querySelectorAll('article,main,[role=main],section,div');
  var best=null,bestScore=0;
  for (var i=0;i<pool.length;i++){
    var n=pool[i];
    if (junky(n) && n.tagName!=='ARTICLE') continue;
    var sc=score(n);
    if (n.tagName==='ARTICLE') sc*=1.25;
    if (sc>bestScore){bestScore=sc;best=n;}
  }
  if(!best||bestScore<12) return null;

  function abs(u){try{return new URL(u,document.baseURI).href;}catch(e){return '';}}
  function clean(n){
    if (n.nodeType===3) return esc(n.nodeValue);
    if (n.nodeType!==1) return '';
    var tag=n.tagName;
    if (DROP[tag]) return '';
    if (junky(n) && !/^(ARTICLE|SECTION|P|H\d)$/.test(tag)) return '';
    var kids='';
    for (var c=n.firstChild;c;c=c.nextSibling) kids+=clean(c);
    if (!ALLOWED[tag]) return kids;
    var t=tag.toLowerCase();
    if (tag==='DIV'||tag==='SECTION'||tag==='ARTICLE'||tag==='SPAN') return kids;
    if (tag==='BR'||tag==='HR') return '<'+t+'>';
    if (tag==='IMG'){
      var src=n.currentSrc||n.getAttribute('data-src')||n.src;
      if(!src||/^data:/.test(src)&&src.length<200) return '';
      if ((n.naturalWidth&&n.naturalWidth<80)||(n.width&&n.width<60)) return '';
      return '<img src="'+esc(abs(src)).replace(/"/g,'&quot;')+'" alt="'+esc(n.alt||'').replace(/"/g,'&quot;')+'">';
    }
    if (!kids.replace(/<[^>]*>/g,'').trim() && tag!=='TD' && tag!=='TH') return '';
    if (tag==='A'){
      var h=abs(n.getAttribute('href')||'');
      if(!/^https?:/i.test(h)) return kids;
      return '<a href="'+esc(h).replace(/"/g,'&quot;')+'" rel="noopener">'+kids+'</a>';
    }
    return '<'+t+'>'+kids+'</'+t+'>';
  }
  var body=clean(best);
  var plain=body.replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
  if (plain.length<300) return null;
  function meta(sel,attr){var e=document.querySelector(sel);return e?(e.getAttribute(attr||'content')||''):'';}
  var h1=document.querySelector('h1');
  return JSON.stringify({
    title: meta('meta[property="og:title"]')||(h1?text(h1):'')||document.title,
    byline: meta('meta[name="author"]')||meta('meta[property="article:author"]'),
    site: meta('meta[property="og:site_name"]')||location.hostname,
    words: plain.split(' ').length,
    html: body
  });
})();
"""


def _words_to_minutes(words: int) -> int:
    return max(1, round(words / 220))


_CSS = """
:root{--bg:@bg;--fg:@fg;--muted:@muted;--line:@line;--accent:@accent;--size:19px;--width:680px;--font:@serif}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--font);
transition:background .2s,color .2s}
.bar{position:sticky;top:0;z-index:5;display:flex;gap:6px;align-items:center;justify-content:center;
padding:10px 14px;background:var(--bg);border-bottom:1px solid var(--line);
font:13px/1 'Segoe UI',system-ui,sans-serif}
.bar button,.bar a.exit{border:1px solid var(--line);background:transparent;color:var(--fg);
border-radius:8px;padding:6px 10px;font:inherit;cursor:pointer;text-decoration:none}
.bar button:hover,.bar a.exit:hover{border-color:var(--accent);color:var(--accent)}
.bar button.on{background:var(--accent);border-color:var(--accent);color:#fff}
.bar .sp{flex:1}
.bar .grp{display:flex;gap:4px}
article{max-width:var(--width);margin:0 auto;padding:44px 22px 120px;
font-size:var(--size);line-height:1.72}
.meta{font:13px/1.4 'Segoe UI',system-ui,sans-serif;color:var(--muted);margin-bottom:10px}
h1.title{font-size:2.05em;line-height:1.18;letter-spacing:-.015em;margin:.2em 0 .35em}
h1,h2,h3,h4{line-height:1.25;margin:1.6em 0 .5em}
p{margin:0 0 1.15em}
a{color:var(--accent)}
img{max-width:100%;height:auto;border-radius:10px;margin:.6em 0;display:block}
blockquote{margin:1.2em 0;padding:.2em 1.1em;border-left:3px solid var(--accent);color:var(--muted)}
pre,code{font-family:'Cascadia Code',Consolas,monospace;font-size:.86em}
pre{background:rgba(127,127,127,.12);padding:14px;border-radius:10px;overflow:auto}
code{background:rgba(127,127,127,.14);padding:1px 5px;border-radius:5px}
pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;font-size:.9em}
td,th{border:1px solid var(--line);padding:6px 9px}
hr{border:none;border-top:1px solid var(--line);margin:2em 0}
figcaption{font-size:.8em;color:var(--muted)}
"""

_THEMES = {
    "light": ("#FBFBFA", "#1D2026", "#6B7280", "#E6E4DF"),
    "sepia": ("#F4ECD8", "#3B3226", "#7A6A55", "#DDD0B3"),
    "dark": ("#15171C", "#DDE1E8", "#8A93A3", "#2A2E37"),
}

_JS = """
(function(){
  var root=document.documentElement, S={size:19,width:680,serif:1,theme:'@theme'};
  var T=@themes;
  function apply(){
    root.style.setProperty('--size',S.size+'px');
    root.style.setProperty('--width',S.width+'px');
    root.style.setProperty('--font',S.serif?@serif:@sans);
    var t=T[S.theme]; root.style.setProperty('--bg',t[0]);root.style.setProperty('--fg',t[1]);
    root.style.setProperty('--muted',t[2]);root.style.setProperty('--line',t[3]);
    document.querySelectorAll('[data-theme]').forEach(function(b){b.classList.toggle('on',b.dataset.theme===S.theme)});
    document.getElementById('ser').classList.toggle('on',!!S.serif);
  }
  window.rd=function(k,v){
    if(k==='size') S.size=Math.max(14,Math.min(30,S.size+v));
    if(k==='width') S.width=Math.max(480,Math.min(980,S.width+v));
    if(k==='serif') S.serif=S.serif?0:1;
    if(k==='theme') S.theme=v;
    apply();
  };
  apply();
})();
"""


def build_page(data: dict, url: str, dark: bool = False) -> str:
    theme = "dark" if dark else "light"
    bg, fg, muted, line = _THEMES[theme]
    serif = "Georgia,'Iowan Old Style','Times New Roman',serif"
    sans = "'Segoe UI Variable Text','Segoe UI',system-ui,sans-serif"
    css = (_CSS.replace("@bg", bg).replace("@fg", fg).replace("@muted", muted)
           .replace("@line", line).replace("@accent", "#4F7BFF")
           .replace("@serif", serif))
    js = (_JS.replace("@themes", json.dumps(_THEMES))
          .replace("@theme", theme)
          .replace("@serif", json.dumps(serif))
          .replace("@sans", json.dumps(sans)))
    body_html = data.get("html", "")
    import re
    m = re.match(r"\s*<h1>(.*?)</h1>", body_html, re.S)
    if m:
        lead = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip().lower()
        want = (data.get("title") or "").strip().lower()
        if lead and want and (lead in want or want in lead):
            body_html = body_html[m.end():]
    title = html.escape(data.get("title") or "Untitled")
    site = html.escape(data.get("site") or "")
    byline = html.escape(data.get("byline") or "")
    mins = _words_to_minutes(int(data.get("words") or 0))
    meta = " · ".join(x for x in (site, byline, f"{mins} min read") if x)
    safe_url = html.escape(url, quote=True)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src * data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; font-src data:">
<title>Reader — {title}</title><style>{css}</style></head><body>
<div class="bar">
  <a class="exit" href="studybrowse://action/exitreader">✕ Exit reader</a><span class="sp"></span>
  <div class="grp"><button onclick="rd('size',-1)">A−</button><button onclick="rd('size',1)">A+</button></div>
  <div class="grp"><button onclick="rd('width',-60)">Narrow</button><button onclick="rd('width',60)">Wide</button></div>
  <button id="ser" onclick="rd('serif')">Serif</button>
  <div class="grp"><button data-theme="light" onclick="rd('theme','light')">Light</button>
  <button data-theme="sepia" onclick="rd('theme','sepia')">Sepia</button>
  <button data-theme="dark" onclick="rd('theme','dark')">Dark</button></div>
</div>
<article><div class="meta">{meta}</div><h1 class="title">{title}</h1>
{body_html}</article><script>{js}</script></body></html>"""


def parse_result(raw):
    """runJavaScript result -> dict | None"""
    if not raw or not isinstance(raw, str):
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) and data.get("html") else None
