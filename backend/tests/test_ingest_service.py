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
