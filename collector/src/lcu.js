// LCU access layer. This is the ONLY module that imports league-connect, so the mapping and
// upload logic stay free of it and remain unit-testable. It handles discovery (lockfile via
// league-connect), basic auth, the self-signed TLS cert, and the three match-history reads
// the contract names.

// league-connect 5.x ships as CommonJS, so import the default and destructure.
import leagueConnect from "league-connect";

const { authenticate, request } = leagueConnect;

export class LcuClient {
  constructor() {
    this.credentials = null;
  }

  // Discover and authenticate against the running client. Resolves once connected.
  // awaitConnection polls internally until the client is up, so this does not crash when the
  // client is not running yet.
  async connect() {
    this.credentials = await authenticate({
      awaitConnection: true,
      pollInterval: 2500,
    });
    return this.credentials;
  }

  isConnected() {
    return this.credentials !== null;
  }

  // Drop stale credentials so the next connect() re-reads the lockfile (port and password
  // change on every client restart).
  reset() {
    this.credentials = null;
  }

  async #request(path) {
    const res = await request({ method: "GET", url: path }, this.credentials);
    if (!res.ok) {
      const err = new Error(`LCU ${path} returned ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return res.json();
  }

  // GET /lol-summoner/v1/current-summoner -> { puuid, gameName, tagLine, ... }
  async getCurrentSummoner() {
    return this.#request("/lol-summoner/v1/current-summoner");
  }

  // Recent match list for the logged-in summoner. Returns the game summaries array.
  async getRecentGames(puuid, pageSize = 20) {
    const end = Math.max(0, pageSize - 1);
    const base = puuid
      ? `/lol-match-history/v1/products/lol/${puuid}/matches`
      : "/lol-match-history/v1/products/lol/current-summoner/matches";
    const body = await this.#request(`${base}?begIndex=0&endIndex=${end}`);
    return body?.games?.games ?? [];
  }

  // GET /lol-match-history/v1/games/{gameId} -> authoritative full game object.
  async getGameDetail(gameId) {
    return this.#request(`/lol-match-history/v1/games/${gameId}`);
  }
}
