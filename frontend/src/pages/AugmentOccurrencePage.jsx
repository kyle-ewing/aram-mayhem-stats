import { useEffect, useMemo, useState } from 'react'
import { getAugments, getStats } from '../api'
import Icon from '../components/Icon'
import RarityBadge from '../components/RarityBadge'
import { number, decimal } from '../format'

const TIERS = ['Silver', 'Gold', 'Prismatic']

// Every ingested game has exactly 10 participants (enforced by ingest), so the
// player count is games * 10.
const PLAYERS_PER_GAME = 10

// Columns the augment list can be sorted by: [key, label, default direction].
const COLUMNS = [
  ['augmentName', 'Augment', 'asc'],
  ['games', 'Occurrences', 'desc'],
]

// "Total augment occurrence": how many times each augment has been seen across
// every ingested game. The per-augment `games` field from /api/augments is the
// occurrence count (one row per pick), and /api/stats gives the game total.
export default function AugmentOccurrencePage() {
  const [augments, setAugments] = useState([])
  const [totalGames, setTotalGames] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [sortBy, setSortBy] = useState('games')
  const [sortDir, setSortDir] = useState('desc')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    Promise.all([getAugments(), getStats()])
      .then(([augs, stats]) => {
        if (!active) return
        setAugments(augs ?? [])
        setTotalGames(stats?.totalGames ?? 0)
      })
      .catch((err) => {
        if (active) setError(err.message || 'Could not load augment data.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  // Per-rarity occurrence totals plus the overall pick count.
  const summary = useMemo(() => {
    const byTier = { Silver: 0, Gold: 0, Prismatic: 0 }
    let total = 0
    for (const a of augments) {
      total += a.games
      if (a.rarity in byTier) byTier[a.rarity] += a.games
    }
    return { byTier, total }
  }, [augments])

  const visible = useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1
    const rows = [...augments]
    rows.sort((a, b) => {
      if (sortBy === 'augmentName') {
        return dir * a.augmentName.localeCompare(b.augmentName)
      }
      // 'games' (occurrences), with name as a stable tiebreaker.
      return dir * (a.games - b.games || a.augmentName.localeCompare(b.augmentName))
    })
    return rows
  }, [augments, sortBy, sortDir])

  function toggleSort(col, defaultDir) {
    if (sortBy === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    }
    else {
      setSortBy(col)
      setSortDir(defaultDir)
    }
  }

  const players = totalGames * PLAYERS_PER_GAME
  const avg = (count) => (players ? decimal(count / players) : '-')

  return (
    <section className="augment-occurrence">
      <h2>Augment occurrences</h2>
      <p className="subtitle">
        How often each augment has been seen across all ingested ARAM Mayhem
        games.
      </p>

      {loading && <p className="status">Loading augment data...</p>}
      {error && !loading && (
        <p className="status error" role="alert">
          {error}
        </p>
      )}

      {!loading && !error && augments.length === 0 && (
        <p className="empty">No augment data recorded yet.</p>
      )}

      {!loading && !error && augments.length > 0 && (
        <>
          <table className="stats-table summary-table">
            <thead>
              <tr>
                <th className="left">Rarity</th>
                <th>Total seen</th>
                <th>Avg / player</th>
              </tr>
            </thead>
            <tbody>
              {TIERS.map((t) => (
                <tr key={t}>
                  <td className="left">
                    <RarityBadge rarity={t} />
                  </td>
                  <td>{number(summary.byTier[t])}</td>
                  <td>{avg(summary.byTier[t])}</td>
                </tr>
              ))}
              <tr className="summary-total">
                <td className="left">All</td>
                <td>{number(summary.total)}</td>
                <td>{avg(summary.total)}</td>
              </tr>
            </tbody>
          </table>

          <h3>All augments ({visible.length})</h3>
          <table className="stats-table">
            <thead>
              <tr>
                {COLUMNS.map(([col, label, defaultDir]) => (
                  <th
                    key={col}
                    className={col === 'augmentName' ? 'left' : undefined}
                    aria-sort={
                      sortBy === col
                        ? sortDir === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                    }
                  >
                    <button
                      type="button"
                      className={`th-sort${sortBy === col ? ' active' : ''}`}
                      onClick={() => toggleSort(col, defaultDir)}
                    >
                      {label}
                      <span className="sort-arrow" aria-hidden="true">
                        {sortBy === col ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                      </span>
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((a) => (
                <tr key={a.augmentId}>
                  <td className="left augment-cell">
                    <Icon url={a.iconUrl} className="augment-icon" />
                    <span className="augment-name">{a.augmentName}</span>
                    <RarityBadge rarity={a.rarity} />
                  </td>
                  <td>{number(a.games)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}
