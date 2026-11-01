import sqlite3
from datetime import datetime
from pathlib import Path

class Storage:
    def __init__(self, path: Path):
        self.path = path
        self.db = None

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT, title TEXT, visited TEXT)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS bookmarks(
            url TEXT PRIMARY KEY, title TEXT, created TEXT)""")
        self.db.commit()

    def add_history(self, url, title):
        self.db.execute("INSERT INTO history(url,title,visited) VALUES(?,?,?)",
                        (url, title, datetime.now().isoformat(timespec="seconds")))
        self.db.commit()

    def history(self, limit=200):
        return self.db.execute(
            "SELECT title,url,visited FROM history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    def recent_text(self):
        rows = self.history(4)
        return "\n".join("• " + (r[0] or r[1])[:42] for r in rows) or "No recent activity"

    def add_bookmark(self, url, title):
        self.db.execute("""INSERT INTO bookmarks(url,title,created) VALUES(?,?,?)
            ON CONFLICT(url) DO UPDATE SET title=excluded.title""",
            (url, title, datetime.now().isoformat(timespec="seconds")))
        self.db.commit()

    def bookmarks(self):
        return self.db.execute("SELECT title,url FROM bookmarks ORDER BY title").fetchall()

    def close(self):
        if self.db:
            self.db.close()
            self.db = None
