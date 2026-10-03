import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SESSION_FILE = ROOT / "session.json"


class SessionManager:
    def __init__(self):
        self.closed = []

    def push_closed(self, url: str, title: str, private: bool):
        if not url or url.startswith("studybrowse"):
            return
        self.closed.append({"url": url, "title": title or url,
                            "private": private})
        if len(self.closed) > 25:
            self.closed.pop(0)

    def pop_closed(self):
        return self.closed.pop() if self.closed else None

    def recent_closed(self, limit=8):
        return list(reversed(self.closed[-limit:]))

    def save_session(self, tabs, active_index):
        data = {"active": active_index,
                "tabs": [{"url": t["url"], "title": t["title"],
                          "private": t["private"],
                          "pinned": t.get("pinned", False),
                          "group": t.get("group")}
                         for t in tabs
                         if t["url"] and not t["url"].startswith("studybrowse")]}
        try:
            SESSION_FILE.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass

    def load_session(self):
        try:
            return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None