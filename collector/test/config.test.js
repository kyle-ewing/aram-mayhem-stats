import test from "node:test";
import assert from "node:assert/strict";
import { loadConfig, DEFAULTS } from "../src/config.js";

test("defaults apply when nothing is set", () => {
  const cfg = loadConfig({}, []);
  assert.equal(cfg.backendBaseUrl, DEFAULTS.backendBaseUrl);
  assert.equal(cfg.mayhemQueueId, 2400);
  assert.equal(cfg.pollIntervalMs, 150000);
  assert.equal(cfg.matchHistoryPageSize, 100);
  assert.equal(cfg.ingestPath, "/api/ingest/match");
});

test("env overrides defaults", () => {
  const cfg = loadConfig(
    { BACKEND_BASE_URL: "http://example.test:8080/", MAYHEM_QUEUE_ID: "450", POLL_INTERVAL_MS: "5000" },
    [],
  );
  assert.equal(cfg.backendBaseUrl, "http://example.test:8080");
  assert.equal(cfg.mayhemQueueId, 450);
  assert.equal(cfg.pollIntervalMs, 5000);
});

test("CLI overrides env", () => {
  const cfg = loadConfig(
    { MAYHEM_QUEUE_ID: "450" },
    ["--mayhem-queue-id=2400", "--backend-base-url", "http://127.0.0.1:9000"],
  );
  assert.equal(cfg.mayhemQueueId, 2400);
  assert.equal(cfg.backendBaseUrl, "http://127.0.0.1:9000");
});
