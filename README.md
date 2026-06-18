# aram-mayhem-stats

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

## ARAM Mayhem mode notes

ARAM Mayhem is a **permanent mode** as of patch **26.12**. That patch removed traits, added
Ability and Quest augments, and rotated the augment pool, so any augment ids cached from
before 26.12 are stale.

The curated **synergy notes** served at `/api/synergies` are editorial. They are
community/editorial commentary on champion plus augment combinations that play well
together, not measured win rates. Measured win rates always come from ingested match data
and carry sample sizes.

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

`RIOT_API_KEY` is not required for the core product. If you prefer to run the steps
yourself instead of the script, see `backend/dev.sh` for the exact commands.

On first run the database is empty, so champion and augment endpoints return empty lists and
the frontend shows a cold-start state. Data appears once collectors start ingesting games.

The static-data versions are configurable in `.env`: `CDRAGON_VERSION` (default `latest`)
pins the Community Dragon augment data, and `DDRAGON_VERSION` (default `14.10.1`) pins the
Data Dragon version used for champion icons.

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

## Dev container (sandboxed Claude Code)

The `.devcontainer/` directory defines an isolated Linux container for running
[Claude Code](https://code.claude.com/docs/en/devcontainer), including
`--dangerously-skip-permissions` (bypass) mode, without giving the agent access to your
host. Command execution and network egress happen inside the container; your repo is
bind-mounted so edits still land in your local working tree.

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (WSL2
backend) and the VS Code [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers).

1. Open the repo in VS Code, then **Ctrl+Shift+P, Dev Containers: Reopen in Container**.
   The first build installs the toolchain plus both stacks (`backend/.venv` +
   `npm install`) via `.devcontainer/post-create.sh`.
2. After the build, the firewall (`init-firewall.sh`) locks outbound traffic to an
   allowlist (Anthropic API, GitHub, npm, PyPI, Data Dragon, Community Dragon
   (raw.communitydragon.org), and the Riot API hosts) and prints
   `Firewall configuration complete`.
3. Open a terminal and sign in: `claude` (auth persists across rebuilds via a named volume).
   You run in normal prompted mode; the agent asks before each tool call.

Bypass (`--dangerously-skip-permissions`) mode is **disabled** in this container:
`.devcontainer/managed-settings.json` sets `permissions.disableBypassPermissionsMode` to
`disable`, delivered to `/etc/claude-code/managed-settings.json` at the top of the settings
hierarchy, so the flag is rejected even if passed. To re-enable it, remove that setting and
rebuild.

Inside the container the stack is Linux, so use the venv's POSIX paths
(`backend/.venv/bin/python run.py`), not `.venv\Scripts`. Ports **5000** (Flask) and
**5173** (Vite) are forwarded to your host. The LCU collector reads a local League client,
so it runs on your host machine (where League runs), not inside this container.

> The firewall pins each allowed domain's IPs at startup. If a CDN rotates IPs mid-session,
> re-run `sudo /usr/local/bin/init-firewall.sh` to refresh them.

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
