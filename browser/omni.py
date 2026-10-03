"""Address-bar intelligence: turn whatever the user typed into a navigation.

Pure Python (no Qt widgets) so it is trivially unit-testable.
"""
import ast
import math
import operator
import os
import re
from urllib.parse import quote_plus, quote

HOME_URL = "studybrowse://home"

# key -> (label, search URL template, autocomplete URL template or None)
ENGINES = {
    "duckduckgo": ("DuckDuckGo", "https://duckduckgo.com/?q={}",
                   "https://duckduckgo.com/ac/?q={}&type=list"),
    "google": ("Google", "https://www.google.com/search?q={}",
               "https://suggestqueries.google.com/complete/search?client=firefox&q={}"),
    "bing": ("Bing", "https://www.bing.com/search?q={}",
             "https://api.bing.com/osjson.aspx?query={}"),
    "brave": ("Brave Search", "https://search.brave.com/search?q={}",
              "https://search.brave.com/api/suggest?q={}"),
    "startpage": ("Startpage", "https://www.startpage.com/do/dsearch?query={}", None),
    "ecosia": ("Ecosia", "https://www.ecosia.org/search?q={}", None),
}
DEFAULT_ENGINE = "duckduckgo"

# "yt lofi beats" -> YouTube search. Also accepted as "!yt lofi beats".
SHORTCUTS = {
    "g": ("Google", "https://www.google.com/search?q={}"),
    "ddg": ("DuckDuckGo", "https://duckduckgo.com/?q={}"),
    "yt": ("YouTube", "https://www.youtube.com/results?search_query={}"),
    "w": ("Wikipedia", "https://en.wikipedia.org/w/index.php?search={}"),
    "gh": ("GitHub", "https://github.com/search?q={}"),
    "so": ("Stack Overflow", "https://stackoverflow.com/search?q={}"),
    "maps": ("Google Maps", "https://www.google.com/maps/search/{}"),
    "gs": ("Google Scholar", "https://scholar.google.com/scholar?q={}"),
    "mdn": ("MDN", "https://developer.mozilla.org/en-US/search?q={}"),
    "py": ("Python docs", "https://docs.python.org/3/search.html?q={}"),
    "arxiv": ("arXiv", "https://arxiv.org/search/?query={}"),
    "img": ("Google Images", "https://www.google.com/search?tbm=isch&q={}"),
    "tr": ("Google Translate", "https://translate.google.com/?sl=auto&tl=en&text={}"),
    "r": ("Reddit", "https://www.reddit.com/search/?q={}"),
    "a": ("Amazon", "https://www.amazon.com/s?k={}"),
}

_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")
_HOSTPORT = re.compile(
    r"^(localhost|(\d{1,3}\.){3}\d{1,3}|\[[0-9a-fA-F:]+\])(:\d{1,5})?(/.*)?$")
_DOMAIN = re.compile(
    r"^([a-zA-Z0-9\u00a1-\uffff]([a-zA-Z0-9\u00a1-\uffff\-]{0,61}"
    r"[a-zA-Z0-9\u00a1-\uffff])?\.)+[a-zA-Z\u00a1-\uffff]{2,24}"
    r"(:\d{1,5})?([/?#].*)?$")
_WIN_PATH = re.compile(r"^[a-zA-Z]:[\\/]")


def engine_url(key: str) -> str:
    return ENGINES.get(key, ENGINES[DEFAULT_ENGINE])[1]


def engine_label(key: str) -> str:
    return ENGINES.get(key, ENGINES[DEFAULT_ENGINE])[0]


def search_url(query: str, template: str) -> str:
    return template.format(quote_plus(query.strip()))


class Resolved:
    """kind: 'url' | 'search' | 'internal'"""
    __slots__ = ("kind", "url", "label")

    def __init__(self, kind, url, label=""):
        self.kind, self.url, self.label = kind, url, label

    def __repr__(self):
        return f"Resolved({self.kind!r}, {self.url!r}, {self.label!r})"


