import type { DataPoint } from '../../api/types'

const DAY_MS = 86_400_000

/** True when the series covers more than one year end to end. */
export function spansMoreThanAYear(points: DataPoint[]): boolean {
  if (points.length < 2) return false
  const first = Date.parse(points[0].date)
  const last = Date.parse(points[points.length - 1].date)
  return last - first > 366 * DAY_MS
}

export interface YearLine {
  year: number
  /** x is the date moved into the leap year 2000, so every year shares Jan-Dec. */
  points: { x: string; y: number }[]
}

/**
 * Split a series into calendar years, each re-dated into 2000 (a leap year,
 * so Feb 29 has a slot). Daily/weekly data lines up by day of year; monthly
 * buckets (YYYY-MM-01) line up by month. Oldest year first.
 */
export function buildYearLines(points: DataPoint[]): YearLine[] {
  const byYear = new Map<number, { x: string; y: number }[]>()
  for (const p of points) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(p.date)
    if (!m || !Number.isFinite(p.value)) continue
    const year = Number(m[1])
    const list = byYear.get(year) ?? []
    list.push({ x: `2000-${m[2]}-${m[3]}`, y: p.value })
    byYear.set(year, list)
  }
  return [...byYear.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([year, pts]) => ({ year, points: pts }))
}
