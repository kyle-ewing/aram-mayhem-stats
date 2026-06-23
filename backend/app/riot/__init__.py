"""Riot static-data helpers (keyless).

The per-summoner match-v5 client was removed: Riot's public match-v5 API returns
403 for ARAM Mayhem on purpose, so winrates now come from first-party ingest.

What remains here is keyless public static data only:

* augment name/icon/rarity resolution via Community Dragon (``fetch_augments``)
* champion square-icon URLs via Data Dragon (``champion_icon_url``)
* item name/icon/classification via Data Dragon (``fetch_item_metadata``)

No Flask, no aggregation, no Riot API key.
"""
from __future__ import annotations

from .augments import (
    champion_icon_url,
    fetch_augments,
    latest_ddragon_version,
)
from .items import fetch_item_metadata
from .routing import platform_host, regional_cluster, regional_host

__all__ = [
    "fetch_augments",
    "fetch_item_metadata",
    "champion_icon_url",
    "latest_ddragon_version",
    "platform_host",
    "regional_host",
    "regional_cluster",
]
