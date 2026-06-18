"""SQLite connection management and schema for ingested Mayhem matches.

Thin data-access layer over the stdlib ``sqlite3`` (no heavy deps). Route
handlers and services obtain connections from here and run their SQL; the schema
itself lives in this module so initialization is one call.

Schema (normalized to support per-champion, per-augment, and champion+augment
synergy winrate queries):

* ``matches``              one row per game, keyed on ``gameId`` for dedup.
* ``participants``         ten rows per match (one per player), linked by gameId.
* ``participant_augments`` zero-or-more rows per participant (one per augment id).
* ``participant_loadouts`` one row per participant: end-of-game items (7 slots)
                           and the two summoner spells. Collected for later use;
                           nothing reads it yet.

Foreign keys cascade on delete. ``init_db`` is idempotent and is called at app
startup (and by tests against an in-memory or temp-file database).
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from .config import Config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    gameId        INTEGER PRIMARY KEY,
    queueId       INTEGER NOT NULL,
    patch         TEXT    NOT NULL,
    gameVersion   TEXT,
    gameCreation  INTEGER,
    gameDuration  INTEGER,
    ingestedAt    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS participants (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    gameId                      INTEGER NOT NULL,
    participantId               INTEGER NOT NULL,
    championId                  INTEGER NOT NULL,
    championName                TEXT    NOT NULL,
    teamId                      INTEGER NOT NULL,
    win                         INTEGER NOT NULL,
    kills                       INTEGER NOT NULL,
    deaths                      INTEGER NOT NULL,
    assists                     INTEGER NOT NULL,
    totalDamageDealtToChampions INTEGER NOT NULL,
    FOREIGN KEY (gameId) REFERENCES matches (gameId) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS participant_augments (
    participant_id INTEGER NOT NULL,
    augmentId      INTEGER NOT NULL,
    FOREIGN KEY (participant_id) REFERENCES participants (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS participant_loadouts (
    participant_id INTEGER PRIMARY KEY,
    gameId         INTEGER NOT NULL,
    championId     INTEGER NOT NULL,
    item0          INTEGER NOT NULL DEFAULT 0,
    item1          INTEGER NOT NULL DEFAULT 0,
    item2          INTEGER NOT NULL DEFAULT 0,
    item3          INTEGER NOT NULL DEFAULT 0,
    item4          INTEGER NOT NULL DEFAULT 0,
    item5          INTEGER NOT NULL DEFAULT 0,
    item6          INTEGER NOT NULL DEFAULT 0,
    summoner1      INTEGER NOT NULL DEFAULT 0,
    summoner2      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (participant_id) REFERENCES participants (id) ON DELETE CASCADE,
    FOREIGN KEY (gameId) REFERENCES matches (gameId) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_participants_gameId
    ON participants (gameId);
CREATE INDEX IF NOT EXISTS idx_participants_championId
    ON participants (championId);
CREATE INDEX IF NOT EXISTS idx_participant_augments_augmentId
    ON participant_augments (augmentId);
CREATE INDEX IF NOT EXISTS idx_participant_augments_participant
    ON participant_augments (participant_id);
CREATE INDEX IF NOT EXISTS idx_participant_loadouts_championId
    ON participant_loadouts (championId);
CREATE INDEX IF NOT EXISTS idx_participant_loadouts_gameId
    ON participant_loadouts (gameId);
"""


# A ``:memory:`` database is unique per connection, so callers that close and
# reopen would each see an empty database. To make the in-memory mode usable for
# tests and a single-process dev server, the one in-memory connection is cached
# and reused (and never closed by ``close_connection``).
_memory_conn: Optional[sqlite3.Connection] = None


def _is_memory(path: str) -> bool:
    return path == ":memory:"


def get_connection(database_path: Optional[str] = None) -> sqlite3.Connection:
    """Open a SQLite connection with rows accessible by column name.

    ``database_path`` defaults to ``Config.DATABASE_PATH``. Foreign-key
    enforcement is enabled per connection (SQLite defaults it off). For the
    ``:memory:`` path a single shared connection is reused so data persists
    across calls within the process.
    """
    global _memory_conn
    path = database_path if database_path is not None else Config.DATABASE_PATH

    if _is_memory(path):
        if _memory_conn is None:
            _memory_conn = _new_connection(path)
        return _memory_conn

    return _new_connection(path)


def _new_connection(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def close_connection(conn: sqlite3.Connection) -> None:
    """Close a connection unless it is the shared in-memory one."""
    if conn is not _memory_conn:
        conn.close()


def reset_memory_db() -> None:
    """Drop the cached in-memory connection (test isolation helper)."""
    global _memory_conn
    if _memory_conn is not None:
        _memory_conn.close()
        _memory_conn = None


def init_db(database_path: Optional[str] = None) -> None:
    """Create tables and indexes if they do not exist. Idempotent."""
    conn = get_connection(database_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        close_connection(conn)
