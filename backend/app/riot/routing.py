"""Riot region routing.

Riot splits its API across two kinds of hosts:

* **Platform hosts** (``na1``, ``euw1``, ``kr`` …) serve summoner/league/spectator
  data tied to a specific shard.
* **Regional cluster hosts** (``americas`` / ``asia`` / ``europe``) serve the newer
  account-v1 and match-v5 endpoints.

This module maps a platform region string to both host kinds. Region strings are
accepted case-insensitively.
"""
from __future__ import annotations

from ..errors import NotFoundError

# Platform region -> regional cluster used for account-v1 / match-v5.
_PLATFORM_TO_CLUSTER: dict[str, str] = {
    # Americas
    "na1": "americas",
    "br1": "americas",
    "la1": "americas",
    "la2": "americas",
    "oc1": "americas",
    # Asia
    "kr": "asia",
    "jp1": "asia",
    # Europe
    "euw1": "europe",
    "eun1": "europe",
    "tr1": "europe",
    "ru": "europe",
}

# Clusters are also valid as-is for callers that already know the cluster.
_CLUSTERS = frozenset({"americas", "asia", "europe"})


def _normalize(region: str) -> str:
    return (region or "").strip().lower()


def platform_host(region: str) -> str:
    """Return the platform host URL for ``region`` (e.g. ``https://na1.api.riotgames.com``).

    Raises ``NotFoundError`` for an unknown region.
    """
    key = _normalize(region)
    if key not in _PLATFORM_TO_CLUSTER:
        raise NotFoundError(f"Unknown region: {region!r}")
    return f"https://{key}.api.riotgames.com"


def regional_host(region: str) -> str:
    """Return the regional cluster host URL for ``region``.

    Accepts either a platform region (``na1`` -> ``americas``) or a cluster name
    (``americas``) directly. Raises ``NotFoundError`` for an unknown region.
    """
    key = _normalize(region)
    if key in _CLUSTERS:
        cluster = key
    elif key in _PLATFORM_TO_CLUSTER:
        cluster = _PLATFORM_TO_CLUSTER[key]
    else:
        raise NotFoundError(f"Unknown region: {region!r}")
    return f"https://{cluster}.api.riotgames.com"


def regional_cluster(region: str) -> str:
    """Return the bare regional cluster name (``americas``/``asia``/``europe``)."""
    key = _normalize(region)
    if key in _CLUSTERS:
        return key
    if key in _PLATFORM_TO_CLUSTER:
        return _PLATFORM_TO_CLUSTER[key]
    raise NotFoundError(f"Unknown region: {region!r}")
