import test from "node:test";
import assert from "node:assert/strict";
import { uploadMatch, UploadResult } from "../src/upload.js";

const config = { backendBaseUrl: "http://127.0.0.1:5000", ingestPath: "/api/ingest/match" };

function fakeResponse(status, headers = {}) {
  return {
    status,
    headers: { get: (k) => headers[k.toLowerCase()] ?? null },
  };
}

test("201 is treated as success", async () => {
  const fetchImpl = async () => fakeResponse(201);
  const { result, status } = await uploadMatch(config, {}, { fetch: fetchImpl });
  assert.equal(result, UploadResult.SUCCESS);
  assert.equal(status, 201);
});

test("200 (duplicate) is treated as success", async () => {
  const fetchImpl = async () => fakeResponse(200);
  const { result } = await uploadMatch(config, {}, { fetch: fetchImpl });
  assert.equal(result, UploadResult.SUCCESS);
});

test("429 retries then reports rate limited", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return fakeResponse(429, { "retry-after": "0" });
  };
  const { result } = await uploadMatch(config, {}, { fetch: fetchImpl, maxRetries: 2, baseBackoffMs: 1 });
  assert.equal(result, UploadResult.RATE_LIMITED);
  assert.equal(calls, 3);
});

test("429 then 201 succeeds after backoff", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return calls === 1 ? fakeResponse(429, { "retry-after": "0" }) : fakeResponse(201);
  };
  const { result } = await uploadMatch(config, {}, { fetch: fetchImpl, maxRetries: 2, baseBackoffMs: 1 });
  assert.equal(result, UploadResult.SUCCESS);
});

test("400 is rejected and not retried", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return fakeResponse(400);
  };
  const { result, status } = await uploadMatch(config, {}, { fetch: fetchImpl });
  assert.equal(result, UploadResult.REJECTED);
  assert.equal(status, 400);
  assert.equal(calls, 1);
});
