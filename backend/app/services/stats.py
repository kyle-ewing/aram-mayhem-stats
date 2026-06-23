"""Aggregation over ingested Mayhem matches (Flask-free, unit-testable).

Computes per-champion, per-augment, and champion+augment synergy winrates from
the SQLite store, then enriches augment ids with a name/rarity from the curated
Mayhem pool (``app/data/mayhem_augments.json``) and champions with Data Dragon
icons.

Augment names come from the curated pool, not Community Dragon: Mayhem augment
ids are a different id space from Community Dragon's arena augments, so only the
hand-maintained pool can resolve a Mayhem id to a name. If an id has no curated
entry (still null, or not yet recorded), the augment name falls back to the raw
id as a string and icon/rarity are ``None``. Callers (tests) may inject
``augment_map`` directly.

------------------------------------------------------------------------------
Response shapes (camelCase, frontend contract)
------------------------------------------------------------------------------
champion_winrates() -> list, sorted by games desc then winRate desc:
    {championId, championName, iconUrl, games, wins, winRate}

champion_detail(championId) -> dict, or None if the champion has no games:
    {championId, championName, iconUrl, games, wins, winRate,
     augments: [ {augmentId, augmentName, iconUrl, rarity, games, wins, winRate},
                 ... ]}    # augments sorted by games desc then winRate desc

champion_itemization(championId) -> dict, or None if the champion has no games:
    {championId, championName, iconUrl, games, wins, winRate,
     items: [ {itemId, itemName, iconUrl, damageType, games, wins, winRate},
              ... ],       # one row per legendary item seen, games desc then winRate desc
     builds: [ {build, games, wins, winRate}, ... ]}  # fixed order AD, AP, mixed, other
    Only completed/legendary items count (components, trinkets, consumables, and
    item id 0 are ignored). Among a game's distinct legendary items, the damage
    items are those typed AD, AP, or mixed; "other"-typed items are excluded from
    that count. A game is AD when >= 75% of its damage items are AD, AP when
    >= 75% are AP, "other" when it has no damage items at all, else "mixed".
    Games with no legendary items are skipped from build buckets.

augment_leaderboard() -> list, sorted by games desc then winRate desc:
    {augmentId, augmentName, iconUrl, rarity, games, wins, winRate}

``winRate`` is wins/games rounded to 4 decimals (0.0 when games is 0).
------------------------------------------------------------------------------
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from ..db import close_connection, get_connection
from ..riot import champion_icon_url, fetch_item_metadata, latest_ddragon_version
from .mayhem_augments import get_mayhem_augments

_ITEM_SLOTS = ("item0", "item1", "item2", "item3", "item4", "item5", "item6")
_AD_AP_THRESHOLD = 0.75


def total_games(database_path: Optional[str] = None) -> int:
    """Total number of ingested matches (games), for a parsed-games counter."""
    conn = get_connection(database_path)
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM matches").fetchone()
    finally:
        close_connection(conn)
    return row["n"] if row else 0


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

    version = latest_ddragon_version()
    result = [_champion_summary(r, version) for r in rows]
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

    summary = _champion_summary(champ_row, latest_ddragon_version())
    summary["augments"] = _finalize_augment_rows(augment_rows, augment_map)
    return summary


def champion_itemization(
    champion_id: int,
    database_path: Optional[str] = None,
    *,
    item_map: Optional[dict[int, dict]] = None,
) -> Optional[dict]:
    """Champion winrate plus that champion's itemization winrates.

    Builds two tables from end-of-game loadouts, restricted to completed/
    legendary items (components, trinkets, consumables, and empty slot 0 are
    ignored):

    * ``items``: per legendary item, how many of this champion's games included
      it and how many were wins. A game counts once per distinct legendary item.
    * ``builds``: each game is bucketed AD, AP, mixed, or other from the damage
      types of its distinct legendary items. Among AD/AP/mixed items, >= 75% AD
      -> AD, >= 75% AP -> AP, else mixed; a game with no AD/AP/mixed items at all
      -> other. Games with no legendary items are skipped from the buckets.

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

        loadout_rows = conn.execute(
            """
            SELECT p.win AS win,
                   pl.item0 AS item0, pl.item1 AS item1, pl.item2 AS item2,
                   pl.item3 AS item3, pl.item4 AS item4, pl.item5 AS item5,
                   pl.item6 AS item6
            FROM participant_loadouts pl
            JOIN participants p ON p.id = pl.participant_id
            WHERE p.championId = ?
            """,
            (champion_id,),
        ).fetchall()
    finally:
        close_connection(conn)

    item_map = _ensure_item_map(item_map)

    summary = _champion_summary(champ_row, latest_ddragon_version())
    items, builds = _aggregate_itemization(loadout_rows, item_map)
    summary["items"] = items
    summary["builds"] = builds
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


