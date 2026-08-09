# -*- coding: utf-8 -*-
"""解析历史：本地 SQLite，最多 50 条"""
import os
import sqlite3
import time


def _db():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.db")


def _conn():
    c = sqlite3.connect(_db())
    c.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, platform TEXT, title TEXT, url TEXT,
        media_type TEXT, media_count INTEGER)""")
    return c


def add(platform, title, url, media_type, media_count=0):
    try:
        c = _conn()
        c.execute("INSERT INTO history(ts, platform, title, url, media_type, media_count) VALUES(?,?,?,?,?,?)",
                  (time.time(), platform, (title or "")[:80], url, media_type, media_count))
        # 只保留最新 50 条
        c.execute("DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY id DESC LIMIT 50)")
        c.commit()
        c.close()
    except Exception:
        pass


def recent(limit=5):
    try:
        c = _conn()
        rows = c.execute("SELECT ts, platform, title, url, media_type, media_count FROM history ORDER BY id DESC LIMIT ?",
                         (limit,)).fetchall()
        c.close()
        return [{"ts": r[0], "platform": r[1], "title": r[2], "url": r[3],
                 "media_type": r[4], "media_count": r[5]} for r in rows]
    except Exception:
        return []


def clear():
    try:
        c = _conn()
        c.execute("DELETE FROM history")
        c.commit()
        c.close()
    except Exception:
        pass
