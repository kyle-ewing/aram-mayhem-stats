# aram-mayhem-stats, Agent Guide

A web app that surfaces **ARAM Mayhem statistics** from *League of Legends*. It is
champion-centric: a champion grid leads to a champion detail page with that champion's ARAM
Mayhem win rate, per-augment win rates with sample sizes, and curated synergy notes.
Augments are first-class, since ARAM Mayhem is built around them.

Win rates come from our **own first-party data**, not the Riot web API. Riot's public
match-v5 API returns **403 Forbidden** for ARAM Mayhem matches, intentionally (Riot
dev-relations issue #1109, closed working-as-intended), so the old per-summoner Riot-ID flow
was removed. Instead an opt-in **LCU collector** reads each player's local League client (the
LCU API can see full Mayhem results, including augments), maps finished games to a canonical
payload, and POSTs them to the backend, which stores and aggregates them.

ARAM Mayhem is a permanent mode as of patch 26.12, which removed traits, added Ability/Quest
augments, and rotated the augment pool (so pre-26.12 cached augment ids are stale).

## Stack

- **Backend:** Flask (Python **3.11+**), app-factory pattern, blueprints, SQLite storage.
  HTTP via `requests` for keyless static data only.
- **Collector:** Node app (`league-connect`) reading the local LCU API.
- **Frontend:** React + Vite (JavaScript), champion-centric SPA.
- **Tests:** `pytest` (+ `responses` to mock any static-data HTTP) for the backend.

> The machine default `python` is 3.6.8 (EOL). Always target 3.11+; use a `.venv` created
> with `py -3.12`.

## Layout

```
backend/
  app/
    __init__.py        # create_app() factory, calls init_db
    config.py          # env-driven Config (all os.environ access lives here)
    errors.py          # ApiError hierarchy, JSON responses
    db.py              # sqlite connection + schema
    riot/              # KEYLESS static-data helpers only: augments.py + routing.py
    services/          # business logic, no Flask imports: ingest.py, stats.py, synergies.py
    api/               # blueprints / route handlers, thin, delegate to services
    data/
      synergies.json   # curated editorial synergy notes
  tests/
  run.py               # dev entrypoint
collector/             # Node LCU collector: reads local client, POSTs canonical payloads
  src/
  test/fixtures/
  INGEST_CONTRACT.md   # canonical ingest payload contract
  README.md
  package.json
frontend/
  src/                 # React components, api client
.claude/agents/        # project subagents (see below)
```

## Conventions

- **Secrets:** `RIOT_API_KEY` (in `backend/.env`, gitignored) is now optional and unused by
  the core product (static data is keyless). If a key is ever present, never hardcode it,
  log it, or include it in error messages returned to clients.
- **Data source:** match win rates come from the LCU collector ingest, not match-v5, because
  match-v5 returns 403 for Mayhem games (issue #1109, working-as-intended). The backend never
  fetches Mayhem results from the Riot web API.
- **Ingest:** the canonical payload contract lives in `collector/INGEST_CONTRACT.md`. Ingest
  must stay idempotent: dedup by `gameId`, since up to 10 collectors can upload the same game.
- **Config:** all environment reads go through `app/config.py`. Don't scatter `os.environ`.
- **Errors:** raise subclasses of `ApiError` (in `app/errors.py`); the app's error handler
  converts them to JSON with the right status code.
- **Layering:** routes (`api/`) stay thin and call into `services/`; `services/` contain no
  Flask request/response objects so they're unit-testable; `riot/` only does keyless
  static-data fetching plus routing helpers.
- **Static data:** champion icons from Data Dragon, augment names/icons from Community Dragon,
  both keyless. Pre-26.12 augment ids are stale; treat the post-26.12 pool as current.
- **Tests:** mock all outbound HTTP with `responses`; never hit live APIs in tests.
- **Frontend:** talk to the backend through `src/api.js`; the Vite dev server proxies
  `/api` to `http://127.0.0.1:5000`.
- **Style:** never use em dashes in code, comments, or docs; rewrite with commas,
  parentheses, or separate sentences. No inline comments (no trailing `# ...` or `// ...`
  after a line of code); put explanatory comments on their own line above the code, and
  only when they add something the code doesn't already say.
- **Braces:** continuation keywords go on their own line below the closing brace, never
  cuddled on the same line as `}`. This applies everywhere (all languages, all constructs):
  `else`, `else if`, `catch`, `finally`, `do`/`while`, etc. For example:

  ```
  if () {
  }
  else if () {
  }
  else {
  }

  try {
  }
  catch (e) {
  }
  finally {
  }
  ```

## Commands

```bash
# backend
cd backend && .venv\Scripts\activate && python run.py
cd backend && pytest

# collector
cd collector && npm install
cd collector && npm start
cd collector && npm test

# frontend
cd frontend && npm run dev
```

## Subagents (`.claude/agents/`)

Coordination:
- **orchestrator**, plans multi-step / cross-cutting tasks and delegates each piece to the
  right specialist below, sequencing dependencies and integrating results. Use this for
  anything spanning more than one specialist.

Build & maintenance:
- **riot-api**, Riot Games API specialist: endpoints, routing, queue IDs, Data Dragon,
  rate limits. Use when touching `backend/app/riot/` or debugging upstream calls.
- **flask-backend**, builds/maintains the Flask backend (blueprints, services, tests).
- **react-frontend**, builds/maintains the React + Vite frontend.
- **bug-fixer**, diagnoses and fixes defects across the stack; reproduces, root-causes,
  patches with a regression test.

Domain knowledge:
- **league-pro**, expert on champions, abilities, and ARAM Mayhem augment synergy; advises
  on which augments perform well/poorly on which champions and why.
- **news-aggregator**, scans Reddit and League forums/news sites for ARAM Mayhem news,
  patch changes, and community interactions.

When a task fits one of these, delegate to it.
