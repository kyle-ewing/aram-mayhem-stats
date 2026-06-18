// championId -> championName resolution via Data Dragon.
//
// Choice: fetch the champion map once from Data Dragon at startup (key field is the numeric
// "key" in champion.json, mapped to the "id" field which is the canonical PascalCase name,
// for example 64 -> "LeeSin"). Rationale: Data Dragon needs no API key, the file is small,
// and fetching once keeps the collector current with new champions without shipping a stale
// bundled map. championId stays authoritative in the contract, so championName is a
// convenience label; if the network is unavailable the resolver degrades to "" rather than
// crashing, and the backend still has championId.

// Resolve the latest Data Dragon version unless one is pinned in config.
async function resolveVersion(pinnedVersion) {
  if (pinnedVersion) {
    return pinnedVersion;
  }
  const res = await fetch("https://ddragon.leagueoflegends.com/api/versions.json");
  if (!res.ok) {
    throw new Error(`Data Dragon versions fetch failed: ${res.status}`);
  }
  const versions = await res.json();
  return versions[0];
}

// Build a championId(number) -> championName(string) lookup.
export async function buildChampionResolver(pinnedVersion = "") {
  const map = new Map();
  try {
    const version = await resolveVersion(pinnedVersion);
    const url = `https://ddragon.leagueoflegends.com/cdn/${version}/data/en_US/champion.json`;
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Data Dragon champion.json fetch failed: ${res.status}`);
    }
    const body = await res.json();
    for (const champ of Object.values(body.data ?? {})) {
      const numericKey = Number.parseInt(champ.key, 10);
      if (Number.isFinite(numericKey)) {
        map.set(numericKey, champ.id);
      }
    }
  }
  catch (err) {
    console.warn(
      `[champions] could not load Data Dragon names (${err.message}); ` +
        "falling back to empty names. championId remains authoritative.",
    );
  }
  return (championId) => map.get(Number(championId)) ?? "";
}
