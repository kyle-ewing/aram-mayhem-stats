"""Tests for augment static-data fetching. HTTP is mocked with `responses`."""
from __future__ import annotations

import pytest
import responses

from app.config import Config
from app.errors import NotFoundError, RateLimitError, RiotApiError
from app.riot import champion_icon_url, fetch_augments, latest_ddragon_version
from app.riot import augments as augmod

_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"

_VERSION = "latest"
_ARENA_URL = (
    f"https://raw.communitydragon.org/{_VERSION}/cdragon/arena/en_us.json"
)
_ASSET_BASE = (
    f"https://raw.communitydragon.org/{_VERSION}"
    "/plugins/rcp-be-lol-game-data/global/default/"
)


def _arena_payload():
    return {
        "augments": [
            {
                "id": 1,
                "name": "Apex Inventor",
                "apiName": "ApexInventor",
                "rarity": 2,
                "desc": "Become the apex inventor.",
                "tooltip": "tt",
                "dataValues": {},
                "iconLarge": (
                    "/lol-game-data/assets/ASSETS/Augments/Icons/ApexLarge.png"
                ),
                "iconSmall": (
                    "/lol-game-data/assets/ASSETS/Augments/Icons/ApexSmall.png"
                ),
            },
            {
                "id": 2,
                "name": "Blade Waltz",
                "apiName": "BladeWaltz",
                "rarity": 0,
                "desc": "Dance with blades.",
                "tooltip": "tt",
                "dataValues": {},
                "iconLarge": "ASSETS/Ux/Augments/BladeLarge.png",
                "iconSmall": "ASSETS/Ux/Augments/BladeSmall.png",
            },
        ]
    }


@responses.activate
def test_fetch_augments_happy_id_to_name_mapping():
    responses.add(
        responses.GET, _ARENA_URL, json=_arena_payload(), status=200
    )
    augments = fetch_augments(version=_VERSION)

    assert set(augments) == {1, 2}
    assert augments[1]["name"] == "Apex Inventor"
    assert augments[1]["rarity"] == 2
    assert augments[1]["desc"] == "Become the apex inventor."
    assert augments[2]["name"] == "Blade Waltz"
    assert augments[2]["rarity"] == 0


@responses.activate
def test_icon_url_normalization_prefixed_path():
    responses.add(
        responses.GET, _ARENA_URL, json=_arena_payload(), status=200
    )
    augments = fetch_augments(version=_VERSION)

    expected_large = _ASSET_BASE + "assets/augments/icons/apexlarge.png"
    expected_small = _ASSET_BASE + "assets/augments/icons/apexsmall.png"
    assert augments[1]["iconLarge"] == expected_large
    assert augments[1]["iconSmall"] == expected_small


@responses.activate
def test_icon_url_normalization_unprefixed_path():
    responses.add(
        responses.GET, _ARENA_URL, json=_arena_payload(), status=200
    )
    augments = fetch_augments(version=_VERSION)

    expected_large = _ASSET_BASE + "assets/ux/augments/bladelarge.png"
    expected_small = _ASSET_BASE + "assets/ux/augments/bladesmall.png"
    assert augments[2]["iconLarge"] == expected_large
    assert augments[2]["iconSmall"] == expected_small


@responses.activate
def test_fetch_augments_404_maps_to_not_found():
    responses.add(responses.GET, _ARENA_URL, status=404)
    with pytest.raises(NotFoundError):
        fetch_augments(version=_VERSION)


@responses.activate
def test_fetch_augments_429_maps_to_rate_limit_with_retry_after():
    responses.add(
        responses.GET,
        _ARENA_URL,
        status=429,
        headers={"Retry-After": "7"},
    )
    with pytest.raises(RateLimitError) as exc:
        fetch_augments(version=_VERSION)
    assert exc.value.retry_after == 7


@responses.activate
def test_fetch_augments_500_maps_to_riot_api_error():
    responses.add(responses.GET, _ARENA_URL, status=500)
    with pytest.raises(RiotApiError):
        fetch_augments(version=_VERSION)


@responses.activate
def test_fetch_augments_works_without_riot_api_key(monkeypatch):
    monkeypatch.setattr(Config, "RIOT_API_KEY", "")
    responses.add(
        responses.GET, _ARENA_URL, json=_arena_payload(), status=200
    )
    augments = fetch_augments(version=_VERSION)
    assert augments[1]["name"] == "Apex Inventor"


def test_champion_icon_url_uses_ddragon_version():
    url = champion_icon_url("MonkeyKing", version="14.10.1")
    assert url == (
        "https://ddragon.leagueoflegends.com/cdn/14.10.1"
        "/img/champion/MonkeyKing.png"
    )


@responses.activate
def test_latest_ddragon_version_returns_newest(monkeypatch):
    monkeypatch.setattr(augmod, "_latest_version", None)
    responses.add(
        responses.GET, _VERSIONS_URL, json=["16.12.1", "16.11.1", "16.10.1"], status=200
    )
    assert latest_ddragon_version() == "16.12.1"


@responses.activate
def test_latest_ddragon_version_caches_after_first_lookup(monkeypatch):
    monkeypatch.setattr(augmod, "_latest_version", None)
    responses.add(responses.GET, _VERSIONS_URL, json=["16.12.1"], status=200)
    latest_ddragon_version()
    latest_ddragon_version()
    # Cached: only one HTTP call despite two resolver calls.
    assert len(responses.calls) == 1


@responses.activate
def test_latest_ddragon_version_falls_back_on_error(monkeypatch):
    monkeypatch.setattr(augmod, "_latest_version", None)
    responses.add(responses.GET, _VERSIONS_URL, status=500)
    assert latest_ddragon_version() == Config.DDRAGON_VERSION


def test_champion_icon_url_defaults_to_resolved_latest(monkeypatch):
    monkeypatch.setattr(augmod, "_latest_version", "16.12.1")
    assert champion_icon_url("Lux") == (
        "https://ddragon.leagueoflegends.com/cdn/16.12.1/img/champion/Lux.png"
    )
