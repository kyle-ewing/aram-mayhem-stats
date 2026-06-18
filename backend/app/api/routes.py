"""API route handlers (thin blueprint).

Handlers parse/validate request input at the boundary, delegate to a service,
and jsonify the result. No business logic, no SQL, no Riot calls here.
``ApiError`` subclasses raised deeper in the stack propagate to the app's error
handler.

------------------------------------------------------------------------------
Endpoints and JSON response shapes (camelCase, frontend contract)
------------------------------------------------------------------------------
GET  /api/health
    {"status": "ok"}

POST /api/ingest/match
    201 {"status": "created", "gameId": <int>}      new match stored
    200 {"status": "duplicate", "gameId": <int>}    dedup, nothing changed
    400 {"error": <str>}                            validation failure
    Body: the canonical ingest payload (see collector/INGEST_CONTRACT.md).

GET  /api/champions
    [ {championId, championName, iconUrl, games, wins, winRate}, ... ]
    Sorted by games desc, then winRate desc.

GET  /api/champions/<championId>          (championId is the numeric Riot id)
    200 {championId, championName, iconUrl, games, wins, winRate,
         augments: [ {augmentId, augmentName, iconUrl, rarity,
                      games, wins, winRate}, ... ]}
    404 {"error": <str>}                  champion has no ingested games

GET  /api/augments
    [ {augmentId, augmentName, iconUrl, rarity, games, wins, winRate}, ... ]
    Sorted by games desc, then winRate desc.

GET  /api/synergies
    [ {champion, championId, augment, rarity, note, source}, ... ]
    Curated editorial notes, served from app/data/synergies.json ([] if absent).

GET  /api/mayhem-augments
    [ {name, tier, id, notes}, ... ]
    Curated ARAM Mayhem augment pool, from app/data/mayhem_augments.json.

POST /api/mayhem-augments
    201 {name, tier, id, notes}             new augment appended to the file
    400 {"error": <str>}                    validation failure or duplicate name
    Body: {name (req), tier (req: Silver|Gold|Prismatic), id (int|null), notes}

PUT  /api/mayhem-augments/<name>           (<name> is the current augment name)
    200 {name, tier, id, notes}             augment updated (supports rename)
    400 {"error": <str>}                    validation failure or name collision
    404 {"error": <str>}                    no augment with that name
    Body: same shape as POST.
------------------------------------------------------------------------------
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..errors import NotFoundError, ValidationError
from ..services.ingest import ingest_match
from ..services.stats import (
    augment_leaderboard,
    champion_detail,
    champion_winrates,
)
from ..services.synergies import get_synergies
from ..services.mayhem_augments import (
    add_mayhem_augment,
    get_mayhem_augments,
    update_mayhem_augment,
)

bp = Blueprint("api", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.post("/ingest/match")
def ingest():
    payload = request.get_json(silent=True)
    if payload is None:
        raise ValidationError("Request body must be valid JSON")
    result = ingest_match(payload)
    status_code = 201 if result["status"] == "created" else 200
    return jsonify(result), status_code


@bp.get("/champions")
def champions():
    return jsonify(champion_winrates())


@bp.get("/champions/<int:champion_id>")
def champion(champion_id: int):
    detail = champion_detail(champion_id)
    if detail is None:
        raise NotFoundError(f"No data for champion {champion_id}")
    return jsonify(detail)


@bp.get("/augments")
def augments():
    return jsonify(augment_leaderboard())


@bp.get("/synergies")
def synergies():
    return jsonify(get_synergies())


@bp.get("/mayhem-augments")
def mayhem_augments():
    return jsonify(get_mayhem_augments())


@bp.post("/mayhem-augments")
def add_mayhem_augment_route():
    payload = request.get_json(silent=True)
    if payload is None:
        raise ValidationError("Request body must be valid JSON")
    record = add_mayhem_augment(payload)
    return jsonify(record), 201


@bp.put("/mayhem-augments/<name>")
def update_mayhem_augment_route(name: str):
    payload = request.get_json(silent=True)
    if payload is None:
        raise ValidationError("Request body must be valid JSON")
    record = update_mayhem_augment(name, payload)
    return jsonify(record)
