"""Curated champion+augment synergy notes (editorial, not measured).

These notes are hand-authored guidance, distinct from the measured winrates the
stats service computes. They are served verbatim from a JSON file on disk so a
teammate can drop in the full curated list without code changes.

Flask-free. The file is a JSON array of objects with keys: ``champion``,
``championId``, ``augment``, ``rarity``, ``note``, ``source``.
"""
from __future__ import annotations

import json
import os
from typing import Optional

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "synergies.json",
)


def get_synergies(path: Optional[str] = None) -> list:
    """Read and return the curated synergy array.

    Degrades to ``[]`` if the file is missing or not a JSON array, so a missing
    dataset never breaks the endpoint.
    """
    file_path = path if path is not None else _DATA_PATH
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, ValueError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return data
