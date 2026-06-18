import { rarityLabel, rarityClass } from '../rarity'

export default function RarityBadge({ rarity }) {
  const label = rarityLabel(rarity)
  if (!label) return null
  const cls = rarityClass(rarity)
  return <span className={`rarity-badge ${cls ?? ''}`}>{label}</span>
}
