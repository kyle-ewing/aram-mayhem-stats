"""Static-data fetching for League item metadata.

This module does HTTP + URL building only (no Flask, no aggregation). It targets
Data Dragon's public item catalog, so like ``augments.py`` it is keyless: no Riot
API key is required or sent.

``fetch_item_metadata()`` resolves Data Dragon's ``item.json`` into a compact map
from item id (int) to display/classification metadata used by the itemization-stats
feature in ``app/services``.
"""
from __future__ import annotations

from typing import Optional

import requests

from ..config import Config
from ..errors import NotFoundError, RateLimitError, RiotApiError
from .augments import _parse_retry_after, latest_ddragon_version

# Network timeout (connect, read) in seconds.
_TIMEOUT = 10

# Data Dragon map id for Summoner's Rift. Used to skip mode-specific items
# (Arena/ARAM-only entries) that do not apply to a normal build tree.
_SUMMONERS_RIFT_MAP_ID = "11"


def _ddragon_item_url(version: str) -> str:
    return (
        f"https://ddragon.leagueoflegends.com/cdn/{version}"
        "/data/en_US/item.json"
    )


def _item_icon_url(image_full: Optional[str], item_id: int, version: str) -> str:
    """Build the Data Dragon item-icon URL.

    Prefers the ``image.full`` filename from item.json (e.g. ``"3031.png"``).
    Falls back to ``{item_id}.png`` when that field is missing.
    """
    filename = image_full if image_full else f"{item_id}.png"
    return (
        f"https://ddragon.leagueoflegends.com/cdn/{version}"
        f"/img/item/{filename}"
    )


def _is_legendary(entry: dict) -> bool:
    """Decide whether an item.json entry is a completed/legendary item.

    Rule implemented here (terminal, purchasable, non-consumable, real cost):

    * It must be purchasable (``gold.purchasable`` is truthy). Non-purchasable
      entries are quest rewards, ornn upgrades, or internal placeholders.
    * It must be terminal in the build tree: its ``into`` list is empty or
      absent, so nothing builds out of it. Components (Long Sword, B.F. Sword)
      always populate ``into`` and are excluded.
    * It must have a meaningful cost (``gold.total`` > 0), which drops free or
      zero-cost placeholder entries.
    * It must not be a consumable: the ``consumed``/``consumable`` flags are
      false and the ``tags`` list does not contain ``"Consumable"``. This drops
      potions and biscuits, which are terminal and purchasable but not items.
    * It must not be a trinket: the ``tags`` list does not contain ``"Trinket"``.

    This intentionally keeps basic starter components out (they have ``into``)
    while keeping completed items (Infinity Edge, Rabadon's Deathcap) in, even
    in mode-specific catalogs where ids are remapped.
    """
    gold = entry.get("gold") or {}
    if not gold.get("purchasable", False):
        return False

    into = entry.get("into") or []
    if into:
        return False

    if not isinstance(gold.get("total"), (int, float)) or gold.get("total", 0) <= 0:
        return False

    if entry.get("consumed") or entry.get("consumable"):
        return False

    tags = entry.get("tags") or []
    if "Consumable" in tags or "Trinket" in tags:
        return False

    return True


# Curated damage-type overrides keyed by item id.
#
# These are items whose damage identity (for example on-hit magic damage from a
# passive) cannot be derived from item.json's flat stats or tags, so the
# heuristic in ``_damage_type`` would misclassify them. They are pinned by hand
# here and should be revalidated each patch. Keep this map minimal: prefer the
# heuristic and only add an item when item.json genuinely cannot express its
# damage profile. Both the Summoner's Rift id and the Mayhem map-30 variant id
# (22xxxx pattern) are listed for safety.
_DAMAGE_TYPE_OVERRIDES = {
    # Wit's End (Summoner's Rift): on-hit magic damage from a passive, no flat
    # AP stat, so the heuristic would read its attack speed as pure AD.
    3091: "mixed",
    # Wit's End (Mayhem map-30 variant).
    223091: "mixed",
}


