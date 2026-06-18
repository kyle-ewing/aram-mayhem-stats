// Single source of truth for collector configuration.
// All environment and CLI argument reads happen here. Nothing else touches process.env.

const DEFAULTS = {
  backendBaseUrl: "http://127.0.0.1:5000",
  pollIntervalMs: 60000,
  reconnectIntervalMs: 5000,
  mayhemQueueId: 2400,
  ddragonVersion: "",
  seenFile: "seen.json",
  matchHistoryPageSize: 20,
};

function parseIntOr(value, fallback) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

// Minimal --key=value / --key value CLI parser. CLI overrides env, env overrides defaults.
function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      continue;
    }
    const body = token.slice(2);
    const eq = body.indexOf("=");
    if (eq !== -1) {
      out[body.slice(0, eq)] = body.slice(eq + 1);
    }
    else {
      const next = argv[i + 1];
      if (next !== undefined && !next.startsWith("--")) {
        out[body] = next;
        i += 1;
      }
      else {
        out[body] = "true";
      }
    }
  }
  return out;
}

export function loadConfig(env = process.env, argv = process.argv.slice(2)) {
  const cli = parseArgs(argv);

  const pick = (cliKey, envKey) => {
    if (cli[cliKey] !== undefined) {
      return cli[cliKey];
    }
    return env[envKey];
  };

  const backendBaseUrl =
    pick("backend-base-url", "BACKEND_BASE_URL") || DEFAULTS.backendBaseUrl;

  return {
    backendBaseUrl: backendBaseUrl.replace(/\/+$/, ""),
    ingestPath: "/api/ingest/match",
    pollIntervalMs: parseIntOr(
      pick("poll-interval-ms", "POLL_INTERVAL_MS"),
      DEFAULTS.pollIntervalMs,
    ),
    reconnectIntervalMs: parseIntOr(
      pick("reconnect-interval-ms", "RECONNECT_INTERVAL_MS"),
      DEFAULTS.reconnectIntervalMs,
    ),
    mayhemQueueId: parseIntOr(
      pick("mayhem-queue-id", "MAYHEM_QUEUE_ID"),
      DEFAULTS.mayhemQueueId,
    ),
    ddragonVersion: pick("ddragon-version", "DDRAGON_VERSION") || DEFAULTS.ddragonVersion,
    seenFile: pick("seen-file", "SEEN_FILE") || DEFAULTS.seenFile,
    matchHistoryPageSize: parseIntOr(
      pick("match-history-page-size", "MATCH_HISTORY_PAGE_SIZE"),
      DEFAULTS.matchHistoryPageSize,
    ),
  };
}

export { DEFAULTS };
