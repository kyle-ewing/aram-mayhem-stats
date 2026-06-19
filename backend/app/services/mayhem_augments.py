"""Curated ARAM Mayhem augment pool (hand-maintained reference).

The match/ingest payload only carries augment ids. Display names and tiers are
not in that data, and Community Dragon's arena bundle lists the full Arena pool
rather than the rotated ARAM Mayhem pool. This file is the curated source of
truth for which augments are actually in Mayhem, recorded by hand as they are
observed in game.

Flask-free. The data file is a JSON array of objects with keys: ``name``,
``tier`` (one of ``Silver``, ``Gold``, ``Prismatic``), ``id`` (the Community
Dragon augment id once known, else null), and ``notes`` (free text, optional).
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Optional

from ..errors import NotFoundError, ValidationError

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "mayhem_augments.json",
)

_VALID_TIERS = ("Silver", "Gold", "Prismatic")


def get_mayhem_augments(path: Optional[str] = None) -> list:
    """Read and return the curated Mayhem augment array.

    Degrades to ``[]`` if the file is missing or not a JSON array, so a missing
    dataset never breaks a caller.
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


def add_mayhem_augment(entry: dict, path: Optional[str] = None) -> dict:
    """Validate ``entry`` and append it to the curated Mayhem augment file.

    Returns the normalized stored record. Raises ``ValidationError`` (HTTP 400)
    for a bad payload or a duplicate name. The write is atomic (temp file +
    replace) so a crash mid-write cannot leave a truncated JSON file.
    """
    file_path = path if path is not None else _DATA_PATH
    record = _normalize_entry(entry)

    augments = get_mayhem_augments(file_path)
    existing = {
        str(a.get("name", "")).strip().lower()
        for a in augments
        if isinstance(a, dict)
    }
    if record["name"].lower() in existing:
        raise ValidationError(f"Augment '{record['name']}' is already in the list")

    augments.append(record)
    _write_atomic(file_path, augments)
    return record


def update_mayhem_augment(
    original_name: str, entry: dict, path: Optional[str] = None
) -> dict:
    """Replace the augment named ``original_name`` with a validated ``entry``.

    Matches the existing record by name (case-insensitive). Supports renaming,
    but rejects a rename that would collide with a different existing augment.
    Raises ``NotFoundError`` if no augment matches, ``ValidationError`` for a
    bad payload or a name collision. The write is atomic.
    """
    file_path = path if path is not None else _DATA_PATH
    record = _normalize_entry(entry)

    augments = get_mayhem_augments(file_path)
    target = original_name.strip().lower()

    index = next(
        (
            i
            for i, a in enumerate(augments)
            if isinstance(a, dict)
            and str(a.get("name", "")).strip().lower() == target
        ),
        None,
    )
    if index is None:
        raise NotFoundError(f"No augment named '{original_name}'")

    collision = any(
        i != index
        and isinstance(a, dict)
        and str(a.get("name", "")).strip().lower() == record["name"].lower()
        for i, a in enumerate(augments)
    )
    if collision:
        raise ValidationError(f"Augment '{record['name']}' is already in the list")

    # The edit form does not carry the icon, so keep the existing one on update.
    old = augments[index]
    if "icon" not in record and isinstance(old, dict) and old.get("icon"):
        record["icon"] = old["icon"]

    augments[index] = record
    _write_atomic(file_path, augments)
    return record


def _normalize_entry(entry: object) -> dict:
    """Coerce and validate one augment entry into the canonical shape."""
    if not isinstance(entry, dict):
        raise ValidationError("Augment entry must be a JSON object")

    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("Augment 'name' is required")

    tier = entry.get("tier")
    if tier not in _VALID_TIERS:
        raise ValidationError(
            f"Augment 'tier' must be one of {', '.join(_VALID_TIERS)}"
        )

    raw_id = entry.get("id")
    augment_id: Optional[int]
    if raw_id in (None, ""):
        augment_id = None
    elif isinstance(raw_id, bool):
        raise ValidationError("Augment 'id' must be an integer or null")
    elif isinstance(raw_id, int):
        augment_id = raw_id
    elif isinstance(raw_id, str) and raw_id.strip().lstrip("-").isdigit():
        augment_id = int(raw_id.strip())
    else:
        raise ValidationError("Augment 'id' must be an integer or null")

    notes = entry.get("notes", "")
    if notes is None:
        notes = ""
    if not isinstance(notes, str):
        raise ValidationError("Augment 'notes' must be a string")

    record = {
        "name": name.strip(),
        "tier": tier,
        "id": augment_id,
        "notes": notes.strip(),
    }

    # icon is optional display metadata (a full image URL). Only carry it when
    # present so hand-added augments stay {name, tier, id, notes}.
    icon = entry.get("icon")
    if isinstance(icon, str) and icon.strip():
        record["icon"] = icon.strip()
    return record


def _write_atomic(file_path: str, data: list) -> None:
    """Write ``data`` as pretty JSON to ``file_path`` atomically."""
    directory = os.path.dirname(os.path.abspath(file_path))
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp_path, file_path)
    except OSError:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
