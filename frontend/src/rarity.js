// Augment rarity helpers. The backend uses numeric rarities for measured
// augments (0/1/2) and string rarities for curated synergies
// ("Silver"/"Gold"/"Prismatic"); normalize both to a label + css class.

const NUMERIC_LABELS = {
  0: 'Silver',
  1: 'Gold',
  2: 'Prismatic',
}

const CLASS_BY_LABEL = {
  Silver: 'rarity-silver',
  Gold: 'rarity-gold',
  Prismatic: 'rarity-prismatic',
}

export function rarityLabel(rarity) {
  if (rarity == null) return null
  if (typeof rarity === 'number') return NUMERIC_LABELS[rarity] ?? null
  const text = String(rarity).trim()
  if (!text) return null
  const normalized = text.charAt(0).toUpperCase() + text.slice(1).toLowerCase()
  return CLASS_BY_LABEL[normalized] ? normalized : text
}

export function rarityClass(rarity) {
  const label = rarityLabel(rarity)
  if (!label) return null
  return CLASS_BY_LABEL[label] ?? null
}
