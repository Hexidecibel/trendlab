// Recently loaded queries, kept per-browser in localStorage.
// Every storage access is wrapped: private windows / blocked storage must not break the app.

export interface RecentQuery {
  source: string
  query: string
  horizon: number
  start?: string
  end?: string
  resample?: string
  apply?: string
  label: string
  ts: number
}

const KEY = 'trendlab.recentQueries'
const MAX = 8

function sameQuery(a: RecentQuery, b: RecentQuery): boolean {
  return (
    a.source === b.source &&
    a.query === b.query &&
    (a.start || '') === (b.start || '') &&
    (a.end || '') === (b.end || '') &&
    (a.resample || '') === (b.resample || '') &&
    (a.apply || '') === (b.apply || '')
  )
}

export function loadRecentQueries(): RecentQuery[] {
  try {
    const raw = window.localStorage.getItem(KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter(
        (r): r is RecentQuery =>
          !!r && typeof r === 'object' &&
          typeof (r as RecentQuery).source === 'string' &&
          typeof (r as RecentQuery).query === 'string',
      )
      .slice(0, MAX)
  } catch {
    return []
  }
}

export function recordRecentQuery(entry: Omit<RecentQuery, 'ts'>): RecentQuery[] {
  const full: RecentQuery = { ...entry, ts: Date.now() }
  const next = [full, ...loadRecentQueries().filter((r) => !sameQuery(r, full))].slice(0, MAX)
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    // storage unavailable: keep going without persistence
  }
  return next
}

export function clearRecentQueries(): void {
  try {
    window.localStorage.removeItem(KEY)
  } catch {
    // ignore
  }
}