def _champion_summary(row: sqlite3.Row, version: Optional[str] = None) -> dict:
    games = row["games"] or 0
    wins = row["wins"] or 0
    name = row["championName"] or ""
    return {
        "championId": row["championId"],
        "championName": name,
        "iconUrl": champion_icon_url(name, version) if name else None,
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
        if info is not None and info.get("name"):
            name = info["name"]
            icon_url = (
                info.get("icon")
                or info.get("iconLarge")
                or info.get("iconSmall")
            )
            rarity = info.get("rarity")
        else:
            # No matching id in the static data (or it has no name): fall back
            # to showing the raw augment id rather than a placeholder label.
            name = str(augment_id)
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


def _legendary_item_ids(row, item_map: dict[int, dict]) -> set[int]:
    """Distinct completed/legendary item ids in a participant's seven slots.

    Empty slots (id 0), ids missing from the metadata, and items the metadata
    marks as non-legendary (components, trinkets, consumables) are dropped.
    """
    ids: set[int] = set()
    for slot in _ITEM_SLOTS:
        item_id = row[slot] or 0
        if item_id == 0:
            continue
        info = item_map.get(item_id)
        if info is None or not info.get("legendary"):
            continue
        ids.add(item_id)
    return ids


def _classify_build(item_ids: set[int], item_map: dict[int, dict]) -> Optional[str]:
    """Bucket legendary item ids into ``"AD"``, ``"AP"``, ``"mixed"``, or ``"other"``.

    Returns ``None`` when there are no legendary items, so the game is skipped.

    Only AD, AP, and mixed items are damage items and form the denominator.
    "mixed"-typed items count in that denominator but toward neither the AD nor
    AP share, so they pull the build toward the "mixed" bucket. "other"-typed
    items are excluded from the denominator entirely, so they do not dilute the
    AD/AP share. A build with no damage items at all falls into "other".
    """
    if len(item_ids) == 0:
        return None
    ad = sum(
        1 for i in item_ids if (item_map.get(i) or {}).get("damageType") == "AD"
    )
    ap = sum(
        1 for i in item_ids if (item_map.get(i) or {}).get("damageType") == "AP"
    )
    mixed = sum(
        1 for i in item_ids if (item_map.get(i) or {}).get("damageType") == "mixed"
    )
    damage_items = ad + ap + mixed
    if damage_items == 0:
        return "other"
    if ad / damage_items >= _AD_AP_THRESHOLD:
        return "AD"
    if ap / damage_items >= _AD_AP_THRESHOLD:
        return "AP"
    return "mixed"


def _aggregate_itemization(
    rows, item_map: dict[int, dict]
) -> tuple[list[dict], list[dict]]:
    """Compute the single-item table and the AD/AP/mixed/other build table."""
    item_games: dict[int, int] = {}
    item_wins: dict[int, int] = {}
    build_games = {"AD": 0, "AP": 0, "mixed": 0, "other": 0}
    build_wins = {"AD": 0, "AP": 0, "mixed": 0, "other": 0}

    for row in rows:
        win = row["win"] or 0
        legendary = _legendary_item_ids(row, item_map)
        for item_id in legendary:
            item_games[item_id] = item_games.get(item_id, 0) + 1
            item_wins[item_id] = item_wins.get(item_id, 0) + win
        build = _classify_build(legendary, item_map)
        if build is not None:
            build_games[build] += 1
            build_wins[build] += win

    items = []
    for item_id, games in item_games.items():
        wins = item_wins[item_id]
        info = item_map.get(item_id) or {}
        name = info.get("name") or str(item_id)
        icon_url = info.get("iconUrl") if info.get("name") else None
        items.append(
            {
                "itemId": item_id,
                "itemName": name,
                "iconUrl": icon_url,
                "damageType": info.get("damageType", "other"),
                "games": games,
                "wins": wins,
                "winRate": round(wins / games, 4) if games else 0.0,
            }
        )
    items.sort(key=lambda it: (-it["games"], -it["winRate"]))

    builds = []
    for build in ("AD", "AP", "mixed", "other"):
        games = build_games[build]
        wins = build_wins[build]
        builds.append(
            {
                "build": build,
                "games": games,
                "wins": wins,
                "winRate": round(wins / games, 4) if games else 0.0,
            }
        )

    return items, builds


def _ensure_item_map(
    item_map: Optional[dict[int, dict]],
) -> dict[int, dict]:
    """Return the injected map, or fetch item metadata from Data Dragon.

    Names/classification come from ``fetch_item_metadata`` (keyless Data Dragon).
    Tests inject a small map directly to avoid HTTP.
    """
    if item_map is not None:
        return item_map
    return fetch_item_metadata()


def _ensure_augment_map(
    augment_map: Optional[dict[int, dict]],
) -> dict[int, dict]:
    """Return the injected map, or build one from the curated Mayhem pool.

    Names come from ``app/data/mayhem_augments.json``, not Community Dragon:
    Community Dragon's arena augment ids are a different id space from ARAM
    Mayhem's, so only the hand-maintained pool can map a Mayhem augment id to a
    name. Entries whose ``id`` is still null are skipped (they have no id to
    match against). Tier is carried through as ``rarity`` for display.
    """
    if augment_map is not None:
        return augment_map
    return {
        entry["id"]: {
            "name": entry.get("name", ""),
            "rarity": entry.get("tier"),
            "icon": entry.get("icon"),
        }
        for entry in get_mayhem_augments()
        if isinstance(entry, dict) and entry.get("id") is not None
    }
