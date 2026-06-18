// Small formatting helpers shared by the stats views.

export function percent(value) {
  if (value == null || Number.isNaN(value)) return '-'
  return `${(value * 100).toFixed(1)}%`
}

export function number(value) {
  if (value == null || Number.isNaN(value)) return '-'
  return Math.round(value).toLocaleString()
}

export function decimal(value, digits = 1) {
  if (value == null || Number.isNaN(value)) return '-'
  return value.toFixed(digits)
}

// Below this many games a winrate is treated as low confidence.
export const LOW_SAMPLE_THRESHOLD = 20

export function isLowSample(games) {
  return (games ?? 0) < LOW_SAMPLE_THRESHOLD
}
