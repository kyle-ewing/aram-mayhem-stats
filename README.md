# Aram Mayhem Stats

A web app that surfaces **ARAM Mayhem statistics** from *League of Legends*. It is
champion-centric: browse a grid of champions, open a champion to see its ARAM Mayhem
win rate, per-augment win rates with sample sizes, and curated notes on strong synergies.
Augments are first-class, because ARAM Mayhem is built around them.

The numbers come from our **own first-party data**, not from the Riot web API. See
[Why the data is first-party](#why-the-data-is-first-party) below.

- **Backend:** Flask (Python 3.11+), SQLite storage, stats aggregation. No Riot API key
  needed for the core product.
- **Collector:** a Node app that reads each opted-in player's local League client and
  uploads finished Mayhem games to the backend.
- **Frontend:** React + Vite.

## Why the data is first-party

Riot's public match-v5 API returns **403 Forbidden** for ARAM Mayhem matches, intentionally
(Riot dev-relations issue [#1109](https://github.com/RiotGames/developer-relations/issues/1109),
closed working-as-intended). Win/loss for Mayhem games cannot be read from the Riot web API,
so the old per-summoner Riot-ID lookup flow has been removed.

Instead, aram-mayhem-stats is fed by an **LCU collector**. The local League Client Update (LCU)
API, running on a player's own machine while their client is open, *can* see full Mayhem
results including augments. The collector reads those finished games, maps them to a
canonical ingest payload, and POSTs them to the backend, which stores and aggregates them.
Participation is opt-in.

Champion and augment static data (names, icons) stays **keyless**, pulled from Data Dragon
and Community Dragon, so the core product needs no Riot API key. `RIOT_API_KEY` is now
optional and unused by the core flow.

## Prerequisites

- **Python 3.11+** for the backend (the default `python` on this machine is 3.6.8, which is
  EOL; install a newer one from <https://www.python.org/downloads/> or
  `winget install Python.Python.3.12`).
- **Node 18+** for the collector and the frontend (you have v22).
- For the collector only: a **running League of Legends client** on the same machine, and
  the player opting in.

## Setup

### Backend

Run the setup script. It creates the venv (Python 3.12), installs deps, ensures a
`.env` exists, then serves on http://127.0.0.1:5000. Re-running reuses the existing
venv, so it is safe to use as your everyday start command:

```bash
bash backend/dev.sh
```

On first run the database is empty, so champion and augment endpoints return empty lists and
the frontend shows a cold-start state. Data appears once collectors start ingesting games.

### Collector

The collector is a Node app that reads the local League client (the LCU API) and uploads
finished ARAM Mayhem games to the backend.

```bash
cd collector
npm install
npm start                       # connects to the local League client, POSTs games to the backend
```

Prerequisites: Node 18+ and a running League of Legends client on the same machine.
Participation is opt-in. The collector points at the backend (default
`http://127.0.0.1:5000`) and POSTs each finished Mayhem game as a canonical payload. The
ingest contract is documented in `collector/INGEST_CONTRACT.md`.

### Frontend

```bash
cd frontend
npm install
npm run dev                     # serves http://127.0.0.1:5173, proxies /api -> backend
```

## Project layout

```
backend/      Flask API (app factory, SQLite store, ingest + stats + synergies services, tests)
collector/    Node LCU collector that uploads local Mayhem games to the backend
frontend/     React + Vite champion-centric single-page app
.devcontainer/ Sandboxed Linux container for running Claude Code (see above)
.claude/      Project subagents and harness config for agentic workflows
CLAUDE.md   Conventions and architecture notes for future agent runs
```

## API

| Method | Path                       | Description                                                                                  |
|--------|----------------------------|----------------------------------------------------------------------------------------------|
| GET    | `/api/health`              | Health check. Returns `{"status":"ok"}`.                                                     |
| POST   | `/api/ingest/match`        | Ingest one match (canonical payload per `collector/INGEST_CONTRACT.md`). 201 created, 200 duplicate (idempotent dedup by `gameId`), 400 validation error. |
| GET    | `/api/champions`           | List of champions with `games`, `wins`, `winRate`, `iconUrl`. May be empty at cold start.    |
| GET    | `/api/champions/<championId>` | Champion detail for a numeric `championId`: champion `winRate`/`games`/icon plus that champion's augment win rates. 404 if no ingested games. |
| GET    | `/api/augments`            | Augment leaderboard across all champions.                                                    |
| GET    | `/api/synergies`           | Curated editorial synergy notes (not measured win rates).                                    |
