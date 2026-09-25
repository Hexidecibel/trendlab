/**
 * Lag formatting for correlation results. A lag is counted in steps of the
 * aligned series; the backend reports the step as `lag_step` ("day", "week",
 * "month", "quarter", "year", or e.g. "3 days" / "6 months").
 */

const SHORT: Record<string, string> = {
  day: 'd',
  days: 'd',
  week: 'w',
  weeks: 'w',
  month: 'mo',
  months: 'mo',
  quarter: 'q',
  quarters: 'q',
  year: 'y',
  years: 'y',
}

function parseStep(step: string | undefined): { mult: number; unit: string } {
  const m = (step || 'day').trim().match(/^(\d+)\s+(\w+)$/)
  if (m) return { mult: Number(m[1]), unit: m[2].replace(/s$/, '') }
  return { mult: 1, unit: (step || 'day').replace(/s$/, '') }
}

/** Compact tick label, e.g. "+3d", "-2w", "+1mo". */
export function formatLagShort(lag: number, step?: string): string {
  const { mult, unit } = parseStep(step)
  const sign = lag > 0 ? '+' : ''
  return `${sign}${lag * mult}${SHORT[unit] ?? unit}`
}

/** Long form without sign, e.g. "3 weeks", "1 month", "same time". */
export function formatLagLong(lag: number, step?: string): string {
  const { mult, unit } = parseStep(step)
  const n = Math.abs(lag * mult)
  if (n === 0) return 'no lag'
  return `${n} ${unit}${n === 1 ? '' : 's'}`
}

/** Axis title, e.g. "Lag (weeks)". */
export function lagAxisTitle(step?: string): string {
  const { mult, unit } = parseStep(step)
  return mult === 1 ? `Lag (${unit}s)` : `Lag (${unit}s, steps of ${mult})`
}
