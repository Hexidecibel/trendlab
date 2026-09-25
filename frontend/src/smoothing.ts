// Smoothing presets for the trend charts: defaults per source and the
// user's remembered choice (localStorage, every access wrapped).
import type { DataPoint, DataSourceInfo, TrendSignal } from './api/types'

export type SmoothingPreset = 'raw' | 'light' | 'medium' | 'heavy' | 'line'

export const SMOOTHING_PRESETS: { value: SmoothingPreset; label: string; hint: string }[] = [
  { value: 'raw', label: 'Raw', hint: 'The data as reported' },
  { value: 'light', label: 'Light', hint: 'Trend smoothed over about a week' },
  { value: 'medium', label: 'Medium', hint: 'Trend smoothed over about a month' },
  { value: 'heavy', label: 'Heavy', hint: 'Trend smoothed over about a quarter' },
  { value: 'line', label: 'Line', hint: 'Best-fit trend line' },
]

export function isSmoothingPreset(v: unknown): v is SmoothingPreset {
  return typeof v === 'string' && SMOOTHING_PRESETS.some((p) => p.value === v)
}

const STORAGE_KEY = 'trendlab.smoothing'

function readStore(): Record<string, SmoothingPreset> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return {}
    const out: Record<string, SmoothingPreset> = {}
    for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
      if (isSmoothingPreset(v)) out[k] = v
    }
    return out
  } catch {
    return {}
  }
}

/** The user's last choice for a source, if any. */
export function loadStoredSmoothing(source: string): SmoothingPreset | null {
  return readStore()[source] ?? null
}

/** Remember the user's choice for a source (best effort). */
export function storeSmoothing(source: string, preset: SmoothingPreset): void {
  try {
    const next = { ...readStore(), [source]: preset }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    // storage unavailable: the choice just isn't remembered
  }
}

/**
 * Default preset: Medium for count-like sources whose values are summed when
 * resampled (daily downloads, page views, new stars) -- they are spiky day to
 * day -- and Raw for level-like sources (prices, temperatures, indices).
 */
export function defaultSmoothing(source: string, sources: DataSourceInfo[]): SmoothingPreset {
  const info = sources.find((s) => s.name === source)
  return info?.aggregation_method === 'sum' ? 'medium' : 'raw'
}

/** Stored choice, else the source default. */
export function preferredSmoothing(source: string, sources: DataSourceInfo[]): SmoothingPreset {
  return loadStoredSmoothing(source) ?? defaultSmoothing(source, sources)
}

/** The smoothed points for a preset, or null for Raw / when unavailable. */
export function smoothedPoints(
  trend: TrendSignal | undefined | null,
  preset: SmoothingPreset,
): DataPoint[] | null {
  if (preset === 'raw' || !trend?.smoothed) return null
  const pts = trend.smoothed[preset]
  return pts && pts.length > 0 ? pts : null
}

/** "+4.1% / month" style label for a slope in % per month. */
export function formatSlope(pct: number | null | undefined): string | null {
  if (pct == null || !Number.isFinite(pct)) return null
  const digits = Math.abs(pct) >= 100 ? 0 : 1
  const text = pct.toFixed(digits)
  return `${pct >= 0 ? '+' : ''}${text}% / month`
}
