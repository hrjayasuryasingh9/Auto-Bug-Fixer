"""Production-grade conversation context — SQLite backed.

Scopes state to Slack's natural hierarchy so many people can use the bot in the
same channel, each on their own repo and answer-style:

    workspace → channel → thread → user  →  { selected_repo, mode }

Resolution falls back thread → channel-level (same user) → server env default,
so a user who picked a repo in the channel keeps it inside threads too, while a
thread can still override.
"""
import os
import sqlite3
import threading

from server.utils.credentials import github_owner, github_repo
from server.utils.logger import logger

_DB = os.path.join(os.path.dirname(__file__), "..", "data", "context.db")
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

_DDL = """
CREATE TABLE IF NOT EXISTS conversation_context (
    workspace_id   TEXT NOT NULL DEFAULT '',
    channel_id     TEXT NOT NULL DEFAULT '',
    thread_id      TEXT NOT NULL DEFAULT '',
    user_id        TEXT NOT NULL DEFAULT '',
    selected_owner TEXT,
    selected_repo  TEXT,
    mode           TEXT NOT NULL DEFAULT 'simple',   -- 'simple' | 'technical'
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (workspace_id, channel_id, thread_id, user_id)
);
"""


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(_DB), exist_ok=True)
        _conn = sqlite3.connect(_DB, check_same_thread=False)
        _conn.execute(_DDL)
        _conn.commit()
    return _conn


def _key(ctx: dict) -> tuple[str, str, str, str]:
    return (
        (ctx.get("workspace_id") or ""),
        (ctx.get("channel_id") or ""),
        (ctx.get("thread_id") or ""),
        (ctx.get("user_id") or ""),
    )


def _row(w: str, c: str, t: str, u: str) -> dict | None:
    with _lock:
        cur = _db().execute(
            "SELECT selected_owner, selected_repo, mode FROM conversation_context "
            "WHERE workspace_id=? AND channel_id=? AND thread_id=? AND user_id=?",
            (w, c, t, u),
        )
        r = cur.fetchone()
    return {"owner": r[0], "repo": r[1], "mode": r[2]} if r else None


def _best(ctx: dict) -> dict | None:
    """Exact (incl. thread) → same user at channel level (thread='') → None."""
    w, c, t, u = _key(ctx)
    row = _row(w, c, t, u)
    if row:
        return row
    if t:  # inside a thread but nothing set there → fall back to channel-level
        return _row(w, c, "", u)
    return None


def get_active_repo(ctx: dict) -> dict | None:
    row = _best(ctx)
    if row and row.get("owner") and row.get("repo"):
        return {"owner": row["owner"], "repo": row["repo"]}
    return None


def resolve_repo(ctx: dict) -> tuple[str, str]:
    repo = get_active_repo(ctx)
    if repo:
        return repo["owner"], repo["repo"]
    return github_owner(), github_repo()


def get_technical(ctx: dict) -> bool:
    row = _best(ctx)
    return bool(row and row.get("mode") == "technical")


def _upsert(ctx: dict, **fields) -> None:
    w, c, t, u = _key(ctx)
    cols = ", ".join(fields)
    placeholders = ", ".join(["?"] * len(fields))
    updates = ", ".join(f"{k}=excluded.{k}" for k in fields)
    sql = (
        f"INSERT INTO conversation_context "
        f"(workspace_id, channel_id, thread_id, user_id, {cols}, updated_at) "
        f"VALUES (?, ?, ?, ?, {placeholders}, datetime('now')) "
        f"ON CONFLICT(workspace_id, channel_id, thread_id, user_id) "
        f"DO UPDATE SET {updates}, updated_at=datetime('now')"
    )
    try:
        with _lock:
            conn = _db()
            conn.execute(sql, (w, c, t, u, *fields.values()))
            conn.commit()
    except Exception as e:
        logger.error(f"[context_store] upsert failed: {e}")


def set_active_repo(ctx: dict, owner: str, repo: str) -> None:
    _upsert(ctx, selected_owner=owner, selected_repo=repo)


def set_mode(ctx: dict, technical: bool) -> None:
    _upsert(ctx, mode=("technical" if technical else "simple"))
