"""Shared pytest fixtures and helpers.

Ensures the ``backend`` directory is importable so ``import app`` works no matter
where pytest is invoked from, and points the app at a fresh in-memory SQLite
database per test so ingest/aggregation tests are isolated and never touch disk
or the live network.
"""
from __future__ import annotations

import os
import sys

import pytest

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Use an in-memory database for the whole test session. Set before app/config
# import so Config picks it up.
os.environ["DATABASE_PATH"] = ":memory:"

from app import create_app  # noqa: E402
from app import db as _db  # noqa: E402
from app.config import Config  # noqa: E402
from app.db import init_db  # noqa: E402


@pytest.fixture
def app():
    # Reset the shared in-memory database so each test starts clean.
    _db.reset_memory_db()
    init_db(":memory:")
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def make_participant(
    *,
    participant_id=1,
    champion_name="Lux",
    champion_id=99,
    team_id=100,
    win=True,
    kills=5,
    deaths=4,
    assists=10,
    damage=18000,
    augments=(0, 0, 0, 0),
    items=(0, 0, 0, 0, 0, 0, 0),
    summoner_spells=(0, 0),
):
    """Build a single canonical-contract participant dict."""
    return {
        "participantId": participant_id,
        "championId": champion_id,
        "championName": champion_name,
        "teamId": team_id,
        "win": win,
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "totalDamageDealtToChampions": damage,
        "augments": list(augments),
        "items": list(items),
        "summonerSpells": list(summoner_spells),
    }


def make_payload(participants=None, *, game_id=1, queue_id=None, patch="26.12"):
    """Build a canonical ingest payload with exactly 10 participants.

    When ``participants`` is shorter than 10, the remainder is filled with
    distinct losing/winning enemy fillers so the payload passes the exactly-ten
    contract check. ``queue_id`` defaults to the configured Mayhem queue id.
    """
    queue_id = queue_id if queue_id is not None else Config.ARAM_QUEUE_ID
    participants = list(participants or [])

    next_pid = len(participants) + 1
    while len(participants) < 10:
        team = 100 if next_pid <= 5 else 200
        participants.append(
            make_participant(
                participant_id=next_pid,
                champion_name=f"Filler{next_pid}",
                champion_id=900 + next_pid,
                team_id=team,
                win=team == 100,
                augments=(0, 0, 0, 0),
            )
        )
        next_pid += 1

    return {
        "schemaVersion": 1,
        "gameId": game_id,
        "queueId": queue_id,
        "patch": patch,
        "gameVersion": "26.12.123.4567",
        "gameCreation": 1718700000000,
        "gameDuration": 1234,
        "participants": participants,
    }
