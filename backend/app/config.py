"""Application configuration, loaded from environment variables."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    """Base config read from the environment.

    Keep all environment access here so the rest of the app depends on typed
    attributes rather than scattered ``os.environ`` lookups.
    """

    # Optional and unused by the core product. The first-party ingest pipeline
    # needs no Riot key, and the static-data helpers in riot/augments.py are
    # keyless. Kept only for possible future Riot calls; startup never requires it.
    RIOT_API_KEY: str = os.environ.get("RIOT_API_KEY", "")
    # ARAM Mayhem queue id; standard ARAM (450) carries no augment data.
    # Shared by the collector and ingest validation as one source of truth.
    ARAM_QUEUE_ID: int = int(os.environ.get("ARAM_QUEUE_ID", "2400"))

    # SQLite database file for ingested matches and aggregation. Use ":memory:"
    # for tests. Defaults to backend/mayhem.db.
    DATABASE_PATH: str = os.environ.get(
        "DATABASE_PATH", os.path.join(_BACKEND_DIR, "mayhem.db")
    )

    DEBUG: bool = os.environ.get("FLASK_DEBUG", "0") == "1"

    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.environ.get(
            "CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
        ).split(",")
        if origin.strip()
    ]

    # Riot static-data / Data Dragon version used for champion lookups.
    DDRAGON_VERSION: str = os.environ.get("DDRAGON_VERSION", "14.10.1")

    # Community Dragon version used for the arena augment static-data fetch.
    CDRAGON_VERSION: str = os.environ.get("CDRAGON_VERSION", "latest")
