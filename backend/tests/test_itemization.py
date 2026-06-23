"""Tests for champion itemization aggregation and its route.

Item metadata is injected via ``item_map`` so the service-level tests never hit
HTTP. Loadouts are seeded through the normal ingest path: ``make_participant``'s
``items`` slots flow into the ``participant_loadouts`` table.
"""
from __future__ import annotations

import pytest

from app.db import init_db, reset_memory_db
from app.riot.items import _DAMAGE_TYPE_OVERRIDES, _damage_type
from app.services import stats as stats_service
from app.services.ingest import ingest_match
from app.services.stats import champion_itemization
from tests.conftest import make_participant, make_payload

_DB = ":memory:"

# A small fake item catalog covering each case the service must handle:
# legendary AD/AP/mixed/other items, a component, a trinket, and a consumable.
# Item id 0 (empty slot) and any id absent from this map must be ignored as well.
ITEM_MAP = {
    101: {"id": 101, "name": "AD Item One", "iconUrl": "http://x/101.png",
          "legendary": True, "damageType": "AD"},
    102: {"id": 102, "name": "AD Item Two", "iconUrl": "http://x/102.png",
          "legendary": True, "damageType": "AD"},
    103: {"id": 103, "name": "AD Item Three", "iconUrl": "http://x/103.png",
          "legendary": True, "damageType": "AD"},
    201: {"id": 201, "name": "AP Item One", "iconUrl": "http://x/201.png",
          "legendary": True, "damageType": "AP"},
    202: {"id": 202, "name": "AP Item Two", "iconUrl": "http://x/202.png",
          "legendary": True, "damageType": "AP"},
    301: {"id": 301, "name": "Other Item", "iconUrl": "http://x/301.png",
          "legendary": True, "damageType": "other"},
    501: {"id": 501, "name": "Mixed Item One", "iconUrl": "http://x/501.png",
          "legendary": True, "damageType": "mixed"},
    502: {"id": 502, "name": "Mixed Item Two", "iconUrl": "http://x/502.png",
          "legendary": True, "damageType": "mixed"},
    400: {"id": 400, "name": "Boots Component", "iconUrl": "http://x/400.png",
          "legendary": False, "damageType": "other"},
    3340: {"id": 3340, "name": "Warding Totem", "iconUrl": "http://x/3340.png",
           "legendary": False, "damageType": "other"},
    2003: {"id": 2003, "name": "Health Potion", "iconUrl": "http://x/2003.png",
           "legendary": False, "damageType": "other"},
    999: {"id": 999, "name": "Never Built", "iconUrl": "http://x/999.png",
          "legendary": True, "damageType": "AP"},
}

# An id not present in ITEM_MAP at all; treated as unknown / non-legendary.
_UNKNOWN_ID = 55555


@pytest.fixture(autouse=True)
def _fresh_db():
    reset_memory_db()
    init_db(_DB)
    yield
    reset_memory_db()


def _ingest_game(game_id, champion_id, win, items):
    payload = make_payload(
        [
            make_participant(
                champion_id=champion_id,
                champion_name="Lux",
                win=win,
                items=items,
            )
        ],
        game_id=game_id,
    )
    ingest_match(payload, database_path=_DB)


def test_single_item_counts_dedupes_and_filters():
    # Three Lux games, each padded with components/trinket/consumable/empty/unknown
    # that must all be ignored. Item 101 appears in all three (deduped within a
    # game where it occupies two slots).
    _ingest_game(
        1, 99, True,
        (101, 101, 400, 3340, 2003, 0, _UNKNOWN_ID),
    )
    _ingest_game(
        2, 99, True,
        (101, 201, 0, 0, 0, 0, 0),
    )
    _ingest_game(
        3, 99, False,
        (101, 201, 0, 0, 0, 0, 0),
    )

    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    by_id = {it["itemId"]: it for it in result["items"]}

    assert set(by_id) == {101, 201}

    assert by_id[101]["games"] == 3
    assert by_id[101]["wins"] == 2
    assert by_id[101]["winRate"] == round(2 / 3, 4)
    assert by_id[101]["damageType"] == "AD"
    assert by_id[101]["itemName"] == "AD Item One"
    assert by_id[101]["iconUrl"] == "http://x/101.png"

    assert by_id[201]["games"] == 2
    assert by_id[201]["wins"] == 1
    assert by_id[201]["winRate"] == 0.5


