// Collector entrypoint. Wires config, LCU discovery, polling, mapping, dedup, and upload.
// Designed to never crash on a disconnected client or a transient network error: failures
// are logged and retried on the next loop iteration.

import { loadConfig } from "./config.js";
import { LcuClient } from "./lcu.js";
import { buildChampionResolver } from "./champions.js";
import { SeenStore } from "./seen.js";
import { mapGameToIngestPayload } from "./map.js";
import { uploadMatch, UploadResult } from "./upload.js";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function processNewGames(ctx) {
  const { lcu, config, seen, resolveChampionName } = ctx;
  const pageSize = config.matchHistoryPageSize;

  console.log(
    `[collector] pulse: scanning match history ${ctx.begIndex}..${ctx.begIndex + pageSize - 1}`,
  );

  const summoner = await lcu.getCurrentSummoner();
  const recent = await lcu.getRecentGames(summoner?.puuid, pageSize, ctx.begIndex);

  const mayhemGames = recent.filter(
    (g) => Number(g?.queueId) === config.mayhemQueueId && !seen.has(g?.gameId),
  );

  let uploaded = 0;
  for (const summary of mayhemGames) {
    const gameId = summary.gameId;
    try {
      const detail = await lcu.getGameDetail(gameId);
      const payload = mapGameToIngestPayload(detail, resolveChampionName);

      if (payload.participants.length !== 10) {
        console.warn(`[collector] game ${gameId} has ${payload.participants.length} participants, skipping`);
        continue;
      }

      if (payload.gameEndedInEarlySurrender) {
        await seen.add(gameId);
        console.log(`[collector] game ${gameId} was a remake; not uploading`);
        continue;
      }

      const { result, status } = await uploadMatch(config, payload);
      if (result === UploadResult.SUCCESS) {
        await seen.add(gameId);
        uploaded += 1;
        console.log(`[collector] uploaded game ${gameId} (HTTP ${status})`);
      }
      else if (result === UploadResult.RATE_LIMITED) {
        console.warn(`[collector] rate limited on game ${gameId}; will retry next poll`);
      }
      else {
        console.warn(`[collector] backend rejected game ${gameId} (HTTP ${status}); not retrying`);
        await seen.add(gameId);
      }
    }
    catch (err) {
      console.warn(`[collector] failed to process game ${gameId} (${err.message}); will retry next poll`);
    }
  }

  console.log(
    `[collector] pulse done: grabbed ${uploaded} new game(s) ` +
      `(page returned ${recent.length}, ${mayhemGames.length} new mayhem)`,
  );

  // Advance the paging window so the next pulse grabs the next 100 older games.
  // A short page means we reached the end of retained history, so wrap back to
  // the most recent page to keep catching newly played games (seen-dedup makes
  // the re-scan cheap). Only advance after a fully processed page so a mid-page
  // failure does not skip games.
  if (recent.length < pageSize) {
    ctx.begIndex = 0;
  }
  else {
    ctx.begIndex += pageSize;
  }
}

async function main() {
  const config = loadConfig();
  console.log(
    `[collector] backend=${config.backendBaseUrl}${config.ingestPath} ` +
      `queueId=${config.mayhemQueueId} pollMs=${config.pollIntervalMs} ` +
      `pageSize=${config.matchHistoryPageSize}`,
  );

  const seen = await new SeenStore(config.seenFile).load();
  const resolveChampionName = await buildChampionResolver(config.ddragonVersion);
  const lcu = new LcuClient();
  // begIndex is the paging cursor into match history; it advances each pulse.
  const ctx = { lcu, config, seen, resolveChampionName, begIndex: 0 };

  // Connection plus poll loop. A dropped client resets credentials and reconnects.
  for (;;) {
    try {
      if (!lcu.isConnected()) {
        console.log("[collector] waiting for the League client...");
        await lcu.connect();
        console.log("[collector] connected to the League client");
      }
      await processNewGames(ctx);
    }
    catch (err) {
      console.warn(`[collector] loop error (${err.message}); reconnecting`);
      lcu.reset();
      await sleep(config.reconnectIntervalMs);
      continue;
    }
    await sleep(config.pollIntervalMs);
  }
}

main().catch((err) => {
  console.error(`[collector] fatal: ${err.message}`);
  process.exit(1);
});
