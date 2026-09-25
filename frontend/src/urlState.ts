// The current view, encoded in the page URL so it can be bookmarked, shared
// and restored on reload. Written with history.replaceState (no history spam).
//
//   Forecast: ?source=pypi&q=requests&h=14&start=..&end=..&resample=week&apply=..&smooth=medium
//   Compare:  ?tab=compare&cs=npm&cq=react&cs=npm&cq=vue&resample=..&smooth=..&mode=index
//   Saved:    ?view=<hash>[&smooth=..]   (the share link SaveViewButton generates)

import { isSmoothingPreset } from './smoothing'
import type { SmoothingPreset } from './smoothing'

export type CompareMode = 'index' | 'raw'

export interface ForecastUrlState {
  kind: 'forecast'
  source: string
  query: string
  horizon: number
  start?: string
  end?: string
  resample?: string
  apply?: string
  smooth?: SmoothingPreset
}

export interface CompareUrlState {
  kind: 'compare'
  items: { source: string; query: string }[]
  resample?: string
  smooth?: SmoothingPreset
  mode?: CompareMode
}

export interface ViewUrlState {
  kind: 'view'
  hash: string
  smooth?: SmoothingPreset
}

export type UrlState = ForecastUrlState | CompareUrlState | ViewUrlState

const HASH_RE = /^[A-Za-z0-9_-]{1,64}$/

function opt(params: URLSearchParams, key: string): string | undefined {
  const v = params.get(key)
  return v ? v : undefined
}

export function parseUrlState(search: string): UrlState | null {
  let params: URLSearchParams
  try {
    params = new URLSearchParams(search)
  } catch {
    return null
  }
  const smoothRaw = params.get('smooth')
  const smooth = isSmoothingPreset(smoothRaw) ? smoothRaw : undefined

  const view = params.get('view')
  if (view && HASH_RE.test(view)) return { kind: 'view', hash: view, smooth }

  if (params.get('tab') === 'compare') {
    const sources = params.getAll('cs')
    const queries = params.getAll('cq')
    const items = sources
      .map((source, i) => ({ source, query: queries[i] ?? '' }))
      .filter((it) => it.source && it.query)
      .slice(0, 3)
    if (items.length < 2) return null
    const mode = params.get('mode')
    return {
      kind: 'compare',
      items,
      resample: opt(params, 'resample'),
      smooth,
      mode: mode === 'raw' || mode === 'index' ? mode : undefined,
    }
  }

  const source = params.get('source')
  const query = params.get('q')
  if (!source || !query) return null
  const h = Number(params.get('h'))
  return {
    kind: 'forecast',
    source,
    query,
    horizon: Number.isFinite(h) && h > 0 ? Math.min(Math.round(h), 365) : 14,
    start: opt(params, 'start'),
    end: opt(params, 'end'),
    resample: opt(params, 'resample'),
    apply: opt(params, 'apply'),
    smooth,
  }
}

export function buildUrlSearch(state: UrlState | null): string {
  const p = new URLSearchParams()
  if (!state) return ''
  if (state.kind === 'view') {
    p.set('view', state.hash)
  } else if (state.kind === 'compare') {
    p.set('tab', 'compare')
    for (const it of state.items) {
      p.append('cs', it.source)
      p.append('cq', it.query)
    }
    if (state.resample) p.set('resample', state.resample)
    if (state.mode) p.set('mode', state.mode)
  } else {
    p.set('source', state.source)
    p.set('q', state.query)
    if (state.horizon && state.horizon !== 14) p.set('h', String(state.horizon))
    if (state.start) p.set('start', state.start)
    if (state.end) p.set('end', state.end)
    if (state.resample) p.set('resample', state.resample)
    if (state.apply) p.set('apply', state.apply)
  }
  if (state.smooth) p.set('smooth', state.smooth)
  const qs = p.toString()
  return qs ? `?${qs}` : ''
}

/** Replace the current URL's query string (no new history entry). */
export function replaceUrlState(state: UrlState | null): void {
  try {
    const search = buildUrlSearch(state)
    if (search === window.location.search) return
    const url = `${window.location.pathname}${search}${window.location.hash}`
    window.history.replaceState(window.history.state, '', url)
  } catch {
    // history unavailable (sandboxed frame): the URL just doesn't update
  }
}
