"""Ingest service: validate a Mayhem match payload and store it idempotently.

Pure of Flask. Validation maps every contract violation to ``ValidationError``
(HTTP 400). Storage dedups on ``gameId`` so the same game uploaded by up to ten
collectors is counted once.

See ``/workspace/collector/INGEST_CONTRACT.md`` for the canonical payload. The
backend treats ``championId`` as authoritative; ``championName`` is a
denormalized label kept as sent.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..config import Config
from ..db import close_connection, get_connection
from ..errors import ValidationError

_EXPECTED_SCHEMA_VERSION = 1
_PARTICIPANT_COUNT = 10
_VALID_TEAM_IDS = (100, 200)

# End-of-game loadout slots, stored but not yet read by any aggregation.
# Items: item0..item5 plus the item6 trinket. Summoner spells: spell1, spell2.
_ITEM_SLOTS = 7
_SUMMONER_SPELL_SLOTS = 2

_PARTICIPANT_INT_FIELDS = (
    "participantId",
    "championId",
    "teamId",
    "kills",
    "deaths",
    "assists",
    "totalDamageDealtToChampions",
)
_NON_NEGATIVE_FIELDS = (
    "kills",
    "deaths",
    "assists",
    "totalDamageDealtToChampions",
)


def ingest_match(payload: Any, database_path: str | None = None) -> dict:
    """Validate ``payload`` and store the match, deduping on ``gameId``.

    Returns ``{"status": "created", "gameId": int}`` for a new match or
    ``{"status": "duplicate", "gameId": int}`` for a repeat. Games that ended in
    a remake (``gameEndedInEarlySurrender``) are never stored and return
    ``{"status": "skipped", "gameId": int}``. Raises ``ValidationError`` (400)
    on any contract violation.
    """
    match = _validate(payload)

    # Remakes carry no meaningful stats; drop them before touching the database.
    if match["gameEndedInEarlySurrender"]:
        return {"status": "skipped", "gameId": match["gameId"]}

    conn = get_connection(database_path)
    try:
        inserted = _store(conn, match)
        conn.commit()
    finally:
        close_connection(conn)

    status = "created" if inserted else "duplicate"
    return {"status": status, "gameId": match["gameId"]}


def _validate(payload: Any) -> dict:
    """Validate the payload against the contract and return a normalized match.

    The returned dict has coerced int/bool fields and an ``augments`` list of
    positive ints per participant (zero placeholders dropped defensively).
    """
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")

    schema_version = _require_int(payload, "schemaVersion")
    if schema_version != _EXPECTED_SCHEMA_VERSION:
        raise ValidationError(
            f"Unsupported schemaVersion {schema_version}; "
            f"expected {_EXPECTED_SCHEMA_VERSION}"
        )

    game_id = _require_int(payload, "gameId")
    queue_id = _require_int(payload, "queueId")
    if queue_id != Config.ARAM_QUEUE_ID:
        raise ValidationError(
            f"queueId {queue_id} is not the configured Mayhem queue"
        )

    patch = _require_str(payload, "patch")

    game_version = payload.get("gameVersion")
    if game_version is not None and not isinstance(game_version, str):
        raise ValidationError("gameVersion must be a string")

    game_creation = _optional_int(payload, "gameCreation")
    game_duration = _optional_int(payload, "gameDuration")
    remake = _optional_bool(payload, "gameEndedInEarlySurrender")

    raw_participants = payload.get("participants")
    if not isinstance(raw_participants, list):
        raise ValidationError("participants must be a list")
    if len(raw_participants) != _PARTICIPANT_COUNT:
        raise ValidationError(
            f"participants must contain exactly {_PARTICIPANT_COUNT} entries, "
            f"got {len(raw_participants)}"
        )

    participants = [_validate_participant(p, i) for i, p in enumerate(raw_participants)]

    return {
        "gameId": game_id,
        "queueId": queue_id,
        "patch": patch,
        "gameVersion": game_version,
        "gameCreation": game_creation,
        "gameDuration": game_duration,
        "gameEndedInEarlySurrender": remake,
        "participants": participants,
    }


def _validate_participant(p: Any, index: int) -> dict:
    if not isinstance(p, dict):
        raise ValidationError(f"participants[{index}] must be an object")

    values: dict[str, Any] = {}
    for field in _PARTICIPANT_INT_FIELDS:
        values[field] = _require_int(p, field, context=f"participants[{index}]")

    for field in _NON_NEGATIVE_FIELDS:
        if values[field] < 0:
            raise ValidationError(
                f"participants[{index}].{field} must be >= 0"
            )

    if not 1 <= values["participantId"] <= _PARTICIPANT_COUNT:
        raise ValidationError(
            f"participants[{index}].participantId must be 1..{_PARTICIPANT_COUNT}"
        )

    if values["teamId"] not in _VALID_TEAM_IDS:
        raise ValidationError(
            f"participants[{index}].teamId must be 100 or 200"
        )

    champion_name = p.get("championName")
    if not isinstance(champion_name, str) or not champion_name:
        raise ValidationError(
            f"participants[{index}].championName must be a non-empty string"
        )
    values["championName"] = champion_name

    win = p.get("win")
    if not isinstance(win, bool):
        raise ValidationError(
            f"participants[{index}].win must be a boolean"
        )
    values["win"] = win

    augments = p.get("augments")
    if not isinstance(augments, list):
        raise ValidationError(
            f"participants[{index}].augments must be a list"
        )
    clean: list[int] = []
    for aug in augments:
        if isinstance(aug, bool) or not isinstance(aug, int):
            raise ValidationError(
                f"participants[{index}].augments must contain integers"
            )
        if aug > 0:
            clean.append(aug)
    values["augments"] = clean

    # End-of-game items and summoner spells. Optional and additive: older
    # collectors that omit them still validate. Normalized to fixed slot counts.
    values["items"] = _optional_int_list(p, "items", index, _ITEM_SLOTS)
    values["summonerSpells"] = _optional_int_list(
        p, "summonerSpells", index, _SUMMONER_SPELL_SLOTS
    )

    return values


def _store(conn: sqlite3.Connection, match: dict) -> bool:
    """Insert the match and its children if new. Returns True if newly inserted.

    Uses ``INSERT OR IGNORE`` on the ``gameId`` primary key. Participant and
    augment rows are written only when the match row was newly created, so a
    duplicate upload never double-counts.
    """
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO matches
            (gameId, queueId, patch, gameVersion, gameCreation, gameDuration)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            match["gameId"],
            match["queueId"],
            match["patch"],
            match["gameVersion"],
            match["gameCreation"],
            match["gameDuration"],
        ),
    )

    if cur.rowcount == 0:
        return False

    for p in match["participants"]:
        pcur = conn.execute(
            """
            INSERT INTO participants
                (gameId, participantId, championId, championName, teamId,
                 win, kills, deaths, assists, totalDamageDealtToChampions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match["gameId"],
                p["participantId"],
                p["championId"],
                p["championName"],
                p["teamId"],
                1 if p["win"] else 0,
                p["kills"],
                p["deaths"],
                p["assists"],
                p["totalDamageDealtToChampions"],
            ),
        )
        participant_row_id = pcur.lastrowid
        for augment_id in p["augments"]:
            conn.execute(
                "INSERT INTO participant_augments (participant_id, augmentId) "
                "VALUES (?, ?)",
                (participant_row_id, augment_id),
            )

        conn.execute(
            """
            INSERT INTO participant_loadouts
                (participant_id, gameId, championId,
                 item0, item1, item2, item3, item4, item5, item6,
                 summoner1, summoner2)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                participant_row_id,
                match["gameId"],
                p["championId"],
                *p["items"],
                *p["summonerSpells"],
            ),
        )

    return True


# -- field coercion helpers ---------------------------------------------------


def _require_int(obj: dict, field: str, context: str | None = None) -> int:
    label = f"{context}.{field}" if context else field
    if field not in obj:
        raise ValidationError(f"Missing required field '{label}'")
    value = obj[field]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"'{label}' must be an integer")
    return value


def _optional_int_list(
    obj: dict, field: str, index: int, length: int
) -> list[int]:
    """Validate an optional list of non-negative ints into exactly ``length`` slots.

    Missing/None yields all-zero slots; a short list is zero-padded and a long
    one is truncated, so the stored loadout always has a fixed shape. Booleans,
    non-ints, and negatives are rejected with a ``ValidationError``.
    """
    raw = obj.get(field)
    if raw is None:
        return [0] * length
    if not isinstance(raw, list):
        raise ValidationError(f"participants[{index}].{field} must be a list")
    cleaned: list[int] = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(
                f"participants[{index}].{field} must contain integers"
            )
        if value < 0:
            raise ValidationError(
                f"participants[{index}].{field} must contain non-negative integers"
            )
        cleaned.append(value)
    if len(cleaned) >= length:
        return cleaned[:length]
    return cleaned + [0] * (length - len(cleaned))


def _optional_int(obj: dict, field: str) -> int | None:
    if field not in obj or obj[field] is None:
        return None
    value = obj[field]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"'{field}' must be an integer")
    return value


def _optional_bool(obj: dict, field: str) -> bool:
    if field not in obj or obj[field] is None:
        return False
    value = obj[field]
    if not isinstance(value, bool):
        raise ValidationError(f"'{field}' must be a boolean")
    return value


def _require_str(obj: dict, field: str) -> str:
    if field not in obj:
        raise ValidationError(f"Missing required field '{field}'")
    value = obj[field]
    if not isinstance(value, str) or not value:
        raise ValidationError(f"'{field}' must be a non-empty string")
    return value
