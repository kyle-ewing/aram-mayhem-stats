"""Tests for region routing."""
from __future__ import annotations

import pytest

from app.errors import NotFoundError
from app.riot.routing import platform_host, regional_cluster, regional_host


def test_platform_host_happy():
    assert platform_host("na1") == "https://na1.api.riotgames.com"
    # Case-insensitive.
    assert platform_host("EUW1") == "https://euw1.api.riotgames.com"


def test_platform_host_unknown_region():
    with pytest.raises(NotFoundError):
        platform_host("zz9")


def test_regional_host_from_platform():
    assert regional_host("na1") == "https://americas.api.riotgames.com"
    assert regional_host("kr") == "https://asia.api.riotgames.com"
    assert regional_host("euw1") == "https://europe.api.riotgames.com"


def test_regional_host_accepts_cluster_directly():
    assert regional_host("americas") == "https://americas.api.riotgames.com"


def test_regional_host_unknown_region():
    with pytest.raises(NotFoundError):
        regional_host("nowhere")


def test_regional_cluster_happy():
    assert regional_cluster("na1") == "americas"
    assert regional_cluster("jp1") == "asia"
    assert regional_cluster("europe") == "europe"


def test_regional_cluster_unknown_region():
    with pytest.raises(NotFoundError):
        regional_cluster("xx1")
