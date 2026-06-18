"""Tests for the aggregation service against a known ingested dataset.

Augment static data is injected so no HTTP happens. The dataset is constructed
so per-champion, per-augment, and synergy winrates have hand-checkable values.
"""
from __future__ import annotations

import pytest

from app.db import init_db, reset_memory_db
from app.services.ingest import ingest_match
from app.services.stats import (
    augment_leaderboard,
    champion_detail,
    champion_winrates,
)
from tests.conftest import make_participant, make_payload

_DB = ":memory:"

AUGMENT_MAP = {
    7: {
        "id": 7,
        "name": "Symphony of War",
        "iconLarge": "https://cdragon.example/symphony_large.png",
        "iconSmall": "https://cdragon.example/symphony_small.png",
        "rarity": 1,
        "desc": "",
    },
    12: {
        "id": 12,
        "name": "Blade Waltz",
        "iconLarge": "https://cdragon.example/blade_large.png",
        "iconSmall": "https://cdragon.example/blade_small.png",
        "rarity": 2,
        "desc": "",
    },
}


@pytest.fixture(autouse=True)
def _fresh_db():
    reset_memory_db()
    init_db(_DB)
    yield
    reset_memory_db()


def _seed():
    """Ingest a small known set of matches.

    Lux (championId 99) appears in 4 games:
      g1 win  with augment 7
      g2 win  with augment 7 and 12
      g3 loss with augment 12
      g4 loss (no augments)
    So Lux: 4 games, 2 wins, winRate 0.5.
    Augment 7: 2 games (g1,g2), 2 wins -> winRate 1.0.
    Augment 12: 2 games (g2 win, g3 loss) -> winRate 0.5.
    Lux+7 synergy: 2 games, 2 wins -> 1.0. Lux+12: 2 games, 1 win -> 0.5.
    """
    specs = [
        (1, True, (7, 0, 0, 0)),
        (2, True, (7, 12, 0, 0)),
        (3, False, (12, 0, 0, 0)),
        (4, False, (0, 0, 0, 0)),
    ]
    for game_id, win, augs in specs:
        payload = make_payload(
            [
                make_participant(
                    champion_id=99, champion_name="Lux", win=win, augments=augs
                )
            ],
            game_id=game_id,
        )
        ingest_match(payload, database_path=_DB)


def test_champion_winrates():
    _seed()
    champs = champion_winrates(_DB, augment_map=AUGMENT_MAP)
    lux = next(c for c in champs if c["championId"] == 99)
    assert lux["championName"] == "Lux"
    assert lux["games"] == 4
    assert lux["wins"] == 2
    assert lux["winRate"] == 0.5
    assert lux["iconUrl"].endswith("/img/champion/Lux.png")


def test_champion_detail_augments():
    _seed()
    detail = champion_detail(99, _DB, augment_map=AUGMENT_MAP)
    assert detail["games"] == 4
    assert detail["winRate"] == 0.5

    by_id = {a["augmentId"]: a for a in detail["augments"]}
    assert by_id[7]["games"] == 2
    assert by_id[7]["wins"] == 2
    assert by_id[7]["winRate"] == 1.0
    assert by_id[7]["augmentName"] == "Symphony of War"
    assert by_id[7]["rarity"] == 1
    assert by_id[12]["games"] == 2
    assert by_id[12]["wins"] == 1
    assert by_id[12]["winRate"] == 0.5


def test_champion_detail_unknown_is_none():
    _seed()
    assert champion_detail(7777, _DB, augment_map=AUGMENT_MAP) is None


def test_augment_leaderboard():
    _seed()
    board = augment_leaderboard(_DB, augment_map=AUGMENT_MAP)
    by_id = {a["augmentId"]: a for a in board}
    assert by_id[7]["games"] == 2
    assert by_id[7]["winRate"] == 1.0
    assert by_id[12]["games"] == 2
    assert by_id[12]["winRate"] == 0.5
    # Sorted by games desc then winRate desc: 7 (1.0) before 12 (0.5).
    assert board[0]["augmentId"] == 7


def test_augment_enrichment_degrades_without_map():
    _seed()
    board = augment_leaderboard(_DB, augment_map={})
    aug = next(a for a in board if a["augmentId"] == 7)
    assert aug["augmentName"] == "7"
    assert aug["iconUrl"] is None
    assert aug["rarity"] is None


def test_empty_database_yields_empty_lists():
    assert champion_winrates(_DB, augment_map=AUGMENT_MAP) == []
    assert augment_leaderboard(_DB, augment_map=AUGMENT_MAP) == []
