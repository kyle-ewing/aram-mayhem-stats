import { useEffect, useMemo, useState } from 'react'
import { getChampion } from '../api'
import Icon from './Icon'
import AugmentWinrateTable from './AugmentWinrateTable'
import SynergyNotes from './SynergyNotes'
import { percent, number, isLowSample, LOW_SAMPLE_THRESHOLD } from '../format'

export default function ChampionDetail({
  championId,
  summary,
  synergies,
  onBack,
}) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    setDetail(null)

    getChampion(championId)
      .then((data) => {
        if (active) setDetail(data)
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

  // Join synergy notes by champion name (case-insensitive), since the synergy
  // feed carries a Data Dragon string id that does not match the numeric id.
  const name = (detail?.championName ?? summary?.championName ?? '').toLowerCase()
  const championSynergies = useMemo(() => {
    if (!name) return []
    return (synergies ?? []).filter(
      (s) => (s.champion ?? '').toLowerCase() === name,
    )
  }, [synergies, name])

  const display = detail ?? summary
  const hasMeasured = detail != null

  return (
    <div className="champion-detail">
      <button type="button" className="back-button" onClick={onBack}>
        Back to champions
      </button>

      {loading && <p className="status">Loading champion...</p>}

      {error && !loading && (
        <p className="status error" role="alert">
          {error}
        </p>
      )}

      {!loading && !error && !display && (
        <div className="empty-state inline">
          <p>
            No data for this champion yet. It has no collected ARAM Mayhem games
            and is not in the leaderboard. Measured win rates appear here once
            the community LCU collectors feed in match results.
          </p>
        </div>
      )}

      {!loading && !error && display && (
        <>
          <div className="detail-header">
            <Icon url={display.iconUrl} className="detail-icon" />
            <div>
              <h2>{display.championName}</h2>
              {hasMeasured ? (
                <div className="detail-meta">
                  <span
                    className={isLowSample(detail.games) ? 'wr low big' : 'wr big'}
                  >
                    {percent(detail.winRate)} win rate
                  </span>
                  <span className="muted">
                    {number(detail.games)} games
                    {isLowSample(detail.games) && ' (low confidence)'}
                  </span>
                </div>
              ) : (
                <p className="muted">No measured games yet</p>
              )}
            </div>
          </div>

          {hasMeasured ? (
            <section className="augment-section">
              <h3>Augment win rates</h3>
              <p className="muted">
                Measured from collected games. Win rates from fewer than{' '}
                {LOW_SAMPLE_THRESHOLD} games are flagged as low confidence.
              </p>
              <AugmentWinrateTable augments={detail.augments} />
            </section>
          ) : (
            <div className="empty-state inline">
              <p>
                We have not collected any ARAM Mayhem games for this champion
                yet. Measured win rates appear here once the community LCU
                collectors feed in match results. The community synergy notes
                below are still available.
              </p>
            </div>
          )}

          <SynergyNotes synergies={championSynergies} />
        </>
      )}
    </div>
  )
}
