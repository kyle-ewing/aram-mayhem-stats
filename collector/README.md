# aram-mayhem-stats LCU Collector

A small local desktop helper that reads ARAM Mayhem game results from the player's running
League of Legends client (via the LCU API) and uploads them to the aram-mayhem-stats backend.

## Why this exists

Riot's public match-v5 web API returns 403 for ARAM Mayhem matches on purpose (Riot
dev-relations issue #1109, working as intended), so Mayhem winrates and augment synergy data
cannot come from the web API. The data we need (all 10 participants, per-participant augments,
KDA, damage, win) is available from the player's own running client through the LCU (League
Client Update) local REST API. This collector reads that first-party end-of-game data and
forwards it, in the canonical ingest shape, to our backend.

Provenance: the authoritative endpoint is
`GET /lol-match-history/v1/games/{gameId}`, which carries the full per-game detail. The
collector polls the recent match list, filters to the Mayhem queue, and fetches that detail
for each new finished game.

The payload shape is defined by `INGEST_CONTRACT.md` in this directory (the source of truth).
This collector emits `schemaVersion: 1`.

## Prerequisites

- Node.js 20 or newer.
- The League of Legends client installed and running, and the player logged in. The collector
  reads the running client's lockfile for local auth; it does not need a Riot web API key.
- Player opt-in. This is a voluntary collector; it uploads the player's own finished Mayhem
  games to the project backend. Identity fields (puuid, names) are intentionally NOT included
  in the v1 payload.
- The aram-mayhem-stats backend reachable (default `http://127.0.0.1:5000`).

## Install and run

```bash
cd collector
npm install
npm start
```

The collector connects to the running client (polling until it appears), then loops: pull
recent games, keep new Mayhem games, map each to the ingest payload, and POST it.

## Configuration

All config is read in one place (`src/config.js`). CLI flags override environment variables,
which override defaults.

| Env var | CLI flag | Default | Meaning |
|---------|----------|---------|---------|
| `BACKEND_BASE_URL` | `--backend-base-url` | `http://127.0.0.1:5000` | Backend base URL. Ingest path is fixed at `/api/ingest/match`. |
| `POLL_INTERVAL_MS` | `--poll-interval-ms` | `60000` | Match-history poll interval. |
| `RECONNECT_INTERVAL_MS` | `--reconnect-interval-ms` | `5000` | Wait before reconnecting after a client/loop error. |
| `MAYHEM_QUEUE_ID` | `--mayhem-queue-id` | `2400` | Mayhem queue id used to filter games. Keep in sync with the backend's `ARAM_QUEUE_ID`. |
| `DDRAGON_VERSION` | `--ddragon-version` | latest | Pin a Data Dragon version for champion-name resolution. Empty means use latest. |
| `SEEN_FILE` | `--seen-file` | `seen.json` | Path to the dedup store file. |
| `MATCH_HISTORY_PAGE_SIZE` | `--match-history-page-size` | `20` | How many recent games to scan per poll. |

Example:

```bash
BACKEND_BASE_URL=http://127.0.0.1:5000 MAYHEM_QUEUE_ID=2400 npm start
# or
npm start -- --backend-base-url http://127.0.0.1:5000 --mayhem-queue-id 2400
```

## How dedup works

The backend dedups idempotently by `gameId` (re-uploading the same game is safe and returns
200). To avoid spamming re-uploads every poll, the collector keeps a local set of already
uploaded `gameId`s in a JSON file (`seen.json` by default), written atomically and loaded on
startup so it persists across restarts. A game is added to the seen set only after a
successful upload (HTTP 200 or 201), or after a non-retryable 400 rejection (no point
retrying a malformed game). Rate-limited (429) and network-failed uploads are left unmarked so
they retry on the next poll.

We chose a JSON file over SQLite: the only state needed is a small set of integer ids, a JSON
array is dependency-free (no native build step), and the volume is tiny. The reference
implementation uses SQLite because it also stores full game rows for a UI; this collector only
needs the seen-set.

## Champion name resolution

`championName` is resolved from `championId` using Data Dragon (`champion.json`, mapping the
numeric `key` to the canonical `id` name, for example `64` to `LeeSin`). The map is fetched
once at startup. Data Dragon needs no API key. If the fetch fails the resolver returns empty
names and the collector keeps running, since `championId` is authoritative per the contract.

## Architecture

```
src/
  config.js      env/CLI config (single source of truth)
  lcu.js         LCU discovery + fetch (the only file that imports league-connect)
  champions.js   championId -> name via Data Dragon
  map.js         LCU game -> canonical ingest payload (pure, no network deps)
  seen.js        JSON-file dedup store
  upload.js      POST + retry/back-off
  index.js       entrypoint: wires discovery, poll loop, mapping, dedup, upload
test/
  fixtures/mayhem-game.json   realistic 10-player Mayhem game
  map.test.js                 fixture-driven mapping assertions
  upload.test.js              200/201/429/400 handling
  config.test.js              default/env/CLI precedence
```

The LCU and HTTP concerns are isolated in `lcu.js` and `upload.js` so `map.js` is pure and
fully unit-testable from fixtures, with no dependency on `league-connect`.

## Tests

```bash
npm test
```

Uses the Node built-in test runner (`node --test`), no test framework dependency. The mapping
test feeds the bundled LCU fixture through `mapGameToIngestPayload` and asserts the output
equals the canonical ingest payload (augments collapsed to positive ids, patch normalized to
MAJOR.MINOR, all required fields present, exactly 10 participants). Tests never hit the live
API or a real client.

## Live verification (required on the user's machine)

This collector cannot be exercised against a real League client in the build sandbox (there is
no client there). The following must be verified live on a machine running the client during a
real Mayhem game, per the LIVE-VERIFY items in `INGEST_CONTRACT.md`:

- The Mayhem `queueId` is actually `2400` on the current (post-26.12) client. If Riot rotated
  it, set `MAYHEM_QUEUE_ID` to match (and keep the backend's `ARAM_QUEUE_ID` in sync).
- The augment fields are exactly `playerAugment1..4` and 4 slots is the max. If a 5th slot
  exists, raise `MAX_AUGMENT_SLOTS` in `src/map.js`; the variable-length `augments` array needs
  no contract change.
- The lockfile discovery (`league-connect`) finds the client on the target OS, and the
  match-history endpoint paths return the expected shape.
- `gameMode` value for Mayhem (assumed `"ARAM"`), used only as an optional secondary filter.
