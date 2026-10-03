import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _resolve_db_path() -> Path:
    env = os.environ.get("STUDYBROWSE_DB")
    if env:
        return Path(env)
    root_db = ROOT / "studybrowse.db"
    cwd_db = Path.cwd() / "studybrowse.db"
    if not root_db.exists() and cwd_db.exists():
        return cwd_db
    return root_db


def _cols(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return {r[1] for r in cur.fetchall()}


def epoch(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    text = str(value).split(".")[0].strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
                "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).timestamp()
        except ValueError:
            continue
    return 0.0


_SPECS = {
    "history": [
        ("url", ("address", "link", "site_url", "page_url"), "TEXT"),
        ("title", ("name", "page_title"), "TEXT"),
        ("visit_time", ("timestamp", "visited_at", "visit_date",
                        "visited_on", "last_visit", "last_visited",
                        "datetime", "time", "date", "ts", "created_at",
                        "created", "visited"), "REAL"),
        ("visit_count", ("count", "visits", "hit_count"),
         "INTEGER DEFAULT 1"),
    ],
    "saved_pages": [
        ("url", ("address", "link", "page_url", "site_url"), "TEXT"),
        ("title", ("name", "page_title"), "TEXT"),
        ("created_at", ("created", "saved_at", "date_added", "timestamp",
                        "time", "date"), "REAL"),
        ("tag", ("label", "category", "folder"), "TEXT"),
    ],
    "notes": [
        ("title", ("name", "heading"), "TEXT"),
        ("content", ("body", "text", "note", "note_text"), "TEXT"),
        ("source_url", ("url", "page_url", "link", "source"), "TEXT"),
        ("source_title", ("page_title", "source_name"), "TEXT"),
        ("created_at", ("created", "date_created", "timestamp"), "REAL"),
        ("updated_at", ("updated", "modified", "last_modified",
                        "date_updated"), "REAL"),
    ],
    "quick_apps": [
        ("name", ("label", "title", "app_name"), "TEXT"),
        ("url", ("address", "link", "target", "app_url"), "TEXT"),
        ("icon", ("emoji", "icon_text", "icon_char", "image"), "TEXT"),
        ("order_index", ("position", "sort_order", "ordering", "idx",
                         "sort"), "INTEGER"),
    ],
}


class Storage:
    def __init__(self, path=None):
        self.path = Path(path) if path else _resolve_db_path()
        self.db = sqlite3.connect(str(self.path))
        self.db.row_factory = sqlite3.Row
        self._migrate()

    # ------------------------------------------------------------ migrations
    def _migrate(self):
        cur = self.db.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, title TEXT,
            visit_time REAL, visit_count INTEGER DEFAULT 1)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS saved_pages(
            id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE, title TEXT,
            created_at REAL, tag TEXT)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT,
            source_url TEXT, source_title TEXT,
            created_at REAL, updated_at REAL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS quick_apps(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT,
            icon TEXT, order_index INTEGER)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS permissions(
            host TEXT, ptype TEXT, granted INTEGER,
            PRIMARY KEY(host, ptype))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS sb_meta(
            key TEXT PRIMARY KEY, value TEXT)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS downloads(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT,
            path TEXT, size INTEGER DEFAULT 0, state TEXT,
            started_at REAL, finished_at REAL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS focus_sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, started_at REAL,
            seconds INTEGER, completed INTEGER DEFAULT 0, label TEXT)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS site_settings(
            host TEXT PRIMARY KEY, zoom INTEGER, shield_off INTEGER DEFAULT 0)""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_history_url ON history(url)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_history_time ON history(visit_time)")
        self._reconcile_columns(cur)
        self.db.commit()
        self._legacy_import(cur)

    def _reconcile_columns(self, cur):
        for table, spec in _SPECS.items():
            cols = _cols(cur, table)
            for canonical, candidates, decl in spec:
                if canonical in cols:
                    continue
                legacy = next((c for c in candidates if c in cols), None)
                if legacy is not None:
                    cur.execute(f"ALTER TABLE {table} RENAME COLUMN "
                                f"{legacy} TO {canonical}")
                    cols.discard(legacy)
                    cols.add(canonical)
                else:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN "
                                f"{canonical} {decl}")
                    cols.add(canonical)
        for table, col in (("history", "visit_time"),
                           ("saved_pages", "created_at"),
                           ("notes", "created_at"),
                           ("notes", "updated_at")):
            if col in _cols(cur, table):
                cur.execute(
                    f"UPDATE {table} SET {col} = "
                    f"CAST(strftime('%s', {col}) AS REAL) "
                    f"WHERE typeof({col}) = 'text' "
                    f"AND strftime('%s', {col}) IS NOT NULL")
        cur.execute("UPDATE history SET visit_time = 0 "
                    "WHERE visit_time IS NULL")
        cur.execute("UPDATE history SET visit_count = 1 "
                    "WHERE visit_count IS NULL")

    def _legacy_import(self, cur):
        done = cur.execute(
            "SELECT value FROM sb_meta WHERE key='legacy_import'").fetchone()
        if done:
            return
        def empty(t):
            return cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
        existing = {r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        try:
            if empty("saved_pages"):
                for legacy in ("bookmarks", "saved", "pages"):
                    if legacy in existing:
                        cols = _cols(cur, legacy)
                        if "url" in cols:
                            title = "title" if "title" in cols else "url"
                            cur.execute(
                                f"INSERT OR IGNORE INTO saved_pages"
                                f"(url,title,created_at) SELECT url, {title}, ?"
                                f" FROM {legacy}", (time.time(),))
                        break
            if empty("notes"):
                for legacy in ("notes_old", "note"):
                    if legacy in existing:
                        cols = _cols(cur, legacy)
                        if "content" in cols:
                            title = "title" if "title" in cols else "''"
                            cur.execute(
                                f"INSERT INTO notes(title,content,created_at,"
                                f"updated_at) SELECT {title}, content, ?, ?"
                                f" FROM {legacy}", (time.time(), time.time()))
                        break
            if empty("quick_apps"):
                for legacy in ("apps", "quickapps"):
                    if legacy in existing:
                        cols = _cols(cur, legacy)
                        if {"name", "url"} <= cols:
                            icon = "icon" if "icon" in cols else "'letter'"
                            cur.execute(
                                f"INSERT INTO quick_apps(name,url,icon,"
                                f"order_index) SELECT name, url, {icon}, rowid"
                                f" FROM {legacy}")
                        break
            cur.execute("INSERT OR REPLACE INTO sb_meta(key,value) "
                        "VALUES('legacy_import','1')")
            self.db.commit()
        except sqlite3.Error:
            self.db.rollback()

    # ------------------------------------------------------------ settings
    def get_setting(self, key, default=""):
        row = self.db.execute(
            "SELECT value FROM sb_meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        self.db.execute(
            "INSERT OR REPLACE INTO sb_meta(key,value) VALUES(?,?)",
            (key, str(value)))
        self.db.commit()

    # ------------------------------------------------------------ permissions
    def get_permission(self, host, ptype):
        row = self.db.execute(
            "SELECT granted FROM permissions WHERE host=? AND ptype=?",
            (host, ptype)).fetchone()
        if row is None:
            return None
        return bool(row["granted"])

    def set_permission(self, host, ptype, granted):
        self.db.execute(
            "INSERT OR REPLACE INTO permissions(host,ptype,granted) "
            "VALUES(?,?,?)", (host, ptype, 1 if granted else 0))
        self.db.commit()

    def list_permissions(self):
        return self.db.execute(
            "SELECT * FROM permissions ORDER BY host").fetchall()

    def delete_permission(self, host, ptype):
        self.db.execute("DELETE FROM permissions WHERE host=? AND ptype=?",
                        (host, ptype))
        self.db.commit()

    def clear_permissions(self):
        self.db.execute("DELETE FROM permissions")
        self.db.commit()

    # ------------------------------------------------------------ history
    def add_visit(self, url, title):
        cur = self.db.cursor()
        row = cur.execute("SELECT id, visit_count FROM history WHERE url=?",
                          (url,)).fetchone()
        if row:
            cur.execute("UPDATE history SET title=?, visit_time=?, "
                        "visit_count=? WHERE id=?",
                        (title, time.time(), (row["visit_count"] or 1) + 1,
                         row["id"]))
        else:
            cur.execute("INSERT INTO history(url,title,visit_time,visit_count)"
                        " VALUES(?,?,?,1)", (url, title, time.time()))
        self.db.commit()

    def recent_history(self, limit=12):
        return self.db.execute(
            "SELECT * FROM history WHERE url IS NOT NULL "
            "ORDER BY visit_time DESC LIMIT ?", (limit,)).fetchall()

    def search_history(self, q, limit=60):
        like = f"%{q}%"
        return self.db.execute(
            "SELECT * FROM history WHERE url LIKE ? OR title LIKE ? "
            "ORDER BY visit_time DESC LIMIT ?", (like, like, limit)).fetchall()

    def top_sites(self, limit=5, days=7):
        since = time.time() - days * 86400
        return self.db.execute(
            "SELECT url, title, SUM(visit_count) AS hits FROM history "
            "WHERE visit_time > ? AND url IS NOT NULL "
            "GROUP BY url ORDER BY hits DESC LIMIT ?",
            (since, limit)).fetchall()

    def delete_history(self, row_id):
        self.db.execute("DELETE FROM history WHERE id=?", (row_id,))
        self.db.commit()

    def clear_history(self):
        self.db.execute("DELETE FROM history")
        self.db.commit()

    # ------------------------------------------------------------ saved
    def list_saved(self, q=""):
        if q.startswith("#"):
            like = f"%{q[1:]}%"
            return self.db.execute(
                "SELECT * FROM saved_pages WHERE tag LIKE ? "
                "ORDER BY created_at DESC", (like,)).fetchall()
        if q:
            like = f"%{q}%"
            return self.db.execute(
                "SELECT * FROM saved_pages WHERE url LIKE ? OR title LIKE ? "
                "OR tag LIKE ? ORDER BY created_at DESC",
                (like, like, like)).fetchall()
        return self.db.execute(
            "SELECT * FROM saved_pages ORDER BY created_at DESC").fetchall()

    def is_saved(self, url):
        return self.db.execute(
            "SELECT 1 FROM saved_pages WHERE url=?", (url,)).fetchone() is not None

    def save_page(self, url, title):
        self.db.execute(
            "INSERT OR IGNORE INTO saved_pages(url,title,created_at) "
            "VALUES(?,?,?)", (url, title, time.time()))
        self.db.commit()

    def set_saved_tag(self, url, tag):
        self.db.execute("UPDATE saved_pages SET tag=? WHERE url=?",
                        (tag, url))
        self.db.commit()

    def unsave(self, url):
        self.db.execute("DELETE FROM saved_pages WHERE url=?", (url,))
        self.db.commit()

    def delete_saved(self, row_id):
        self.db.execute("DELETE FROM saved_pages WHERE id=?", (row_id,))
        self.db.commit()

    # ------------------------------------------------------------ notes
    def list_notes(self, q=""):
        if q:
            like = f"%{q}%"
            return self.db.execute(
                "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? "
                "ORDER BY updated_at DESC", (like, like)).fetchall()
        return self.db.execute(
            "SELECT * FROM notes ORDER BY updated_at DESC").fetchall()

    def get_note(self, note_id):
        return self.db.execute("SELECT * FROM notes WHERE id=?",
                               (note_id,)).fetchone()

    def create_note(self, title, content, source_url="", source_title=""):
        cur = self.db.cursor()
        cur.execute("INSERT INTO notes(title,content,source_url,source_title,"
                    "created_at,updated_at) VALUES(?,?,?,?,?,?)",
                    (title, content, source_url, source_title,
                     time.time(), time.time()))
        self.db.commit()
        return cur.lastrowid

    def update_note(self, note_id, title, content):
        self.db.execute("UPDATE notes SET title=?, content=?, updated_at=? "
                        "WHERE id=?", (title, content, time.time(), note_id))
        self.db.commit()

    def delete_note(self, note_id):
        self.db.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.db.commit()

    # ------------------------------------------------------------ quick apps
    def list_apps(self):
        return self.db.execute(
            "SELECT * FROM quick_apps ORDER BY order_index, id").fetchall()

    def save_app(self, name, url, icon, app_id=None):
        if app_id is None:
            mx = self.db.execute(
                "SELECT COALESCE(MAX(order_index),0) FROM quick_apps"
            ).fetchone()[0]
            self.db.execute(
                "INSERT INTO quick_apps(name,url,icon,order_index) "
                "VALUES(?,?,?,?)", (name, url, icon, (mx or 0) + 1))
        else:
            self.db.execute("UPDATE quick_apps SET name=?, url=?, icon=? "
                            "WHERE id=?", (name, url, icon, app_id))
        self.db.commit()

    def delete_app(self, app_id):
        self.db.execute("DELETE FROM quick_apps WHERE id=?", (app_id,))
        self.db.commit()

    def reorder_apps(self, ids):
        for i, app_id in enumerate(ids):
            self.db.execute("UPDATE quick_apps SET order_index=? WHERE id=?",
                            (i, app_id))
        self.db.commit()

    # ------------------------------------------------------------ misc
    def library_counts(self):
        s = self.db.execute("SELECT COUNT(*) FROM saved_pages").fetchone()[0]
        n = self.db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        h = self.db.execute("SELECT COUNT(*) FROM history").fetchone()[0]
        return {"saved": s, "notes": n, "history": h}

    # ------------------------------------------------------------ site settings
    def get_site(self, host):
        row = self.db.execute(
            "SELECT zoom, shield_off FROM site_settings WHERE host=?",
            (host,)).fetchone()
        return {"zoom": row["zoom"], "shield_off": bool(row["shield_off"])} \
            if row else {"zoom": None, "shield_off": False}

    def set_site_zoom(self, host, zoom):
        if not host:
            return
        self.db.execute(
            "INSERT INTO site_settings(host, zoom) VALUES(?,?) "
            "ON CONFLICT(host) DO UPDATE SET zoom=excluded.zoom",
            (host, None if zoom in (None, 100) else int(zoom)))
        self.db.commit()

    def set_site_shield_off(self, host, off):
        if not host:
            return
        self.db.execute(
            "INSERT INTO site_settings(host, shield_off) VALUES(?,?) "
            "ON CONFLICT(host) DO UPDATE SET shield_off=excluded.shield_off",
            (host, 1 if off else 0))
        self.db.commit()

    def shield_off_hosts(self):
        return {r["host"] for r in self.db.execute(
            "SELECT host FROM site_settings WHERE shield_off=1")}

    # ------------------------------------------------------------ downloads
    def add_download(self, name, url, path):
        cur = self.db.cursor()
        cur.execute("INSERT INTO downloads(name,url,path,state,started_at) "
                    "VALUES(?,?,?,?,?)", (name, url, path, "progress", time.time()))
        self.db.commit()
        return cur.lastrowid

    def finish_download(self, dl_id, state, size=0):
        self.db.execute("UPDATE downloads SET state=?, size=?, finished_at=? "
                        "WHERE id=?", (state, int(size or 0), time.time(), dl_id))
        self.db.commit()

    def list_downloads(self, limit=200):
        return self.db.execute(
            "SELECT * FROM downloads ORDER BY started_at DESC LIMIT ?",
            (limit,)).fetchall()

    def delete_download(self, dl_id):
        self.db.execute("DELETE FROM downloads WHERE id=?", (dl_id,))
        self.db.commit()

    def clear_downloads(self):
        self.db.execute("DELETE FROM downloads WHERE state != 'progress'")
        self.db.commit()

    # ------------------------------------------------------------ focus
    def add_focus_session(self, started_at, seconds, completed, label=""):
        self.db.execute(
            "INSERT INTO focus_sessions(started_at,seconds,completed,label) "
            "VALUES(?,?,?,?)", (started_at, int(seconds), 1 if completed else 0,
                                label))
        self.db.commit()

    def focus_stats(self):
        day0 = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
        today = self.db.execute(
            "SELECT COALESCE(SUM(seconds),0), COUNT(*) FROM focus_sessions "
            "WHERE started_at >= ?", (day0,)).fetchone()
        week = self.db.execute(
            "SELECT COALESCE(SUM(seconds),0) FROM focus_sessions "
            "WHERE started_at >= ?", (day0 - 6 * 86400,)).fetchone()
        done = self.db.execute(
            "SELECT COUNT(*) FROM focus_sessions WHERE completed=1").fetchone()
        return {"today_seconds": today[0], "today_sessions": today[1],
                "week_seconds": week[0], "completed": done[0]}

    # ------------------------------------------------------------ suggestions
    def suggest(self, q, limit=6):
        """Ranked history+saved matches for the address bar.

        Score = text-match quality x frecency (visit count decayed by age).
        """
        q = (q or "").strip().lower()
        if not q:
            return []
        like = f"%{q}%"
        rows = self.db.execute(
            "SELECT url, title, visit_time, visit_count, 0 AS saved FROM history "
            "WHERE url LIKE ? OR title LIKE ? LIMIT 200", (like, like)).fetchall()
        rows += self.db.execute(
            "SELECT url, title, created_at AS visit_time, 3 AS visit_count, 1 AS saved "
            "FROM saved_pages WHERE url LIKE ? OR title LIKE ? LIMIT 100",
            (like, like)).fetchall()
        now = time.time()
        best = {}
        for r in rows:
            url = r["url"] or ""
            if not url.startswith("http"):
                continue
            title = (r["title"] or "").lower()
            bare = url.split("://", 1)[-1].lower()
            if bare.startswith("www."):
                bare = bare[4:]
            score = 1.0
            if bare.startswith(q):
                score += 3.0
            elif q in bare.split("/")[0]:
                score += 2.0
            if title.startswith(q):
                score += 1.5
            age_days = max(0.0, (now - epoch(r["visit_time"])) / 86400)
            frecency = (r["visit_count"] or 1) / (1 + age_days / 14.0)
            score *= 1 + min(frecency, 8)
            if r["saved"]:
                score *= 1.4
            key = url.rstrip("/")
            cur = best.get(key)
            if cur is None or score > cur[0]:
                best[key] = (score, url, r["title"] or url, bool(r["saved"]))
        ranked = sorted(best.values(), key=lambda t: -t[0])[:limit]
        return [{"url": u, "title": t, "saved": sv} for _s, u, t, sv in ranked]

    def top_hosts(self, limit=8):
        rows = self.db.execute(
            "SELECT url, title, SUM(visit_count) AS hits FROM history "
            "WHERE url LIKE 'http%' GROUP BY url ORDER BY hits DESC LIMIT 200"
        ).fetchall()
        seen, out = set(), []
        for r in rows:
            host = r["url"].split("://", 1)[-1].split("/", 1)[0]
            if host in seen:
                continue
            seen.add(host)
            out.append(r)
            if len(out) >= limit:
                break
        return out

    # ------------------------------------------------------------ export
    def export_notes_markdown(self):
        out = ["# Study notes\n"]
        for n in reversed(self.list_notes()):
            out.append(f"## {n['title'] or 'Untitled'}\n")
            if n["source_url"]:
                out.append(f"*Source: [{n['source_title'] or n['source_url']}]"
                           f"({n['source_url']})*\n")
            out.append((n["content"] or "").rstrip() + "\n")
        return "\n".join(out)

    def export_saved_html(self):
        rows = self.list_saved()
        items = "\n".join(
            f'<DT><A HREF="{r["url"]}">{(r["title"] or r["url"])}</A>' for r in rows)
        return ("<!DOCTYPE NETSCAPE-Bookmark-file-1>\n"
                '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">\n'
                "<TITLE>Bookmarks</TITLE>\n<H1>Bookmarks</H1>\n<DL><p>\n"
                + items + "\n</DL><p>\n")
