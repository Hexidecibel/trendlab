/**
 * Readable numbers and dates, shared across the app.
 *
 *   formatCompact(44951259)   -> "45.0M"     (axis ticks, lists, badges)
 *   formatCompact(1234)       -> "1.2K"
 *   formatCompact(64123.4)    -> "64.1K"
 *   formatCompact(21.37)      -> "21.4"      (temperatures, small prices)
 *   formatCompact(0.3456)     -> "0.346"
 *   formatPrecise(44951259)   -> "44.95M"    (tooltips: one more digit)
 *   formatPrecise(64123.4)    -> "64,123"
 *   formatShortDate('2026-04-06') -> "Apr 6"
 */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function trimZeros(text: string): string {
  return text.includes('.') ? text.replace(/\.?0+$/, '') : text
}

function scaled(v: number, digits: number): string | null {
  const a = Math.abs(v)
  if (a >= 1e12) return `${(v / 1e12).toFixed(digits)}T`
  if (a >= 1e9) return `${(v / 1e9).toFixed(digits)}B`
  if (a >= 1e6) return `${(v / 1e6).toFixed(digits)}M`
  return null
}

/** Compact number for axes, lists and labels. */
export function formatCompact(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '–'
  const big = scaled(v, 1)
  if (big) return big
  const a = Math.abs(v)
  if (a >= 1e3) return `${(v / 1e3).toFixed(1)}K`
  if (a >= 100) return v.toFixed(0)
  if (a >= 10) return trimZeros(v.toFixed(1))
  if (a >= 1) return trimZeros(v.toFixed(2))
  if (a === 0) return '0'
  return trimZeros(v.toPrecision(3))
}

/** A little more precision than formatCompact, for tooltips. */
export function formatPrecise(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '–'
  const big = scaled(v, 2)
  if (big) return big
  const a = Math.abs(v)
  if (a >= 1e4) return v.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (a >= 100) return v.toLocaleString(undefined, { maximumFractionDigits: 1 })
  if (a >= 1) return v.toLocaleString(undefined, { maximumFractionDigits: 2 })
  if (a === 0) return '0'
  return trimZeros(v.toPrecision(3))
}

/** Signed percent: "+12%", "-3.4%". */
export function formatPct(pct: number | null | undefined): string {
  if (pct == null || !Number.isFinite(pct)) return '–'
  const digits = Math.abs(pct) >= 10 ? 0 : 1
  return `${pct >= 0 ? '+' : ''}${trimZeros(pct.toFixed(digits))}%`
}

function parseIsoDate(iso: string): { y: number; m: number; d: number } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return null
  return { y: Number(m[1]), m: Number(m[2]), d: Number(m[3]) }
}

/** "Apr 6", or "Apr 6, 2025" with `withYear`. Falls back to the input. */
export function formatShortDate(iso: string, withYear = false): string {
  const p = parseIsoDate(iso)
  if (!p) return iso
  const base = `${MONTHS[p.m - 1]} ${p.d}`
  return withYear ? `${base}, ${p.y}` : base
}

/** Chart.js tick callback that formats numeric ticks compactly. */
export function compactTick(value: number | string): string {
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? formatCompact(n) : String(value)
}