def resolve(text: str, template: str) -> Resolved | None:
    text = (text or "").strip()
    if not text:
        return None
    low = text.lower()

    if low.startswith("studybrowse:"):
        return Resolved("internal", text)
    if low in ("about:home", "about:newtab"):
        return Resolved("internal", HOME_URL)
    if low == "about:blank":
        return Resolved("url", "about:blank")
    if low.startswith(("view-source:", "chrome://", "file://", "data:",
                       "javascript:", "blob:", "mailto:")):
        # javascript: is never navigated to from the omnibox
        if low.startswith("javascript:"):
            return Resolved("search", search_url(text, template), "Search")
        return Resolved("url", text)

    # Search shortcuts: "yt lofi", "!gh pyside"
    parts = text.split(None, 1)
    if len(parts) == 2:
        key = parts[0].lower().lstrip("!")
        if key in SHORTCUTS and (parts[0].startswith("!") or len(key) <= 6):
            label, tmpl = SHORTCUTS[key]
            return Resolved("search", search_url(parts[1], tmpl), label)

    if _SCHEME.match(text):
        return Resolved("url", text.replace(" ", "%20"))

    if " " in text:
        return Resolved("search", search_url(text, template), "Search")

    if _WIN_PATH.match(text) or text.startswith(("\\\\", "/", "~")):
        path = os.path.expanduser(text)
        if os.path.exists(path):
            from PySide6.QtCore import QUrl
            return Resolved("url", QUrl.fromLocalFile(path).toString())

    if _HOSTPORT.match(text):
        return Resolved("url", "http://" + text)

    if _DOMAIN.match(text):
        return Resolved("url", "https://" + text)

    return Resolved("search", search_url(text, template), "Search")


def looks_like_url(text: str) -> bool:
    r = resolve(text, "{}")
    return bool(r and r.kind in ("url", "internal"))


# --------------------------------------------------------------- calculator
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
          "log": math.log10, "ln": math.log, "abs": abs, "round": round,
          "floor": math.floor, "ceil": math.ceil, "exp": math.exp}
_CONSTS = {"pi": math.pi, "e": math.e}


def _eval(node, depth=0):
    if depth > 24:
        raise ValueError("too deep")
    if isinstance(node, ast.Expression):
        return _eval(node.body, depth + 1)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        a, b = _eval(node.left, depth + 1), _eval(node.right, depth + 1)
        if isinstance(node.op, ast.Pow) and abs(b) > 1000:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](a, b)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand, depth + 1))
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in _FUNCS and len(node.args) == 1 and not node.keywords:
        return _FUNCS[node.func.id](_eval(node.args[0], depth + 1))
    raise ValueError("unsupported")


def calc(text: str):
    """Return a formatted result string for arithmetic input, else None."""
    t = (text or "").strip().rstrip("=").replace("^", "**").replace("×", "*") \
        .replace("÷", "/").replace(",", "")
    if not t or not re.search(r"\d", t):
        return None
    if not re.fullmatch(r"[0-9a-z+\-*/%().\s]+", t):
        return None
    # plain numbers aren't calculations
    if re.fullmatch(r"[\d.\s]+", t):
        return None
    try:
        val = _eval(ast.parse(t, mode="eval"))
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, TypeError):
        return None
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        if val == int(val) and abs(val) < 1e15:
            return str(int(val))
        return f"{val:.10g}"
    return str(val)


def parse_suggestions(payload: bytes, limit=6):
    """Parse OpenSearch-style JSON: ["query", ["s1", "s2", ...]]."""
    import json
    try:
        data = json.loads(payload.decode("utf-8", "replace"))
    except (ValueError, AttributeError):
        return []
    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
        out = []
        for item in data[1]:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict) and item.get("phrase"):
                out.append(str(item["phrase"]))
            if len(out) >= limit:
                break
        return out
    return []
