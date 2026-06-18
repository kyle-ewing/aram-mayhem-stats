// Uploads a canonical ingest payload to the backend ingest endpoint.
//
// Success: HTTP 201 (newly stored) and 200 (backend already had this gameId) are both
// treated as success per the contract. 429 triggers a bounded back-off honoring Retry-After.
// Network errors throw so the caller can retry on the next poll without crashing the process.

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Result codes the caller can act on.
export const UploadResult = {
  SUCCESS: "success",
  RATE_LIMITED: "rate_limited",
  REJECTED: "rejected",
};

export async function uploadMatch(config, payload, options = {}) {
  const maxRetries = options.maxRetries ?? 3;
  const baseBackoffMs = options.baseBackoffMs ?? 1000;
  const fetchImpl = options.fetch ?? fetch;
  const url = `${config.backendBaseUrl}${config.ingestPath}`;

  for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
    const res = await fetchImpl(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.status === 200 || res.status === 201) {
      return { result: UploadResult.SUCCESS, status: res.status };
    }

    if (res.status === 429) {
      const retryAfter = Number.parseInt(res.headers.get("retry-after"), 10);
      const waitMs = Number.isFinite(retryAfter)
        ? retryAfter * 1000
        : baseBackoffMs * 2 ** attempt;
      if (attempt < maxRetries) {
        await sleep(waitMs);
        continue;
      }
      return { result: UploadResult.RATE_LIMITED, status: 429 };
    }

    // 400 and other client errors are not retryable: the payload will not improve.
    return { result: UploadResult.REJECTED, status: res.status };
  }

  return { result: UploadResult.RATE_LIMITED, status: 429 };
}
