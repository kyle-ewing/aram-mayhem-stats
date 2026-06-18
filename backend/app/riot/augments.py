"""Static-data fetching for ARAM Mayhem augments and champion icons.

This module does HTTP + URL building only (no Flask, no aggregation). It targets
public static data, so unlike ``client.py`` it does NOT require a Riot API key:

* Augment static data comes from Community Dragon's arena bundle.
* Champion icons come from Data Dragon and only need a pinned version.

Augment ids are the integers found on match-v5 participants (``playerAugment1..N``).
``fetch_augments()`` resolves those ids to display info (name, rarity, full icon
URLs) for downstream enrichment in ``app/services``.
"""
from __future__ import annotations

from typing import Optional

import requests

from ..config import Config
from ..errors import NotFoundError, RateLimitError, RiotApiError

# Network timeout (connect, read) in seconds.
_TIMEOUT = 10

# Community Dragon asset paths are served relative to this base. Icon paths in
# the arena bundle are sometimes absolute under the game-data plugin; this prefix
# is stripped before joining so both forms resolve to the same URL.
_CDRAGON_GAME_DATA_PREFIX = "/lol-game-data/assets/"


def _cdragon_arena_url(version: str) -> str:
    return f"https://raw.communitydragon.org/{version}/cdragon/arena/en_us.json"


def _cdragon_asset_base(version: str) -> str:
    return (
        f"https://raw.communitydragon.org/{version}"
        "/plugins/rcp-be-lol-game-data/global/default/"
    )


def _normalize_icon_url(icon_path: Optional[str], version: str) -> Optional[str]:
    """Turn a raw arena icon path into a full Community Dragon image URL.

    Handles both the absolute ``/lol-game-data/assets/...`` form and the bare
    ``ASSETS/...`` form. The remaining path is lowercased to match the way
    Community Dragon serves these assets. Returns None for an empty path.
    """
    if not icon_path:
        return None

    path = icon_path
    if path.startswith(_CDRAGON_GAME_DATA_PREFIX):
        path = path[len(_CDRAGON_GAME_DATA_PREFIX):]

    path = path.lstrip("/").lower()
    return _cdragon_asset_base(version) + path


def champion_icon_url(
    champion_name: str, version: Optional[str] = None
) -> str:
    """Build the Data Dragon champion square-icon URL for ``champion_name``.

    ``champion_name`` is the Data Dragon champion id, which match-v5 exposes as
    ``participant.championName`` (e.g. ``"MonkeyKing"``, ``"Fiddlesticks"``).
    ``version`` defaults to ``Config.DDRAGON_VERSION``.
    """
    ddragon_version = version if version is not None else Config.DDRAGON_VERSION
    return (
        f"https://ddragon.leagueoflegends.com/cdn/{ddragon_version}"
        f"/img/champion/{champion_name}.png"
    )


def fetch_augments(
    version: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> dict[int, dict]:
    """Fetch ARAM Mayhem / arena augment static data from Community Dragon.

    This is a keyless public request; no Riot API key is required or sent.

    Returns a dict mapping augment id (int) to a display-info dict::

        {
            "id": int,
            "name": str,
            "iconLarge": str | None,   # full normalized image URL
            "iconSmall": str | None,   # full normalized image URL
            "rarity": int,             # 0 silver, 1 gold, 2 prismatic
            "desc": str,
        }

    ``version`` defaults to ``Config.CDRAGON_VERSION`` (e.g. ``"latest"``).
    Upstream failures map to ApiError subclasses: 404 -> NotFoundError,
    429 -> RateLimitError, other non-2xx and transport errors -> RiotApiError.
    """
    cdragon_version = version if version is not None else Config.CDRAGON_VERSION
    http = session or requests.Session()
    url = _cdragon_arena_url(cdragon_version)

    try:
        resp = http.get(url, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        # Use the class name only so config/headers cannot be echoed back.
        raise RiotApiError(
            f"Failed to reach Community Dragon ({type(exc).__name__})"
        ) from None

    status = resp.status_code

    if status == 404:
        raise NotFoundError("Augment static data not found")

    if status == 429:
        raise RateLimitError(
            "Community Dragon rate limit exceeded",
            retry_after=_parse_retry_after(resp.headers.get("Retry-After")),
        )

    if not 200 <= status < 300:
        raise RiotApiError(f"Community Dragon error (status {status})")

    try:
        payload = resp.json()
    except ValueError:
        raise RiotApiError(
            "Community Dragon returned a non-JSON response"
        ) from None

    augments: dict[int, dict] = {}
    for entry in payload.get("augments", []):
        augment_id = entry.get("id")
        if augment_id is None:
            continue
        augments[augment_id] = {
            "id": augment_id,
            "name": entry.get("name", ""),
            "iconLarge": _normalize_icon_url(
                entry.get("iconLarge"), cdragon_version
            ),
            "iconSmall": _normalize_icon_url(
                entry.get("iconSmall"), cdragon_version
            ),
            "rarity": entry.get("rarity", 0),
            "desc": entry.get("desc", ""),
        }

    return augments


def _parse_retry_after(value: Optional[str]) -> Optional[int]:
    """Parse the Retry-After header into seconds, or None if absent/invalid."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
