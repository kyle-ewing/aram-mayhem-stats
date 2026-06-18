"""Route tests via Flask's test_client. No live HTTP; augment static data is
injected into the stats service through monkeypatch so routes never hit the net.
"""
from __future__ import annotations

import pytest

from app.services import stats as stats_service
from tests.conftest import make_participant, make_payload

_MAYHEM_POOL = [
    {"name": "Symphony of War", "tier": "Gold", "id": 7, "notes": ""},
]


@pytest.fixture(autouse=True)
def _stub_augments(monkeypatch):
    """Inject a fixed curated Mayhem pool so stats endpoints resolve names
    from a known dataset rather than the real data file."""
    monkeypatch.setattr(
        stats_service,
        "get_mayhem_augments",
        lambda *a, **k: [dict(e) for e in _MAYHEM_POOL],
    )


def _ingest(client, payload):
    return client.post("/api/ingest/match", json=payload)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_ingest_happy_returns_201(client):
    payload = make_payload(
        [make_participant(champion_id=99, win=True, augments=(7, 0, 0, 0))]
    )
    resp = _ingest(client, payload)
    assert resp.status_code == 201
    assert resp.get_json() == {"status": "created", "gameId": 1}


def test_ingest_duplicate_returns_200(client):
    payload = make_payload(
        [make_participant(champion_id=99, augments=(7, 0, 0, 0))]
    )
    assert _ingest(client, payload).status_code == 201
    resp = _ingest(client, payload)
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "duplicate", "gameId": 1}


def test_ingest_remake_returns_200_skipped(client):
    payload = make_payload(
        [make_participant(champion_id=99, augments=(7, 0, 0, 0))]
    )
    payload["gameEndedInEarlySurrender"] = True
    resp = _ingest(client, payload)
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "skipped", "gameId": 1}
    # The remade game left nothing behind to aggregate.
    assert client.get("/api/champions").get_json() == []


def test_ingest_invalid_returns_400(client):
    payload = make_payload()
    del payload["queueId"]
    resp = _ingest(client, payload)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_ingest_non_json_returns_400(client):
    resp = client.post(
        "/api/ingest/match", data="not json", content_type="application/json"
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_champions_list_shape(client):
    _ingest(
        client,
        make_payload(
            [make_participant(champion_id=99, champion_name="Lux", win=True)]
        ),
    )
    resp = client.get("/api/champions")
    assert resp.status_code == 200
    data = resp.get_json()
    lux = next(c for c in data if c["championId"] == 99)
    assert lux["championName"] == "Lux"
    assert lux["games"] == 1
    assert lux["wins"] == 1
    assert lux["winRate"] == 1.0
    assert lux["iconUrl"].endswith("/img/champion/Lux.png")


def test_champion_detail_shape(client):
    _ingest(
        client,
        make_payload(
            [
                make_participant(
                    champion_id=99, champion_name="Lux", win=True,
                    augments=(7, 0, 0, 0),
                )
            ]
        ),
    )
    resp = client.get("/api/champions/99")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["championId"] == 99
    assert data["winRate"] == 1.0
    aug = next(a for a in data["augments"] if a["augmentId"] == 7)
    assert aug["augmentName"] == "Symphony of War"
    assert aug["rarity"] == "Gold"
    assert aug["iconUrl"] is None
    assert aug["games"] == 1


def test_champion_detail_unknown_returns_404(client):
    resp = client.get("/api/champions/12345")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_augments_leaderboard_shape(client):
    _ingest(
        client,
        make_payload(
            [make_participant(champion_id=99, win=True, augments=(7, 0, 0, 0))]
        ),
    )
    resp = client.get("/api/augments")
    assert resp.status_code == 200
    data = resp.get_json()
    aug = next(a for a in data if a["augmentId"] == 7)
    assert aug["augmentName"] == "Symphony of War"
    assert aug["games"] == 1
    assert aug["winRate"] == 1.0


def test_synergies_returns_array(client):
    resp = client.get("/api/synergies")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    if data:
        entry = data[0]
        for key in ("champion", "championId", "augment", "rarity", "note", "source"):
            assert key in entry
