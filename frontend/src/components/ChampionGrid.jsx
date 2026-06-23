import { useMemo, useState } from 'react'
import Icon from './Icon'
import { percent, number, isLowSample } from '../format'

export default function ChampionGrid({ champions, onSelect }) {
  const [query, setQuery] = useState('')
  // Default sort is total games (desc), matching the backend's default ordering.
  const [sortBy, setSortBy] = useState('games')

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    const rows = q
      ? champions.filter((c) => c.championName.toLowerCase().includes(q))
      : [...champions]

    rows.sort((a, b) => {
      if (sortBy === 'name') {
        return a.championName.localeCompare(b.championName)
      }
      if (sortBy === 'winRate') {
        return b.winRate - a.winRate || b.games - a.games
      }
      // 'games': most games first, then win rate (mirrors the backend default).
      return b.games - a.games || b.winRate - a.winRate
    })
    return rows
  }, [champions, query, sortBy])

  // Cold start: no champions at all means no data has been ingested yet.
  if (!champions || champions.length === 0) {
    return (
      <div className="empty-state">
        <h2>No champion data yet</h2>
        <p>
          We have not collected any ARAM Mayhem games so far. Stats appear here
          once the community LCU collectors start feeding match results. Check
          back soon.
        </p>
      </div>
    )
  }

  return (
    <section className="champion-grid-section">
      <div className="grid-toolbar">
        <input
          type="text"
          className="search-input"
          placeholder="Search champions..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoComplete="off"
          aria-label="Search champions by name"
        />
        <label className="sort-control">
          Sort by
          <select
            className="sort-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            aria-label="Sort champions"
          >
            <option value="games">Total games</option>
            <option value="winRate">Win %</option>
            <option value="name">Name (A-Z)</option>
          </select>
        </label>
        <span className="muted">{visible.length} of {champions.length}</span>
      </div>

      {visible.length === 0 ? (
        <p className="empty">No champions match "{query}".</p>
      ) : (
        <ul className="champion-grid">
          {visible.map((c) => (
            <li key={c.championId}>
              <button
                type="button"
                className="champion-card"
                onClick={() => onSelect(c)}
              >
                <Icon url={c.iconUrl} className="card-icon" />
                <span className="card-body">
                  <span className="card-name" title={c.championName}>
                    {c.championName}
                  </span>
                  <span className="card-stats">
                    <span
                      className={isLowSample(c.games) ? 'wr low' : 'wr'}
                      title={isLowSample(c.games) ? 'Low sample size' : undefined}
                    >
                      {percent(c.winRate)}
                    </span>
                    <span className="muted">{number(c.games)} games</span>
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
