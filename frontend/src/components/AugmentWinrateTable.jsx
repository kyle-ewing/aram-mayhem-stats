import { useMemo, useState } from 'react'
import Icon from './Icon'
import RarityBadge from './RarityBadge'
import { percent, number, isLowSample } from '../format'

// Columns the table can be sorted by: [key, label, default direction].
const COLUMNS = [
  ['augmentName', 'Augment', 'asc'],
  ['games', 'Games', 'desc'],
  ['winRate', 'Win Rate', 'desc'],
]

// Renders a champion's measured augment winrates, sortable by clicking a header.
export default function AugmentWinrateTable({ augments }) {
  // Default to most games (desc), matching the order the backend sends.
  const [sortBy, setSortBy] = useState('games')
  const [sortDir, setSortDir] = useState('desc')

  const visible = useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1
    const rows = [...(augments ?? [])]
    rows.sort((a, b) => {
      if (sortBy === 'augmentName') {
        return dir * a.augmentName.localeCompare(b.augmentName)
      }
      if (sortBy === 'winRate') {
        return dir * (a.winRate - b.winRate || a.games - b.games)
      }
      // 'games', with win rate as the tiebreaker (mirrors the backend default).
      return dir * (a.games - b.games || a.winRate - b.winRate)
    })
    return rows
  }, [augments, sortBy, sortDir])

  // Click a header to sort by it (sensible default direction); click the active
  // one again to flip direction.
  function toggleSort(col, defaultDir) {
    if (sortBy === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    }
    else {
      setSortBy(col)
      setSortDir(defaultDir)
    }
  }

  if (!augments || augments.length === 0) {
    return <p className="empty">No augment data recorded yet.</p>
  }

  return (
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
            <td>
              <span
                className={isLowSample(a.games) ? 'wr low' : 'wr'}
                title={isLowSample(a.games) ? 'Low sample size' : undefined}
              >
                {percent(a.winRate)}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
