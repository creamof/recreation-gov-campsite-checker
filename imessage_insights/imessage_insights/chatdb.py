"""Read-only access to the macOS Messages database (``chat.db``).

Exposes small dataclasses (Chat, Message) and query helpers. The database is
opened read-only; if that fails because of a stale write-ahead log, we copy the
DB (plus its -wal/-shm sidecars) to a temp dir and open the copy.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from . import attributed_body, config
from .contacts import resolve

# chat.style: 43 == group conversation, 45 == one-to-one.
GROUP_STYLE = 43

# Tapback/reaction association types live in the 2000s/3000s range. item_type 0
# is a normal message (non-zero item types are group events like renames).


@dataclass
class Chat:
    rowid: int
    guid: str
    identifier: str
    display_name: str
    is_group: bool
    service: str


@dataclass
class Message:
    rowid: int
    chat_id: int
    text: str
    handle: str  # phone/email of sender, or "" when from me
    is_from_me: bool
    date: datetime
    has_attachment: bool


def _apple_time_to_datetime(value: int | None) -> datetime:
    """Convert a Messages ``date`` (ns since 2001) to a local datetime."""
    if not value:
        return datetime.fromtimestamp(0)
    # Modern macOS stores nanoseconds; older stored seconds. Detect by magnitude.
    seconds = value / 1_000_000_000 if value > 1_000_000_000_000 else value
    return datetime.fromtimestamp(seconds + config.APPLE_EPOCH_OFFSET)


class ChatDB:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    # -- lifecycle -----------------------------------------------------------
    @classmethod
    @contextmanager
    def open(cls, db_path: Path | None = None) -> "Iterator[ChatDB]":
        path = Path(db_path) if db_path else config.DEFAULT_DB_PATH
        if not path.exists():
            raise FileNotFoundError(
                f"Messages database not found at {path}. On macOS it lives at "
                f"~/Library/Messages/chat.db and requires Full Disk Access."
            )
        conn, tmpdir = _connect(path)
        try:
            yield cls(conn)
        finally:
            conn.close()
            if tmpdir is not None:
                shutil.rmtree(tmpdir, ignore_errors=True)

    # -- queries -------------------------------------------------------------
    def message_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM message").fetchone()[0]

    def chats(self, groups_only: bool = False) -> list[Chat]:
        rows = self.conn.execute(
            """
            SELECT ROWID, guid, chat_identifier, display_name, style, service_name
            FROM chat
            """
        ).fetchall()
        result = []
        for r in rows:
            is_group = r["style"] == GROUP_STYLE
            if groups_only and not is_group:
                continue
            result.append(
                Chat(
                    rowid=r["ROWID"],
                    guid=r["guid"],
                    identifier=r["chat_identifier"] or "",
                    display_name=(r["display_name"] or "").strip(),
                    is_group=is_group,
                    service=r["service_name"] or "",
                )
            )
        return result

    def participants(self, chat_id: int) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT h.id
            FROM chat_handle_join chj
            JOIN handle h ON h.ROWID = chj.handle_id
            WHERE chj.chat_id = ?
            """,
            (chat_id,),
        ).fetchall()
        return [r["id"] for r in rows if r["id"]]

    def messages(
        self,
        chat_id: int,
        limit: int | None = None,
        since: datetime | None = None,
    ) -> list[Message]:
        """Return messages for a chat, oldest first (real text messages only)."""
        params: list = [chat_id]
        clause = ""
        if since is not None:
            apple_ns = int(
                (since.timestamp() - config.APPLE_EPOCH_OFFSET) * 1_000_000_000
            )
            clause = "AND m.date >= ?"
            params.append(apple_ns)

        sql = f"""
            SELECT m.ROWID, m.text, m.attributedBody, m.is_from_me, m.date,
                   m.cache_has_attachments, h.id AS handle
            FROM message m
            JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
            LEFT JOIN handle h ON h.ROWID = m.handle_id
            WHERE cmj.chat_id = ?
              AND m.item_type = 0
              AND m.associated_message_type = 0
              {clause}
            ORDER BY m.date ASC
        """
        rows = self.conn.execute(sql, params).fetchall()
        if limit is not None and len(rows) > limit:
            rows = rows[-limit:]  # keep the most recent `limit` messages

        out = []
        for r in rows:
            text = r["text"] or attributed_body.decode(r["attributedBody"]) or ""
            if not text.strip():
                continue
            out.append(
                Message(
                    rowid=r["ROWID"],
                    chat_id=chat_id,
                    text=text.strip(),
                    handle="" if r["is_from_me"] else (r["handle"] or ""),
                    is_from_me=bool(r["is_from_me"]),
                    date=_apple_time_to_datetime(r["date"]),
                    has_attachment=bool(r["cache_has_attachments"]),
                )
            )
        return out

    def last_message(self, chat_id: int) -> Message | None:
        msgs = self.messages(chat_id, limit=1)
        return msgs[-1] if msgs else None

    def reaction_counts(
        self, chat_id: int, since: datetime | None = None
    ) -> dict[str, int]:
        """Count tapbacks/reactions each participant sent in a chat.

        Returns {handle_or_'me': count}. Reactions are messages with a non-zero
        associated_message_type (the normal message views filter these out).
        """
        params: list = [chat_id]
        clause = ""
        if since is not None:
            apple_ns = int(
                (since.timestamp() - config.APPLE_EPOCH_OFFSET) * 1_000_000_000
            )
            clause = "AND m.date >= ?"
            params.append(apple_ns)
        rows = self.conn.execute(
            f"""
            SELECT m.is_from_me AS me, h.id AS handle
            FROM message m
            JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
            LEFT JOIN handle h ON h.ROWID = m.handle_id
            WHERE cmj.chat_id = ?
              AND m.associated_message_type != 0
              {clause}
            """,
            params,
        ).fetchall()
        counts: dict[str, int] = {}
        for r in rows:
            key = "me" if r["me"] else (r["handle"] or "")
            if key:
                counts[key] = counts.get(key, 0) + 1
        return counts

    def activity_counts(self, since: datetime | None = None) -> dict[int, int]:
        """Return {chat_id: message_count}, optionally limited to recent days."""
        params: list = []
        clause = ""
        if since is not None:
            apple_ns = int(
                (since.timestamp() - config.APPLE_EPOCH_OFFSET) * 1_000_000_000
            )
            clause = "WHERE m.date >= ?"
            params.append(apple_ns)
        rows = self.conn.execute(
            f"""
            SELECT cmj.chat_id AS chat_id, COUNT(*) AS n
            FROM message m
            JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
            {clause}
            GROUP BY cmj.chat_id
            """,
            params,
        ).fetchall()
        return {r["chat_id"]: r["n"] for r in rows}


def _connect(path: Path) -> tuple[sqlite3.Connection, Path | None]:
    """Open the DB read-only; fall back to a temp copy on lock/WAL errors."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
        conn.execute("SELECT COUNT(*) FROM message LIMIT 1")
        return conn, None
    except sqlite3.Error:
        pass

    tmpdir = Path(tempfile.mkdtemp(prefix="imsg_"))
    copy = tmpdir / "chat.db"
    shutil.copy2(path, copy)
    for suffix in ("-wal", "-shm"):
        sidecar = path.with_name(path.name + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, tmpdir / (copy.name + suffix))
    conn = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
    return conn, tmpdir


def default_window(days: int) -> datetime:
    return datetime.now() - timedelta(days=days)


def thread_title(db: "ChatDB", chat: Chat, contacts: dict[str, str]) -> str:
    """Human-friendly name for a chat: its display name, else its participants."""
    if chat.display_name:
        return chat.display_name
    parts = db.participants(chat.rowid)
    if not parts:
        return chat.identifier or f"chat {chat.rowid}"
    names = [resolve(p, contacts) for p in parts]
    if len(names) > 4:
        return ", ".join(names[:4]) + f" +{len(names) - 4}"
    return ", ".join(names)
