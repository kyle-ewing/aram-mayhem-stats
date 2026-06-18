import { useMemo, useState } from 'react'
import Icon from './Icon'
import { percent, number, isLowSample } from '../format'

export default function ChampionGrid({ champions, onSelect }) {
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return champions
    return champions.filter((c) => c.championName.toLowerCase().includes(q))
  }, [champions, query])

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
        <span className="muted">{filtered.length} of {champions.length}</span>
      </div>

      {filtered.length === 0 ? (
        <p className="empty">No champions match "{query}".</p>
      ) : (
        <ul className="champion-grid">
          {filtered.map((c) => (
            <li key={c.championId}>
              <button
                type="button"
                className="champion-card"
                onClick={() => onSelect(c)}
              >
                <Icon url={c.iconUrl} className="card-icon" />
                <span className="card-name">{c.championName}</span>
                <span className="card-stats">
                  <span
                    className={isLowSample(c.games) ? 'wr low' : 'wr'}
                    title={isLowSample(c.games) ? 'Low sample size' : undefined}
                  >
                    {percent(c.winRate)}
                  </span>
                  <span className="muted">{number(c.games)} games</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
