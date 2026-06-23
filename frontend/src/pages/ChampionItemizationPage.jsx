import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getChampionItems } from '../api'
import Icon from '../components/Icon'
import { percent, number, isLowSample } from '../format'

// Columns the single-item table can be sorted by: [key, label, default dir].
const ITEM_COLUMNS = [
  ['itemName', 'Item', 'asc'],
  ['damageType', 'Damage type', 'asc'],
  ['games', 'Games', 'desc'],
  ['winRate', 'Win Rate', 'desc'],
]

// How a build bucket's stored key maps to its display label.
const BUILD_LABELS = {
  AD: 'AD',
  AP: 'AP',
  mixed: 'Mixed',
  other: 'Other',
}

function damageTypeLabel(damageType) {
  if (damageType === 'AD') return 'AD'
  if (damageType === 'AP') return 'AP'
  if (damageType === 'mixed') return 'Mixed'
  return 'Other'
}

// Champion itemization win rates: per legendary item built, plus the AD, AP,
// mixed, and other build buckets. Reads the numeric championId from the route
// and fetches on mount (and when the id changes).
export default function ChampionItemizationPage() {
  const { championId } = useParams()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)

  const [sortBy, setSortBy] = useState('games')
  const [sortDir, setSortDir] = useState('desc')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    setData(null)

    getChampionItems(championId)
      .then((result) => {
        if (active) setData(result)
      })
      .catch((err) => {
        if (active) setError(err.message || 'Something went wrong.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [championId])

  const visibleItems = useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1
    const rows = [...(data?.items ?? [])]
    rows.sort((a, b) => {
      if (sortBy === 'itemName') {
        return dir * a.itemName.localeCompare(b.itemName)
      }
      if (sortBy === 'damageType') {
        return dir * (a.damageType.localeCompare(b.damageType) || b.games - a.games)
      }
      if (sortBy === 'winRate') {
        return dir * (a.winRate - b.winRate || a.games - b.games)
      }
      // 'games', with win rate as the tiebreaker (mirrors the backend default).
      return dir * (a.games - b.games || a.winRate - b.winRate)
    })
    return rows
  }, [data, sortBy, sortDir])

  function toggleSort(col, defaultDir) {
    if (sortBy === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    }
    else {
      setSortBy(col)
      setSortDir(defaultDir)
    }
  }

  const builds = data?.builds ?? []
  const hasItemizationData =
    (data?.items?.length ?? 0) > 0 || builds.some((b) => b.games > 0)

  return (
    <div className="champion-detail">
      <button
        type="button"
        className="back-button"
        onClick={() => navigate(`/champions/${championId}`)}
      >
        Back to champion
      </button>

      {loading && <p className="status">Loading itemization stats...</p>}

      {error && !loading && (
        <p className="status error" role="alert">
          {error}
        </p>
      )}

      {!loading && !error && !data && (
        <div className="empty-state inline">
          <p>
            No data for this champion yet. It has no collected ARAM Mayhem games.
            Measured itemization win rates appear here once the community LCU
            collectors feed in match results.
          </p>
        </div>
      )}

      {!loading && !error && data && (
        <>
          <div className="detail-header">
            <Icon url={data.iconUrl} className="detail-icon" />
            <div>
              <h2>{data.championName} itemization</h2>
              <div className="detail-meta">
                <span
                  className={isLowSample(data.games) ? 'wr low big' : 'wr big'}
                >
                  {percent(data.winRate)} win rate
                </span>
                <span className="muted">
                  {number(data.games)} games
                  {isLowSample(data.games) && ' (low confidence)'}
                </span>
              </div>
            </div>
          </div>

          {!hasItemizationData ? (
            <div className="empty-state inline">
              <p>No itemization data recorded yet for this champion.</p>
            </div>
          ) : (
            <>
              <section className="augment-section">
                <h3>Single-item win rates</h3>
                <p className="muted">
                  Per legendary item actually built, measured from collected
                  games.
                </p>
                {visibleItems.length === 0 ? (
                  <p className="empty">No items recorded yet.</p>
                ) : (
                  <table className="stats-table">
                    <thead>
                      <tr>
                        {ITEM_COLUMNS.map(([col, label, defaultDir]) => (
                          <th
                            key={col}
                            className={
                              col === 'itemName' || col === 'damageType'
                                ? 'left'
                                : undefined
                            }
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
                                {sortBy === col
                                  ? sortDir === 'asc'
                                    ? '▲'
                                    : '▼'
                                  : ''}
                              </span>
                            </button>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {visibleItems.map((item) => (
                        <tr key={item.itemId}>
                          <td className="left augment-cell">
                            <Icon url={item.iconUrl} className="augment-icon" />
                            <span className="augment-name">{item.itemName}</span>
                          </td>
                          <td className="left">
                            <span
                              className={`damage-badge damage-${item.damageType}`}
                            >
                              {damageTypeLabel(item.damageType)}
                            </span>
                          </td>
                          <td>{number(item.games)}</td>
                          <td>
                            <span
                              className={isLowSample(item.games) ? 'wr low' : 'wr'}
                              title={
                                isLowSample(item.games)
                                  ? 'Low sample size'
                                  : undefined
                              }
                            >
                              {percent(item.winRate)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>

              <section className="augment-section">
                <h3>Build win rates by damage profile</h3>
                <p className="muted">
                  Win rate by the overall damage profile of the build.
                </p>
                <table className="stats-table">
                  <thead>
                    <tr>
                      <th className="left">Build</th>
                      <th>Games</th>
                      <th>Win Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {builds.map((b) => (
                      <tr key={b.build}>
                        <td className="left">{BUILD_LABELS[b.build] ?? b.build}</td>
                        <td>{number(b.games)}</td>
                        <td>
                          <span
                            className={isLowSample(b.games) ? 'wr low' : 'wr'}
                            title={
                              isLowSample(b.games) ? 'Low sample size' : undefined
                            }
                          >
                            {percent(b.winRate)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            </>
          )}
        </>
      )}
    </div>
  )
}