def _damage_type(entry: dict) -> str:
    """Classify an item's damage profile.

    Returns one of ``"AD"``, ``"AP"``, ``"mixed"``, or ``"other"``.

    Precedence (order matters):

    1. Both ``FlatPhysicalDamageMod`` and ``FlatMagicDamageMod`` > 0 => ``"mixed"``.
    2. ``FlatMagicDamageMod`` > 0 or ``"SpellDamage"`` in tags => ``"AP"``.
    3. ``FlatPhysicalDamageMod`` > 0 => ``"AD"``.
    4. ``FlatCritChanceMod`` > 0, ``PercentAttackSpeedMod`` > 0, or any of the
       AD-flavored tags ``"Damage"``/``"CriticalStrike"``/``"AttackSpeed"`` => ``"AD"``.
    5. Otherwise ``"other"``.
    """
    stats = entry.get("stats") or {}
    physical = stats.get("FlatPhysicalDamageMod", 0) or 0
    magic = stats.get("FlatMagicDamageMod", 0) or 0
    crit = stats.get("FlatCritChanceMod", 0) or 0
    attack_speed = stats.get("PercentAttackSpeedMod", 0) or 0
    tags = entry.get("tags") or []

    if physical > 0 and magic > 0:
        return "mixed"
    if magic > 0 or "SpellDamage" in tags:
        return "AP"
    if physical > 0:
        return "AD"
    if (
        crit > 0
        or attack_speed > 0
        or "Damage" in tags
        or "CriticalStrike" in tags
        or "AttackSpeed" in tags
    ):
        return "AD"
    return "other"


def fetch_item_metadata(
    version: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> dict[int, dict]:
    """Fetch League item metadata from Data Dragon's ``item.json``.

    This is a keyless public request; no Riot API key is required or sent.

    ``version`` defaults to the latest Data Dragon version (resolved and cached
    by ``latest_ddragon_version``), falling back to ``Config.DDRAGON_VERSION``.

    Returns a dict mapping item id (int) to a metadata dict::

        {
            "id": int,
            "name": str,
            "iconUrl": str,        # full Data Dragon item-icon URL
            "legendary": bool,     # completed/legendary item, not a component
            "damageType": str,     # "AD", "AP", "mixed", or "other"
        }

    Upstream failures map to ApiError subclasses: 404 -> NotFoundError,
    429 -> RateLimitError, other non-2xx and transport errors -> RiotApiError.
    """
    ddragon_version = (
        version if version is not None else latest_ddragon_version(session)
    )
    http = session or requests.Session()
    url = _ddragon_item_url(ddragon_version)

    try:
        resp = http.get(url, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise RiotApiError(
            f"Failed to reach Data Dragon ({type(exc).__name__})"
        ) from None

    status = resp.status_code

    if status == 404:
        raise NotFoundError("Item static data not found")

    if status == 429:
        raise RateLimitError(
            "Data Dragon rate limit exceeded",
            retry_after=_parse_retry_after(resp.headers.get("Retry-After")),
        )

    if not 200 <= status < 300:
        raise RiotApiError(f"Data Dragon error (status {status})")

    try:
        payload = resp.json()
    except ValueError:
        raise RiotApiError("Data Dragon returned a non-JSON response") from None

    items: dict[int, dict] = {}
    for raw_id, entry in (payload.get("data") or {}).items():
        try:
            item_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if not isinstance(entry, dict):
            continue

        image = entry.get("image") or {}
        damage_type = _DAMAGE_TYPE_OVERRIDES.get(item_id, _damage_type(entry))
        items[item_id] = {
            "id": item_id,
            "name": entry.get("name", ""),
            "iconUrl": _item_icon_url(
                image.get("full"), item_id, ddragon_version
            ),
            "legendary": _is_legendary(entry),
            "damageType": damage_type,
        }

    return items
