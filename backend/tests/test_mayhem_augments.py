"""Tests for the curated Mayhem augment list service and its routes.

Uses a temp file so the real app/data/mayhem_augments.json is never touched.
"""
from __future__ import annotations

import json

import pytest

from app.errors import NotFoundError, ValidationError
from app.services import mayhem_augments as svc


@pytest.fixture
def data_file(tmp_path):
    path = tmp_path / "mayhem_augments.json"
    path.write_text("[]", encoding="utf-8")
    return str(path)


def test_get_returns_empty_for_missing_file(tmp_path):
    missing = str(tmp_path / "nope.json")
    assert svc.get_mayhem_augments(missing) == []


def test_get_returns_empty_for_non_array(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"not": "a list"}', encoding="utf-8")
    assert svc.get_mayhem_augments(str(path)) == []


def test_add_appends_and_normalizes(data_file):
    record = svc.add_mayhem_augment(
        {"name": "  Multishot  ", "tier": "Prismatic", "id": "166", "notes": " hi "},
        data_file,
    )
    assert record == {
        "name": "Multishot",
        "tier": "Prismatic",
        "id": 166,
        "notes": "hi",
    }
    stored = json.loads(open(data_file, encoding="utf-8").read())
    assert stored == [record]


def test_add_defaults_id_and_notes(data_file):
    record = svc.add_mayhem_augment({"name": "Vanish", "tier": "Silver"}, data_file)
    assert record == {"name": "Vanish", "tier": "Silver", "id": None, "notes": ""}


def test_add_keeps_icon_when_present(data_file):
    record = svc.add_mayhem_augment(
        {"name": "Deft", "tier": "Silver", "id": 1022, "icon": "https://x/deft.png"},
        data_file,
    )
    assert record["icon"] == "https://x/deft.png"


def test_update_preserves_existing_icon_when_omitted(data_file):
    svc.add_mayhem_augment(
        {"name": "Deft", "tier": "Silver", "id": 1022, "icon": "https://x/deft.png"},
        data_file,
    )
    # The edit form sends no icon; the stored icon should survive the update.
    updated = svc.update_mayhem_augment(
        "Deft", {"name": "Deft", "tier": "Gold", "id": 1022}, data_file
    )
    assert updated["tier"] == "Gold"
    assert updated["icon"] == "https://x/deft.png"


def test_add_rejects_missing_name(data_file):
    with pytest.raises(ValidationError):
        svc.add_mayhem_augment({"tier": "Gold"}, data_file)


def test_add_rejects_bad_tier(data_file):
    with pytest.raises(ValidationError):
        svc.add_mayhem_augment({"name": "X", "tier": "Bronze"}, data_file)


def test_add_rejects_bad_id(data_file):
    with pytest.raises(ValidationError):
        svc.add_mayhem_augment({"name": "X", "tier": "Gold", "id": "abc"}, data_file)


def test_add_rejects_duplicate_name_case_insensitive(data_file):
    svc.add_mayhem_augment({"name": "Multishot", "tier": "Prismatic"}, data_file)
    with pytest.raises(ValidationError):
        svc.add_mayhem_augment({"name": "multishot", "tier": "Gold"}, data_file)


def test_update_changes_fields(data_file):
    svc.add_mayhem_augment({"name": "Multishot", "tier": "Prismatic"}, data_file)
    updated = svc.update_mayhem_augment(
        "multishot", {"name": "Multishot", "tier": "Prismatic", "id": 166}, data_file
    )
    assert updated["id"] == 166
    stored = json.loads(open(data_file, encoding="utf-8").read())
    assert stored == [updated]


def test_update_supports_rename(data_file):
    svc.add_mayhem_augment({"name": "Old Name", "tier": "Gold"}, data_file)
    updated = svc.update_mayhem_augment(
        "Old Name", {"name": "New Name", "tier": "Gold"}, data_file
    )
    assert updated["name"] == "New Name"
    names = [a["name"] for a in svc.get_mayhem_augments(data_file)]
    assert names == ["New Name"]


def test_update_missing_raises_not_found(data_file):
    with pytest.raises(NotFoundError):
        svc.update_mayhem_augment("Ghost", {"name": "Ghost", "tier": "Gold"}, data_file)


def test_update_rename_collision_rejected(data_file):
    svc.add_mayhem_augment({"name": "Alpha", "tier": "Gold"}, data_file)
    svc.add_mayhem_augment({"name": "Beta", "tier": "Gold"}, data_file)
    with pytest.raises(ValidationError):
        svc.update_mayhem_augment(
            "Beta", {"name": "alpha", "tier": "Gold"}, data_file
        )


def test_update_same_name_no_false_collision(data_file):
    svc.add_mayhem_augment({"name": "Solo", "tier": "Gold", "id": 1}, data_file)
    updated = svc.update_mayhem_augment(
        "Solo", {"name": "Solo", "tier": "Silver", "id": 2}, data_file
    )
    assert updated == {"name": "Solo", "tier": "Silver", "id": 2, "notes": ""}


def test_route_put_updates(client, monkeypatch, tmp_path):
    path = tmp_path / "mayhem_augments.json"
    path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(svc, "_DATA_PATH", str(path))

    client.post("/api/mayhem-augments", json={"name": "Vanish", "tier": "Silver"})
    resp = client.put(
        "/api/mayhem-augments/Vanish",
        json={"name": "Vanish", "tier": "Silver", "id": 89},
    )
    assert resp.status_code == 200
    assert resp.get_json()["id"] == 89


def test_route_put_missing_returns_404(client, monkeypatch, tmp_path):
    path = tmp_path / "mayhem_augments.json"
    path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(svc, "_DATA_PATH", str(path))

    resp = client.put(
        "/api/mayhem-augments/Ghost", json={"name": "Ghost", "tier": "Gold"}
    )
    assert resp.status_code == 404


def test_route_get_lists(client):
    resp = client.get("/api/mayhem-augments")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_route_post_creates(client, monkeypatch, tmp_path):
    path = tmp_path / "mayhem_augments.json"
    path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(svc, "_DATA_PATH", str(path))

    resp = client.post(
        "/api/mayhem-augments",
        json={"name": "Stackasaurus", "tier": "Prismatic"},
    )
    assert resp.status_code == 201
    assert resp.get_json()["name"] == "Stackasaurus"


def test_route_post_rejects_bad_body(client):
    resp = client.post(
        "/api/mayhem-augments", json={"name": "", "tier": "Prismatic"}
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()