def test_legendary_item_never_built_has_no_row():
    _ingest_game(1, 99, True, (101, 0, 0, 0, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    ids = {it["itemId"] for it in result["items"]}
    assert 999 not in ids


def test_items_sorted_by_games_then_winrate():
    # 101 in two games, 201 in one, 102 in one. 201 wins, 102 loses.
    _ingest_game(1, 99, True, (101, 201, 0, 0, 0, 0, 0))
    _ingest_game(2, 99, False, (101, 102, 0, 0, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    order = [it["itemId"] for it in result["items"]]
    # 101 has the most games (2) and leads. Then 201 (winRate 1.0) before 102 (0.0).
    assert order[0] == 101
    assert order.index(201) < order.index(102)


def _builds_by_name(result):
    return {b["build"]: b for b in result["builds"]}


def test_build_exactly_75_percent_ad_is_ad():
    # 3 AD + 1 AP, damageItems=4, adShare 3/4 = 0.75 -> AD.
    _ingest_game(1, 99, True, (101, 102, 103, 201, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    builds = _builds_by_name(result)
    assert builds["AD"]["games"] == 1
    assert builds["AP"]["games"] == 0
    assert builds["mixed"]["games"] == 0
    assert builds["other"]["games"] == 0


def test_build_just_under_75_percent_is_mixed():
    # 2 AD + 1 AP, damageItems=3, adShare 2/3 = 0.666 < 0.75, apShare 1/3 -> mixed.
    _ingest_game(1, 99, True, (101, 102, 201, 0, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    builds = _builds_by_name(result)
    assert builds["mixed"]["games"] == 1
    assert builds["AD"]["games"] == 0
    assert builds["AP"]["games"] == 0
    assert builds["other"]["games"] == 0


def test_build_full_ap_is_ap():
    _ingest_game(1, 99, True, (201, 202, 0, 0, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    builds = _builds_by_name(result)
    assert builds["AP"]["games"] == 1
    assert builds["AD"]["games"] == 0
    assert builds["mixed"]["games"] == 0
    assert builds["other"]["games"] == 0


def test_other_damage_item_dilutes_to_ad_at_threshold():
    # 3 AD + 1 other. "other"-typed items are not damage items, so they are
    # excluded from the denominator: damageItems=3, adShare 3/3 = 1.0 -> AD.
    # Still AD, but because other no longer dilutes, not because it sits at 0.75.
    _ingest_game(1, 99, True, (101, 102, 103, 301, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    builds = _builds_by_name(result)
    assert builds["AD"]["games"] == 1


def test_other_type_item_does_not_dilute_ad_share():
    # 2 AD + 1 other. "other" is excluded from damageItems, so damageItems=2,
    # adShare 2/2 = 1.0 -> AD. The other item does not pull this toward mixed.
    _ingest_game(1, 99, True, (101, 102, 301, 0, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    builds = _builds_by_name(result)
    assert builds["AD"]["games"] == 1
    assert builds["mixed"]["games"] == 0
    assert builds["other"]["games"] == 0


def test_game_with_no_legendary_items_skipped_from_builds_but_counts_overall():
    # Only a component, trinket, consumable, empty slot, and unknown id: no
    # legendary items, so no build bucket, but it is still a Lux game.
    _ingest_game(1, 99, False, (400, 3340, 2003, 0, _UNKNOWN_ID, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    assert result["games"] == 1
    assert result["wins"] == 0
    assert result["items"] == []
    for bucket in result["builds"]:
        assert bucket["games"] == 0
        assert bucket["winRate"] == 0.0


def test_builds_list_fixed_order_and_winrates():
    # AD: 2 games (1 win), AP: 1 game (1 win), mixed/other: none.
    _ingest_game(1, 99, True, (101, 102, 103, 0, 0, 0, 0))
    _ingest_game(2, 99, False, (101, 102, 103, 0, 0, 0, 0))
    _ingest_game(3, 99, True, (201, 202, 0, 0, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)

    builds = result["builds"]
    assert [b["build"] for b in builds] == ["AD", "AP", "mixed", "other"]

    by_name = _builds_by_name(result)
    assert by_name["AD"]["games"] == 2
    assert by_name["AD"]["wins"] == 1
    assert by_name["AD"]["winRate"] == 0.5
    assert by_name["AP"]["games"] == 1
    assert by_name["AP"]["winRate"] == 1.0
    assert by_name["mixed"]["games"] == 0
    assert by_name["mixed"]["winRate"] == 0.0
    assert by_name["other"]["games"] == 0
    assert by_name["other"]["winRate"] == 0.0


def test_mixed_type_item_classified():
    # Two mixed items, damageItems=2, no AD or AP share -> mixed bucket.
    _ingest_game(1, 99, True, (501, 502, 0, 0, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    builds = _builds_by_name(result)
    assert builds["mixed"]["games"] == 1
    assert builds["AD"]["games"] == 0
    assert builds["AP"]["games"] == 0
    assert builds["other"]["games"] == 0


def test_mixed_item_pulls_build_to_mixed_bucket():
    # 2 AD + 1 mixed, damageItems=3, adShare 2/3 = 0.666 < 0.75 -> mixed.
    _ingest_game(1, 99, True, (101, 102, 501, 0, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    builds = _builds_by_name(result)
    assert builds["mixed"]["games"] == 1
    assert builds["AD"]["games"] == 0


def test_build_three_ad_one_mixed_still_ad():
    # 3 AD + 1 mixed, damageItems=4, adShare 3/4 = 0.75 -> AD even though the
    # mixed item is in the denominator.
    _ingest_game(1, 99, True, (101, 102, 103, 501, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    builds = _builds_by_name(result)
    assert builds["AD"]["games"] == 1
    assert builds["mixed"]["games"] == 0


def test_all_other_items_bucket_other():
    # Only "other"-typed legendary items, damageItems=0 -> other bucket.
    _ingest_game(1, 99, True, (301, 0, 0, 0, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    builds = _builds_by_name(result)
    assert builds["other"]["games"] == 1
    assert builds["AD"]["games"] == 0
    assert builds["AP"]["games"] == 0
    assert builds["mixed"]["games"] == 0


def test_mixed_item_row_carries_mixed_damage_type():
    _ingest_game(1, 99, True, (501, 0, 0, 0, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    by_id = {it["itemId"]: it for it in result["items"]}
    assert by_id[501]["damageType"] == "mixed"


def test_overall_summary_shape():
    _ingest_game(1, 99, True, (101, 0, 0, 0, 0, 0, 0))
    _ingest_game(2, 99, False, (201, 0, 0, 0, 0, 0, 0))
    result = champion_itemization(99, _DB, item_map=ITEM_MAP)
    assert result["championId"] == 99
    assert result["championName"] == "Lux"
    assert result["iconUrl"].endswith("/img/champion/Lux.png")
    assert result["games"] == 2
    assert result["wins"] == 1
    assert result["winRate"] == 0.5


def test_unknown_champion_returns_none():
    _ingest_game(1, 99, True, (101, 0, 0, 0, 0, 0, 0))
    assert champion_itemization(7777, _DB, item_map=ITEM_MAP) is None


# -- route tests --------------------------------------------------------------


def test_route_returns_itemization(client, monkeypatch):
    monkeypatch.setattr(
        stats_service, "fetch_item_metadata", lambda *a, **k: ITEM_MAP
    )
    payload = make_payload(
        [
            make_participant(
                champion_id=99, champion_name="Lux", win=True,
                items=(101, 102, 103, 0, 0, 0, 0),
            )
        ]
    )
    assert client.post("/api/ingest/match", json=payload).status_code == 201

    resp = client.get("/api/champions/99/items")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["championId"] == 99
    assert [b["build"] for b in data["builds"]] == ["AD", "AP", "mixed", "other"]
    by_id = {it["itemId"]: it for it in data["items"]}
    assert by_id[101]["itemName"] == "AD Item One"
    assert by_id[101]["games"] == 1


def test_route_unknown_champion_returns_404(client, monkeypatch):
    monkeypatch.setattr(
        stats_service, "fetch_item_metadata", lambda *a, **k: ITEM_MAP
    )
    resp = client.get("/api/champions/12345/items")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# -- _damage_type / override unit tests (pure functions, no HTTP) -------------


def test_damage_type_both_flat_is_mixed():
    entry = {"stats": {"FlatPhysicalDamageMod": 40, "FlatMagicDamageMod": 45}}
    assert _damage_type(entry) == "mixed"


def test_damage_type_magic_only_is_ap():
    entry = {"stats": {"FlatMagicDamageMod": 80}}
    assert _damage_type(entry) == "AP"


def test_damage_type_spelldamage_tag_only_is_ap():
    entry = {"stats": {}, "tags": ["SpellDamage"]}
    assert _damage_type(entry) == "AP"


def test_damage_type_phys_only_is_ad():
    entry = {"stats": {"FlatPhysicalDamageMod": 55}}
    assert _damage_type(entry) == "AD"


def test_damage_type_crit_only_no_flat_ad_is_ad():
    entry = {
        "stats": {"FlatCritChanceMod": 0.25, "PercentAttackSpeedMod": 0.4},
        "tags": ["CriticalStrike", "AttackSpeed"],
    }
    assert _damage_type(entry) == "AD"


def test_damage_type_attack_speed_tag_only_is_ad():
    entry = {"stats": {}, "tags": ["AttackSpeed"]}
    assert _damage_type(entry) == "AD"


def test_damage_type_tank_stats_is_other():
    entry = {"stats": {"FlatHPPoolMod": 400, "FlatArmorMod": 30}, "tags": ["Health"]}
    assert _damage_type(entry) == "other"


def test_wits_end_override_sr_id_is_mixed():
    # Stats alone (attack speed, no flat AP) would resolve AD; the curated
    # override pins Wit's End (SR id 3091) to mixed.
    assert _DAMAGE_TYPE_OVERRIDES.get(3091) == "mixed"


def test_wits_end_override_mayhem_id_is_mixed():
    assert _DAMAGE_TYPE_OVERRIDES.get(223091) == "mixed"
