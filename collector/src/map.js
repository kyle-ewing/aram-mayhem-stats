// Pure mapping from an LCU match-history game object to the canonical ingest payload.
// This module has NO dependency on league-connect or any network library so it is fully
// unit-testable from fixtures. The contract lives in INGEST_CONTRACT.md and is authoritative.

export const SCHEMA_VERSION = 1;

// Maximum augment slot index read from the LCU stats block (playerAugment1..N).
// The contract notes the array is variable length, so raising this is forward compatible.
const MAX_AUGMENT_SLOTS = 4;

// Normalize a full LCU gameVersion build string to "MAJOR.MINOR".
// "26.12.123.4567" -> "26.12". Falls back to the raw value if it has fewer than two parts.
export function normalizePatch(gameVersion) {
  if (typeof gameVersion !== "string" || gameVersion.length === 0) {
    return "";
  }
  const parts = gameVersion.split(".");
  if (parts.length < 2) {
    return gameVersion;
  }
  return `${parts[0]}.${parts[1]}`;
}

// Collapse playerAugment1..N from a stats block into an array of positive ids.
// Convention 1 from the contract: keep only positive ids, drop zeros.
export function collapseAugments(stats, maxSlots = MAX_AUGMENT_SLOTS) {
  const augments = [];
  for (let slot = 1; slot <= maxSlots; slot += 1) {
    const raw = stats?.[`playerAugment${slot}`];
    const id = Number.parseInt(raw, 10);
    if (Number.isFinite(id) && id > 0) {
      augments.push(id);
    }
  }
  return augments;
}

function toInt(value, fallback = 0) {
  const n = Number.parseInt(value, 10);
  return Number.isFinite(n) ? n : fallback;
}

function damageDealtToChampions(stats) {
  // Prefer the champions-specific field; fall back to totalDamageDealt per the contract note.
  if (stats?.totalDamageDealtToChampions !== undefined) {
    return toInt(stats.totalDamageDealtToChampions);
  }
  return toInt(stats?.totalDamageDealt);
}

function mapParticipant(participant, resolveChampionName) {
  const stats = participant?.stats ?? {};
  const championId = toInt(participant?.championId);
  return {
    participantId: toInt(participant?.participantId),
    championId,
    championName: resolveChampionName(championId),
    teamId: toInt(participant?.teamId),
    win: Boolean(stats.win),
    kills: toInt(stats.kills),
    deaths: toInt(stats.deaths),
    assists: toInt(stats.assists),
    totalDamageDealtToChampions: damageDealtToChampions(stats),
    augments: collapseAugments(stats),
  };
}

// Map a full LCU game object to the canonical ingest payload.
// resolveChampionName: (championId:number) => string. The collector injects a Data Dragon
// backed resolver; tests inject a fixture map. championId stays authoritative per the contract.
export function mapGameToIngestPayload(game, resolveChampionName = () => "") {
  if (!game || typeof game !== "object") {
    throw new Error("mapGameToIngestPayload: game must be an object");
  }
  const participants = Array.isArray(game.participants) ? game.participants : [];
  const payload = {
    schemaVersion: SCHEMA_VERSION,
    gameId: toInt(game.gameId),
    queueId: toInt(game.queueId),
    patch: normalizePatch(game.gameVersion),
    participants: participants.map((p) => mapParticipant(p, resolveChampionName)),
  };
  if (typeof game.gameVersion === "string" && game.gameVersion.length > 0) {
    payload.gameVersion = game.gameVersion;
  }
  if (game.gameCreation !== undefined) {
    payload.gameCreation = toInt(game.gameCreation);
  }
  if (game.gameDuration !== undefined) {
    payload.gameDuration = toInt(game.gameDuration);
  }
  return payload;
}
