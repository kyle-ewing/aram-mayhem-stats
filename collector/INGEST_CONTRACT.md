# aram-mayhem-stats Ingest Payload Contract (Phase 0)

This document defines the contract between the LCU collector (a local desktop agent that
reads the player's running League client) and the Flask backend ingest endpoint. Both sides
implement against this document. The collector is built later; this contract gates that work.

Status: contract is implementation-ready. Items that can only be confirmed against a live
League client are flagged with LIVE-VERIFY.

Background: Riot's public match-v5 web API returns 403 for ARAM Mayhem matches on purpose
(dev-relations issue #1109, working as intended), so winrates cannot come from the web API.
Our data source is first-party end-of-game data read from the local League client via the
LCU (League Client Update) API, which can see full Mayhem data including augments and all 10
players. Reference implementation studied: Yhprum/mayhem-tracker (Electron, league-connect,
better-sqlite3).

## 1. LCU auth discovery

The League client exposes a local HTTPS REST API (the LCU API). Auth credentials are written
to a lockfile while the client is running.

- Lockfile location (Windows): `%LOCALAPPDATA%\Riot Games\Riot Client\Config\lockfile`.
  The legacy League-specific lockfile also appears in the League install directory
  (next to `LeagueClient.exe`). On macOS the path is under the app bundle
  (`/Applications/League of Legends.app/Contents/LoL/lockfile`). The collector should locate
  the running client rather than hardcode one path. Using `league-connect` (as the reference
  does) handles this discovery automatically. LIVE-VERIFY: exact path on the target OS.
- Lockfile format: a single line of colon-separated fields:
  `name:pid:port:password:protocol`
  Example: `LeagueClient:1234:54321:abcd1234efgh:https`.
  - `name`: process name.
  - `pid`: process id.
  - `port`: the TCP port the LCU API listens on (changes every client launch).
  - `password`: the auth password (changes every client launch).
  - `protocol`: always `https`.
- Request base URL: `https://127.0.0.1:{port}`.
- Authentication: HTTP Basic auth. Username is the constant string `riot`, password is the
  lockfile `password`. The header is `Authorization: Basic base64("riot:" + password)`.
- TLS: the LCU serves a self-signed certificate. The client must either trust Riot's root
  certificate (`riotgames.pem`, shipped with `league-connect` and other LCU libraries) or
  disable certificate verification for `127.0.0.1` only. Do not disable TLS verification for
  any non-local host.
- Lifecycle: port and password are only valid while the client runs and change on every
  restart. The collector must re-read the lockfile on reconnect. The reference polls for the
  client every 5 seconds until connected.

The collector reads the lockfile and talks to the LCU. It never needs the Riot web API key
for ingest. The web API key stays a backend concern (Data Dragon needs no key).

## 2. LCU endpoints for post-game Mayhem data

The reference uses match-history endpoints rather than a live end-of-game socket, polling
after games complete. The relevant endpoints:

- `GET /lol-summoner/v1/current-summoner`
  Returns the local player (`puuid`, `summonerId`, `gameName`, `tagLine`). Used to identify
  who is uploading and to drive the match-history lookups.
- `GET /lol-match-history/v1/products/lol/current-summoner/matches`
  Recent match list for the logged-in summoner. Also available by puuid:
  `GET /lol-match-history/v1/products/lol/{puuid}/matches`. Returns a paged list of game
  summaries; the collector filters these by `queueId` to find Mayhem games.
- `GET /lol-match-history/v1/games/{gameId}`
  Full per-game detail for a single game. THIS is the endpoint that carries the complete
  payload: all 10 participants, per-participant `stats` (including
  `totalDamageDealtToChampions` and the `playerAugment1..N` augment fields), and
  `participantIdentities` (puuid / names). This is the authoritative source for an ingest
  record.

Note on the live end-of-game endpoint: the LCU also exposes `/lol-end-of-game/v1/eog-stats-block`
and the `OnJsonApiEvent_lol-end-of-game_v1_eog-stats-block` WebSocket event, which fire on the
post-game screen. The reference does NOT rely on these; it polls match-history instead, which
is more robust (it still works if the player alt-tabs past the post-game screen, and it can
backfill recent games on first launch). The collector SHOULD follow the match-history polling
approach. The end-of-game block is an optional future enhancement for lower latency.

Recommended collector flow: poll `current-summoner/matches` (reference uses ~60s), keep games
where `queueId` matches Mayhem, and for each new `gameId` fetch
`/lol-match-history/v1/games/{gameId}`, transform to the canonical payload below, and POST it.

## 3. Shape of a Mayhem match from the LCU (`/lol-match-history/v1/games/{gameId}`)

This is the standard League match-history game object (same shape the old match-v4 used). Key
paths the collector reads:

Top level:
- `gameId` (number): stable unique id for the game.
- `queueId` (number): Mayhem queue id (see section 5).
- `gameVersion` (string): full client/patch build string, for example
  `"26.12.123.4567"`. Normalize to a major.minor patch string for storage (section 4).
- `gameMode` (string): expected `"ARAM"` (or a Mayhem-specific mode tag, LIVE-VERIFY).
- `gameCreation` (number, epoch ms) and `gameDuration` (number, seconds): optional, useful
  metadata.
- `participants` (array, length 10): per-player data.
- `participantIdentities` (array, length 10): maps `participantId` to `player` identity
  (`puuid`, `gameName`, `tagLine`, `summonerName`).

Per participant (`participants[i]`):
- `participantId` (number): 1..10, joins to `participantIdentities`.
- `championId` (number): champion played. championName is NOT in the payload; resolve it from
  Data Dragon by `championId` (the reference resolves names client-side via Data Dragon).
- `teamId` (number): 100 or 200.
- `spell1Id`, `spell2Id` (number): the two summoner spell ids, on the participant object (not
  inside `stats`). The collector copies them through as `summonerSpells: [spell1Id, spell2Id]`.
- `stats` (object), the flattened stat block:
  - `win` (bool): per-participant win flag (equivalently derivable from the team result).
  - `kills`, `deaths`, `assists` (number).
  - `totalDamageDealtToChampions` (number). The reference falls back to `totalDamageDealt`
    if the champions-specific field is absent; prefer `totalDamageDealtToChampions`.
  - `playerAugment1`, `playerAugment2`, `playerAugment3`, `playerAugment4` (number): augment
    ids. A value of `0` means "no augment in that slot". The reference reads slots 1..4 and
    keeps only positive ids.
  - `item0`, `item1`, `item2`, `item3`, `item4`, `item5` (number): end-of-game inventory item
    ids; `item6` (number) is the trinket. A value of `0` means an empty slot. The collector
    reads all 7 slots positionally and keeps zeros (slot position is the point).
  - `gameEndedInEarlySurrender` (bool): `true` when the game was a remake. Set on every
    participant. The collector folds it into the single top-level payload flag of the same
    name and does not upload remakes; the backend also refuses to store them.

Augments: in the LCU match payload augments appear as the discrete integer fields
`playerAugment1..4` inside `stats`, NOT as an array. The collector collapses them into an
array of positive ints. Augment static metadata (name, icon, rarity) comes from Community
Dragon / Data Dragon, not from the match payload. LIVE-VERIFY: patch 26.12 made Mayhem
permanent, removed traits, and added Ability/Quest augments with a rotated pool. Confirm the
post-26.12 client still uses exactly `playerAugment1..4` and that 4 slots is the max; if a
5th slot exists the collector must read `playerAugment1..N` generically and the contract's
augments array (already variable-length) absorbs it without change.

## 4. Canonical ingest payload (THE CONTRACT)

The collector POSTs this JSON to the backend ingest endpoint. The backend validates it,
normalizes it, and stores it idempotently keyed on `gameId`. A single game is uploaded
independently by up to 10 collectors (one per player), so ingest MUST be idempotent: the
backend dedups on `gameId` (for example INSERT OR IGNORE / upsert on a `gameId` primary key),
and repeat POSTs of the same `gameId` return success without creating duplicates.

### Request

`POST /api/ingest/match`
`Content-Type: application/json`

### Body schema

```json
{
  "schemaVersion": 1,
  "gameId": 1234567890,
  "queueId": 2400,
  "patch": "26.12",
  "gameVersion": "26.12.123.4567",
  "gameCreation": 1718700000000,
  "gameDuration": 1234,
  "participants": [
    {
      "participantId": 1,
      "championId": 64,
      "championName": "LeeSin",
      "teamId": 100,
      "win": true,
      "kills": 12,
      "deaths": 4,
      "assists": 8,
      "totalDamageDealtToChampions": 23456,
      "augments": [101, 207, 0, 0],
      "items": [3047, 6692, 3071, 3133, 1037, 0, 3340],
      "summonerSpells": [4, 32]
    }
  ]
}
```

Note: the example `participants` array is shown with one entry for brevity. A valid payload
contains exactly 10 entries.

### Field definitions

Top level:

| field          | type    | required | notes |
|----------------|---------|----------|-------|
| `schemaVersion`| int     | yes      | Contract version. Currently `1`. Lets the backend reject/migrate old collectors. |
| `gameId`       | int     | yes      | Stable unique game id from the LCU. The dedup key. Backend rejects duplicates idempotently. |
| `queueId`      | int     | yes      | Mayhem queue id (section 5). Backend MAY reject non-Mayhem queue ids. |
| `patch`        | string  | yes      | Normalized `"MAJOR.MINOR"` (for example `"26.12"`). See normalization below. |
| `gameVersion`  | string  | no       | Raw full build string from the LCU, kept for audit. |
| `gameCreation` | int     | no       | Epoch milliseconds. |
| `gameDuration` | int     | no       | Seconds. |
| `gameEndedInEarlySurrender` | bool | no | `true` if the game was a remake (Riot sets `gameEndedInEarlySurrender` on every participant). Collectors SHOULD omit it (or send `false`) for normal games. The backend NEVER stores a remake: it returns `200 {"status": "skipped"}` and writes nothing. |
| `participants` | array   | yes      | Exactly 10 participant objects. |

Per participant:

| field                          | type   | required | notes |
|--------------------------------|--------|----------|-------|
| `participantId`                | int    | yes      | 1..10. |
| `championId`                   | int    | yes      | From the LCU. The source of truth. |
| `championName`                 | string | yes      | Resolved by the collector from Data Dragon by `championId`. See normalization. |
| `teamId`                       | int    | yes      | 100 or 200. |
| `win`                          | bool   | yes      | Per-participant win. |
| `kills`                        | int    | yes      | >= 0. |
| `deaths`                       | int    | yes      | >= 0. |
| `assists`                      | int    | yes      | >= 0. |
| `totalDamageDealtToChampions`  | int    | yes      | >= 0. |
| `augments`                     | int[]  | yes      | Augment ids. Variable length. See normalization. |
| `items`                        | int[]  | no       | End-of-game inventory: `item0..item5` plus the `item6` trinket, 7 slots in order. `0` is an empty slot; zeros are kept (slot position matters). Collected for later use; nothing reads it yet. |
| `summonerSpells`               | int[]  | no       | The two summoner spell ids `[spell1Id, spell2Id]` from the participant object. Collected for later use; nothing reads it yet. |

### Normalization rules

- `patch`: derive from `gameVersion` by taking the first two dot-separated components, so
  `"26.12.123.4567"` becomes `"26.12"`. Store the major.minor form. Keep raw `gameVersion`
  if present. This keeps aggregation stable across hotfix builds within a patch.
- `championName`: resolved by the collector against a pinned Data Dragon version
  (`DDRAGON_VERSION` on the backend defines the canonical version for the project). The
  backend treats `championId` as authoritative; `championName` is a convenience/denormalized
  label. If the two ever disagree, `championId` wins.
- `augments`: the collector collapses the LCU `playerAugment1..N` fields into an array. Two
  acceptable conventions, pick ONE and keep it consistent:
  1. Filtered: include only positive ids, drop zeros (array length 0..N). Recommended,
     matches the reference behavior.
  2. Padded: keep all slots including `0` placeholders (fixed length).
  This contract RECOMMENDS convention 1 (filtered, positive ids only). The backend should
  accept any length 0..N and ignore zero values defensively regardless. Augment id-to-name
  resolution is a backend/service concern via Community Dragon, not part of this payload.
- Numeric fields are integers, not strings. `win` is a JSON boolean, not 0/1 or "Win".

### Responses

- `201 Created`: new match stored.
- `200 OK`: duplicate `gameId`, accepted idempotently, nothing changed; OR a remake
  (`gameEndedInEarlySurrender`) that was deliberately not stored (`status: "skipped"`). The
  collector treats 200 and 201 identically (success), so it stops re-sending the game.
- `400 Bad Request`: schema validation failed (missing required field, wrong type, wrong
  participant count, wrong/disallowed `queueId`). Body is a JSON `ApiError` per the project
  error contract. Never echoes any secret.
- `429 Too Many Requests`: backend rate limiting; collector backs off and retries.

The backend ingest endpoint validates this payload and maps failures to the project's
`ApiError` hierarchy (no Riot API key or internal detail in any error returned to the client).

## 5. Mayhem queueId

- ARAM Mayhem queue id observed in the reference implementation: `2400`. The reference filters
  `if (game.queueId !== 2400) continue;`. Treat `2400` as the confirmed-likely Mayhem queue
  id for the current (permanent, post-26.12) mode.
- Standard ARAM is `450`; that is NOT Mayhem and must not be ingested as Mayhem data.
- LIVE-VERIFY: confirm `2400` against a live client's
  `/lol-match-history/v1/games/{gameId}` for a real Mayhem game and against Riot's published
  queues list (queues.json on Data Dragon / static data). If Riot rotates the queue id for a
  new Mayhem event, make it configurable on the backend (`ARAM_QUEUE_ID` already exists in
  the project config) so both filtering and ingest validation share one source of truth.

## 6. Open items / uncertainty (for collector and backend authors)

1. queueId `2400` is taken from the reference, not yet from our own live capture. Make it
   configurable (`ARAM_QUEUE_ID`) on the backend and have the collector read the same value
   rather than hardcoding. LIVE-VERIFY before launch.
2. Augment slot count: reference reads `playerAugment1..4`. Patch 26.12 rotated the augment
   pool and added Ability/Quest augments. Confirm the slot count did not change. The contract's
   `augments` array is already variable-length, so a slot-count change needs only a collector
   tweak, not a contract change. LIVE-VERIFY.
3. `gameMode` value for Mayhem on the post-26.12 client is assumed `"ARAM"`; confirm whether a
   distinct mode/type tag exists. Not required by the contract (we key on `queueId`), but
   useful as a secondary sanity filter. LIVE-VERIFY.
4. End-of-game socket vs match-history polling: contract uses match-history (robust, supports
   backfill). The live `eog-stats-block` field names differ slightly from match-history; if a
   future collector reads it, it must map to this same canonical payload. LIVE-VERIFY field
   names if that path is taken.
5. Identity fields (`puuid`, `gameName`, `tagLine`) are available in
   `participantIdentities[].player` but are intentionally EXCLUDED from this v1 ingest payload
   to avoid storing personal data we do not need for aggregate winrate/synergy stats. If a
   later phase needs them, bump `schemaVersion`.
6. Trust model: any local collector can POST arbitrary data. v1 assumes cooperative clients.
   If abuse becomes a concern, add a shared ingest token or signature; that is out of scope
   for Phase 0 and would be a `schemaVersion`/header addition.
