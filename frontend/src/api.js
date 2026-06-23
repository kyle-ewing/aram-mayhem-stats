// The ONLY module that talks to the backend.
// The Vite dev server proxies /api -> http://127.0.0.1:5000, so we use
// relative /api/... paths (works in dev and prod).

// Shared request helper: performs the fetch, turns network failures into a
// friendly message, and parses a backend {error} body out of non-ok responses.
async function request(path, options) {
  let res
  try {
    res = await fetch(path, options)
  }
  catch {
    throw new Error('Network error: could not reach the server.')
  }

  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body && body.error) message = body.error
    }
    catch {
      // body wasn't JSON; keep the generic message
    }
    const err = new Error(message)
    err.status = res.status
    throw err
  }

  return res.json()
}

/**
 * Lightweight backend health check.
 * @returns {Promise<{status: string}>} e.g. {status: "ok"}
 */
export async function getHealth() {
  return request('/api/health')
}

/**
 * Fetch aggregate stats about the dataset.
 * @returns {Promise<{totalGames: number}>} count of ingested matches (games parsed)
 */
export async function getStats() {
  return request('/api/stats')
}

/**
 * Fetch the champion leaderboard (sorted games desc, then winRate desc).
 * May be an EMPTY array at cold start before collectors feed data.
 *
 * @returns {Promise<Array<{
 *   championId: number,
 *   championName: string,
 *   iconUrl: string,
 *   games: number,
 *   wins: number,
 *   winRate: number
 * }>>}
 */
export async function getChampions() {
  return request('/api/champions')
}

/**
 * Fetch one champion's detail, including its augment winrate breakdown.
 * Returns null when the backend has NO ingested games for the champion
 * (HTTP 404), so callers can show a graceful "no data yet" state instead
 * of a hard error.
 *
 * @param {number|string} championId - numeric Riot champion id
 * @returns {Promise<null | {
 *   championId: number,
 *   championName: string,
 *   iconUrl: string,
 *   games: number,
 *   wins: number,
 *   winRate: number,
 *   augments: Array<{
 *     augmentId: number,
 *     augmentName: string,
 *     iconUrl: string|null,
 *     rarity: number|string|null,
 *     games: number,
 *     wins: number,
 *     winRate: number
 *   }>
 * }>}
 */
export async function getChampion(championId) {
  try {
    return await request(`/api/champions/${encodeURIComponent(championId)}`)
  }
  catch (err) {
    if (err.status === 404) return null
    throw err
  }
}

/**
 * Fetch one champion's itemization win rates: per legendary item built, plus
 * the AD, AP, mixed, and other build buckets. Returns null when the backend has NO
 * ingested games for the champion (HTTP 404), so callers can show a graceful
 * "no data yet" state instead of a hard error.
 *
 * The `items` array arrives sorted by games desc, then winRate desc. The
 * `builds` array is ALWAYS exactly four entries in this order: AD, AP, mixed, other.
 *
 * @param {number|string} championId - numeric Riot champion id
 * @returns {Promise<null | {
 *   championId: number,
 *   championName: string,
 *   iconUrl: string|null,
 *   games: number,
 *   wins: number,
 *   winRate: number,
 *   items: Array<{
 *     itemId: number,
 *     itemName: string,
 *     iconUrl: string|null,
 *     damageType: "AD"|"AP"|"other",
 *     games: number,
 *     wins: number,
 *     winRate: number
 *   }>,
 *   builds: Array<{
 *     build: "AD"|"AP"|"other",
 *     games: number,
 *     wins: number,
 *     winRate: number
 *   }>
 * }>}
 */
export async function getChampionItems(championId) {
  try {
    return await request(`/api/champions/${encodeURIComponent(championId)}/items`)
  }
  catch (err) {
    if (err.status === 404) return null
    throw err
  }
}

/**
 * Fetch the augment leaderboard across all champions.
 * May be an EMPTY array at cold start.
 *
 * @returns {Promise<Array<{
 *   augmentId: number,
 *   augmentName: string,
 *   iconUrl: string|null,
 *   rarity: number|string|null,
 *   games: number,
 *   wins: number,
 *   winRate: number
 * }>>}
 */
export async function getAugments() {
  return request('/api/augments')
}

/**
 * Fetch curated EDITORIAL synergy notes (not measured winrates).
 * May be non-empty even when winrates are empty.
 * Note: entries carry a Data Dragon STRING championId (e.g. "LeeSin"),
 * which differs from the numeric championId used by /api/champions.
 * Join to a champion by championName (case-insensitive) instead.
 *
 * @returns {Promise<Array<{
 *   champion: string,
 *   championId: string,
 *   augment: string,
 *   rarity: "Silver"|"Gold"|"Prismatic",
 *   note: string,
 *   source: string
 * }>>}
 */
export async function getSynergies() {
  return request('/api/synergies')
}

/**
 * Fetch the curated ARAM Mayhem augment pool (hand-maintained reference).
 *
 * @returns {Promise<Array<{
 *   name: string,
 *   tier: "Silver"|"Gold"|"Prismatic",
 *   id: number|null,
 *   notes: string
 * }>>}
 */
export async function getMayhemAugments() {
  return request('/api/mayhem-augments')
}

/**
 * Append one augment to the curated Mayhem pool.
 * Throws an Error (with the backend message) on validation failure or a
 * duplicate name.
 *
 * @param {{name: string, tier: string, id?: number|null, notes?: string}} entry
 * @returns {Promise<{name: string, tier: string, id: number|null, notes: string}>}
 */
export async function addMayhemAugment(entry) {
  return request('/api/mayhem-augments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entry),
  })
}

/**
 * Update an existing augment, identified by its current name. Supports
 * renaming. Throws an Error (with the backend message) on validation failure,
 * a name collision, or if no augment with that name exists.
 *
 * @param {string} name - the augment's CURRENT name
 * @param {{name: string, tier: string, id?: number|null, notes?: string}} entry
 * @returns {Promise<{name: string, tier: string, id: number|null, notes: string}>}
 */
export async function updateMayhemAugment(name, entry) {
  return request(`/api/mayhem-augments/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entry),
  })
}
