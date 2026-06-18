import Icon from './Icon'
import RarityBadge from './RarityBadge'
import { percent, number, isLowSample } from '../format'

// Renders a champion's measured augment winrates in backend order.
export default function AugmentWinrateTable({ augments }) {
  if (!augments || augments.length === 0) {
    return <p className="empty">No augment data recorded yet.</p>
  }

  return (
    <table className="stats-table">
      <thead>
        <tr>
          <th className="left">Augment</th>
          <th>Games</th>
          <th>Win Rate</th>
        </tr>
      </thead>
      <tbody>
        {augments.map((a) => (
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
