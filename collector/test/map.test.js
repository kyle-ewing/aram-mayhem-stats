import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import {
  mapGameToIngestPayload,
  normalizePatch,
  collapseAugments,
  SCHEMA_VERSION,
} from "../src/map.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(
  readFileSync(path.join(here, "fixtures", "mayhem-game.json"), "utf8"),
);

// Minimal championId -> name map covering the fixture, mirroring Data Dragon "key" -> "id".
const NAMES = {
  64: "LeeSin",
  103: "Ahri",
  1: "Annie",
  412: "Thresh",
  81: "Ezreal",
  238: "Zed",
  99: "Lux",
  555: "Pyke",
  89: "Leona",
  360: "Samira",
};
const resolveName = (id) => NAMES[id] ?? "";

test("normalizePatch reduces a full build string to MAJOR.MINOR", () => {
  assert.equal(normalizePatch("26.12.123.4567"), "26.12");
  assert.equal(normalizePatch("14.1.1.1"), "14.1");
  assert.equal(normalizePatch(""), "");
});

test("collapseAugments keeps only positive ids and drops zeros", () => {
  assert.deepEqual(
    collapseAugments({ playerAugment1: 101, playerAugment2: 207, playerAugment3: 0, playerAugment4: 0 }),
    [101, 207],
  );
  assert.deepEqual(
    collapseAugments({ playerAugment1: 0, playerAugment2: 0, playerAugment3: 0, playerAugment4: 0 }),
    [],
  );
  assert.deepEqual(
    collapseAugments({ playerAugment1: 401, playerAugment2: 402, playerAugment3: 403, playerAugment4: 404 }),
    [401, 402, 403, 404],
  );
});

test("mapGameToIngestPayload produces the exact canonical ingest payload", () => {
  const payload = mapGameToIngestPayload(fixture, resolveName);

  const expected = {
    schemaVersion: SCHEMA_VERSION,
    gameId: 1234567890,
    queueId: 2400,
    patch: "26.12",
    gameVersion: "26.12.123.4567",
    gameCreation: 1718700000000,
    gameDuration: 1234,
    participants: [
      { participantId: 1, championId: 64, championName: "LeeSin", teamId: 100, win: true, kills: 12, deaths: 4, assists: 8, totalDamageDealtToChampions: 23456, augments: [101, 207] },
      { participantId: 2, championId: 103, championName: "Ahri", teamId: 100, win: true, kills: 7, deaths: 6, assists: 15, totalDamageDealtToChampions: 18900, augments: [110, 305] },
      { participantId: 3, championId: 1, championName: "Annie", teamId: 100, win: true, kills: 3, deaths: 9, assists: 21, totalDamageDealtToChampions: 14200, augments: [] },
      { participantId: 4, championId: 412, championName: "Thresh", teamId: 100, win: true, kills: 1, deaths: 7, assists: 24, totalDamageDealtToChampions: 6500, augments: [401, 402, 403, 404] },
      { participantId: 5, championId: 81, championName: "Ezreal", teamId: 100, win: true, kills: 18, deaths: 5, assists: 6, totalDamageDealtToChampions: 31200, augments: [501] },
      { participantId: 6, championId: 238, championName: "Zed", teamId: 200, win: false, kills: 9, deaths: 8, assists: 7, totalDamageDealtToChampions: 27800, augments: [601, 602] },
      { participantId: 7, championId: 99, championName: "Lux", teamId: 200, win: false, kills: 6, deaths: 10, assists: 11, totalDamageDealtToChampions: 22100, augments: [701] },
      { participantId: 8, championId: 555, championName: "Pyke", teamId: 200, win: false, kills: 4, deaths: 11, assists: 13, totalDamageDealtToChampions: 9800, augments: [801] },
      { participantId: 9, championId: 89, championName: "Leona", teamId: 200, win: false, kills: 2, deaths: 9, assists: 18, totalDamageDealtToChampions: 7400, augments: [] },
      { participantId: 10, championId: 360, championName: "Samira", teamId: 200, win: false, kills: 14, deaths: 7, assists: 5, totalDamageDealtToChampions: 29500, augments: [1001, 1002, 1003] },
    ],
  };

  assert.deepEqual(payload, expected);
});

test("mapped payload satisfies the contract invariants", () => {
  const payload = mapGameToIngestPayload(fixture, resolveName);

  assert.equal(payload.schemaVersion, 1);
  assert.equal(payload.participants.length, 10);
  assert.equal(typeof payload.gameId, "number");
  assert.equal(typeof payload.queueId, "number");
  assert.equal(typeof payload.patch, "string");

  for (const p of payload.participants) {
    for (const field of ["participantId", "championId", "teamId", "kills", "deaths", "assists", "totalDamageDealtToChampions"]) {
      assert.equal(typeof p[field], "number", `${field} should be a number`);
    }
    assert.equal(typeof p.championName, "string");
    assert.equal(typeof p.win, "boolean");
    assert.ok(Array.isArray(p.augments));
    assert.ok(p.augments.every((a) => Number.isInteger(a) && a > 0), "augments are positive ints");
  }
});

test("totalDamageDealtToChampions falls back to totalDamageDealt when absent", () => {
  const game = {
    gameId: 1,
    queueId: 2400,
    gameVersion: "26.12.1.1",
    participants: [
      { participantId: 1, championId: 64, teamId: 100, stats: { win: true, kills: 0, deaths: 0, assists: 0, totalDamageDealt: 5000 } },
    ],
  };
  const payload = mapGameToIngestPayload(game, resolveName);
  assert.equal(payload.participants[0].totalDamageDealtToChampions, 5000);
});
