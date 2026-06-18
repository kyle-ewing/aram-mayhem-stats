"""Aggregation over ingested Mayhem matches (Flask-free, unit-testable).

Computes per-champion, per-augment, and champion+augment synergy winrates from
the SQLite store, then enriches augment ids with name/icon/rarity (Community
Dragon, keyless) and champions with Data Dragon icons.

Augment static data is fetched once and degrades gracefully: if Community Dragon
is unreachable the augment fields fall back to a placeholder name and ``None``
icon/rarity, exactly like the old per-summoner service did. Callers (tests) may
inject ``augment_map`` to avoid HTTP.

------------------------------------------------------------------------------
Response shapes (camelCase, frontend contract)
------------------------------------------------------------------------------
champion_winrates() -> list, sorted by games desc then winRate desc:
    {championId, championName, iconUrl, games, wins, winRate}

champion_detail(championId) -> dict, or None if the champion has no games:
    {championId, championName, iconUrl, games, wins, winRate,
     augments: [ {augmentId, augmentName, iconUrl, rarity, games, wins, winRate},
                 ... ]}    # augments sorted by games desc then winRate desc

augment_leaderboard() -> list, sorted by games desc then winRate desc:
    {augmentId, augmentName, iconUrl, rarity, games, wins, winRate}

``winRate`` is wins/games rounded to 4 decimals (0.0 when games is 0).
------------------------------------------------------------------------------
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from ..db import close_connection, get_connection
from ..errors import ApiError
from ..riot import champion_icon_url, fetch_augments


def champion_winrates(
    database_path: Optional[str] = None,
    *,
    augment_map: Optional[dict[int, dict]] = None,
) -> list[dict]:
    """Per-champion winrate and sample size across all ingested matches."""
    conn = get_connection(database_path)
    try:
        rows = conn.execute(
            """
            SELECT championId,
                   MAX(championName) AS championName,
                   COUNT(*)          AS games,
                   SUM(win)          AS wins
            FROM participants
            GROUP BY championId
            """
        ).fetchall()
    finally:
        close_connection(conn)

    result = [_champion_summary(r) for r in rows]
    result.sort(key=lambda c: (-c["games"], -c["winRate"]))
    return result


def champion_detail(
    champion_id: int,
    database_path: Optional[str] = None,
    *,
    augment_map: Optional[dict[int, dict]] = None,
) -> Optional[dict]:
    """Champion winrate plus that champion's per-augment winrates.

    Returns ``None`` when the champion has no ingested games so the route can
    decide on a 404 / empty response.
    """
    conn = get_connection(database_path)
    try:
        champ_row = conn.execute(
            """
            SELECT championId,
                   MAX(championName) AS championName,
                   COUNT(*)          AS games,
                   SUM(win)          AS wins
            FROM participants
            WHERE championId = ?
            GROUP BY championId
            """,
            (champion_id,),
        ).fetchone()

        if champ_row is None or champ_row["games"] == 0:
            return None

        augment_rows = conn.execute(
            """
            SELECT pa.augmentId AS augmentId,
                   COUNT(*)     AS games,
                   SUM(p.win)   AS wins
            FROM participant_augments pa
            JOIN participants p ON p.id = pa.participant_id
            WHERE p.championId = ?
            GROUP BY pa.augmentId
            """,
            (champion_id,),
        ).fetchall()
    finally:
        close_connection(conn)

    augment_map = _ensure_augment_map(augment_map)

    summary = _champion_summary(champ_row)
    summary["augments"] = _finalize_augment_rows(augment_rows, augment_map)
    return summary


def augment_leaderboard(
    database_path: Optional[str] = None,
    *,
    augment_map: Optional[dict[int, dict]] = None,
) -> list[dict]:
    """Per-augment winrate and sample size across all champions."""
    conn = get_connection(database_path)
    try:
        rows = conn.execute(
            """
            SELECT pa.augmentId AS augmentId,
                   COUNT(*)     AS games,
                   SUM(p.win)   AS wins
            FROM participant_augments pa
            JOIN participants p ON p.id = pa.participant_id
            GROUP BY pa.augmentId
            """
        ).fetchall()
    finally:
        close_connection(conn)

    augment_map = _ensure_augment_map(augment_map)
    return _finalize_augment_rows(rows, augment_map)


# -- helpers ------------------------------------------------------------------


def _champion_summary(row: sqlite3.Row) -> dict:
    games = row["games"] or 0
    wins = row["wins"] or 0
    name = row["championName"] or ""
    return {
        "championId": row["championId"],
        "championName": name,
        "iconUrl": champion_icon_url(name) if name else None,
        "games": games,
        "wins": wins,
        "winRate": round(wins / games, 4) if games else 0.0,
    }


def _finalize_augment_rows(
    rows, augment_map: dict[int, dict]
) -> list[dict]:
    result = []
    for row in rows:
        augment_id = row["augmentId"]
        games = row["games"] or 0
        wins = row["wins"] or 0
        info = augment_map.get(augment_id)
        if info is not None:
            name = info.get("name") or f"Augment {augment_id}"
            icon_url = info.get("iconLarge") or info.get("iconSmall")
            rarity = info.get("rarity")
        else:
            name = f"Augment {augment_id}"
            icon_url = None
            rarity = None
        result.append(
            {
                "augmentId": augment_id,
                "augmentName": name,
                "iconUrl": icon_url,
                "rarity": rarity,
                "games": games,
                "wins": wins,
                "winRate": round(wins / games, 4) if games else 0.0,
            }
        )
    result.sort(key=lambda a: (-a["games"], -a["winRate"]))
    return result


def _ensure_augment_map(
    augment_map: Optional[dict[int, dict]],
) -> dict[int, dict]:
    """Return the injected map, or fetch one, degrading to ``{}`` on failure.

    Only ``ApiError`` subclasses (the contract of ``fetch_augments``) are
    swallowed so unreachable Community Dragon never fails an aggregation query.
    """
    if augment_map is not None:
        return augment_map
    try:
        return fetch_augments()
    except ApiError:
        return {}
