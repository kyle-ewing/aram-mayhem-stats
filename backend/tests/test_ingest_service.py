"""Tests for the ingest service: validation, happy path, idempotency."""
from __future__ import annotations

import pytest

from app.db import get_connection, init_db, reset_memory_db
from app.errors import ValidationError
from app.services.ingest import ingest_match
from tests.conftest import make_participant, make_payload

_DB = ":memory:"


@pytest.fixture(autouse=True)
def _fresh_db():
    reset_memory_db()
    init_db(_DB)
    yield
    reset_memory_db()


def _count(table):
    conn = get_connection(_DB)
    try:
        return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
    finally:
        pass


def test_happy_path_stores_match_and_children():
    payload = make_payload(
        [make_participant(champion_id=99, augments=(7, 12, 0, 0))]
    )
    result = ingest_match(payload, database_path=_DB)
    assert result == {"status": "created", "gameId": 1}
    assert _count("matches") == 1
    assert _count("participants") == 10
    assert _count("participant_augments") == 2


def test_remake_is_not_stored():
    payload = make_payload([make_participant(champion_id=99, augments=(7, 0, 0, 0))])
    payload["gameEndedInEarlySurrender"] = True
    result = ingest_match(payload, database_path=_DB)
    assert result == {"status": "skipped", "gameId": 1}
    assert _count("matches") == 0
    assert _count("participants") == 0
    assert _count("participant_augments") == 0
    assert _count("participant_loadouts") == 0


def test_non_remake_flag_false_is_stored():
    payload = make_payload([make_participant(champion_id=99)])
    payload["gameEndedInEarlySurrender"] = False
    result = ingest_match(payload, database_path=_DB)
    assert result["status"] == "created"
    assert _count("matches") == 1


def test_remake_flag_must_be_boolean():
    payload = make_payload([make_participant(champion_id=99)])
    payload["gameEndedInEarlySurrender"] = "yes"
    with pytest.raises(ValidationError):
        ingest_match(payload, database_path=_DB)


def test_idempotent_dedup_does_not_double_count():
    payload = make_payload(
        [make_participant(champion_id=99, augments=(7, 0, 0, 0))]
    )
    first = ingest_match(payload, database_path=_DB)
    second = ingest_match(payload, database_path=_DB)
    assert first["status"] == "created"
    assert second["status"] == "duplicate"
    assert _count("matches") == 1
    assert _count("participants") == 10
    assert _count("participant_augments") == 1


def test_zero_augments_dropped():
    payload = make_payload(
        [make_participant(champion_id=99, augments=(0, 0, 0, 0))]
    )
    ingest_match(payload, database_path=_DB)
    assert _count("participant_augments") == 0


def test_loadout_stored_per_participant():
    payload = make_payload(
        [
            make_participant(
                champion_id=99,
                items=(3047, 6692, 3071, 3133, 1037, 0, 3340),
                summoner_spells=(4, 32),
            )
        ]
    )
    ingest_match(payload, database_path=_DB)
    # One loadout row per participant (all 10), regardless of augment count.
    assert _count("participant_loadouts") == 10

    conn = get_connection(_DB)
    row = conn.execute(
        "SELECT * FROM participant_loadouts WHERE championId = 99"
    ).fetchone()
    assert (row["item0"], row["item6"]) == (3047, 3340)
    assert (row["summoner1"], row["summoner2"]) == (4, 32)


def test_loadout_items_normalized_to_seven_slots():
    # A short items list is zero-padded; an over-long one is truncated.
    payload = make_payload(
        [make_participant(champion_id=99, items=(1001, 1002), summoner_spells=(7,))]
    )
    ingest_match(payload, database_path=_DB)
    conn = get_connection(_DB)
    row = conn.execute(
        "SELECT * FROM participant_loadouts WHERE championId = 99"
    ).fetchone()
    assert (row["item0"], row["item1"], row["item2"], row["item6"]) == (
        1001,
        1002,
        0,
        0,
    )
    assert (row["summoner1"], row["summoner2"]) == (7, 0)


def test_loadout_optional_when_omitted():
    # A participant without items/summonerSpells still ingests (additive fields).
    bare = make_participant(champion_id=99)
    del bare["items"]
    del bare["summonerSpells"]
    payload = make_payload([bare])
    result = ingest_match(payload, database_path=_DB)
    assert result["status"] == "created"
    assert _count("participant_loadouts") == 10


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.pop("schemaVersion"),
        lambda p: p.pop("gameId"),
        lambda p: p.pop("queueId"),
        lambda p: p.pop("patch"),
        lambda p: p.pop("participants"),
        lambda p: p.update(schemaVersion=2),
        lambda p: p.update(queueId=450),
        lambda p: p.update(participants=p["participants"][:9]),
        lambda p: p.update(gameId="oops"),
        lambda p: p.update(patch=""),
    ],
)
def test_validation_rejections(mutate):
    payload = make_payload([make_participant(champion_id=99)])
    mutate(payload)
    with pytest.raises(ValidationError):
        ingest_match(payload, database_path=_DB)


@pytest.mark.parametrize(
    "field,value",
    [
        ("teamId", 999),
        ("participantId", 11),
        ("win", "Win"),
        ("kills", -1),
        ("championName", ""),
        ("championId", "x"),
        ("augments", "notalist"),
        ("items", "notalist"),
        ("items", [3047, -5]),
        ("summonerSpells", {"a": 1}),
        ("summonerSpells", [4, "Flash"]),
    ],
)
def test_participant_validation_rejections(field, value):
    bad = make_participant(champion_id=99)
    bad[field] = value
    payload = make_payload([bad])
    with pytest.raises(ValidationError):
        ingest_match(payload, database_path=_DB)


def test_non_object_payload_rejected():
    with pytest.raises(ValidationError):
        ingest_match([1, 2, 3], database_path=_DB)
