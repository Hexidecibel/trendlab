import type {
  CompareItem,
  CompareResponse,
  CorrelateRequest,
  CorrelateResponse,
  DataSourceInfo,
  ForecastComparison,
  LookupItem,
  NaturalQueryResult,
  SavedViewResponse,
  SaveViewRequest,
  TimeSeries,
  TrendAnalysis,
  WatchlistAddRequest,
  WatchlistCheckResponse,
  WatchlistItem,
} from './types'

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(detail.detail || `HTTP ${response.status}`)
  }
  return response.json()
}

function buildParams(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  return search.toString()
}

export async function fetchSources(): Promise<DataSourceInfo[]> {
  return fetchJson('/api/sources')
}

export async function fetchSeries(
  source: string,
  query: string,
  start?: string,
  end?: string,
  resample?: string,
  apply?: string,
  refresh?: boolean,
): Promise<TimeSeries> {
  const qs = buildParams({ source, query, start, end, resample, apply, refresh: refresh ? 'true' : undefined })
  return fetchJson(`/api/series?${qs}`)
}

export async function fetchAnalysis(
  source: string,
  query: string,
  start?: string,
  end?: string,
  resample?: string,
  apply?: string,
  anomaly_method?: string,
  refresh?: boolean,
): Promise<TrendAnalysis> {
  const qs = buildParams({ source, query, start, end, resample, apply, anomaly_method, refresh: refresh ? 'true' : undefined })
  return fetchJson(`/api/analyze?${qs}`)
}

export async function fetchForecast(
  source: string,
  query: string,
  horizon?: number,
  start?: string,
  end?: string,
  resample?: string,
  apply?: string,
  refresh?: boolean,
): Promise<ForecastComparison> {
  const qs = buildParams({ source, query, horizon, start, end, resample, apply, refresh: refresh ? 'true' : undefined })
  return fetchJson(`/api/forecast?${qs}`)
}

export async function fetchLookup(
  source: string,
  lookupType: string,
  depends?: Record<string, string>,
): Promise<LookupItem[]> {
  const qs = buildParams({
    source,
    lookup_type: lookupType,
    ...depends,
  })
  return fetchJson(`/api/lookup?${qs}`)
}

export async function fetchCompare(
  items: CompareItem[],
  resample?: string,
  apply?: string,
): Promise<CompareResponse> {
  const response = await fetch('/api/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items, resample, apply }),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(detail.detail || `HTTP ${response.status}`)
  }
  return response.json()
}

export async function parseNaturalQuery(
  text: string,
): Promise<NaturalQueryResult> {
  const response = await fetch('/api/natural-query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    throw detail
  }
  return response.json()
}

export async function fetchCorrelate(
  request: CorrelateRequest,
): Promise<CorrelateResponse> {
  const response = await fetch('/api/correlate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(detail.detail || `HTTP ${response.status}`)
  }
  return response.json()
}

export async function fetchViews(): Promise<SavedViewResponse[]> {
  return fetchJson('/api/views')
}

export async function fetchView(hashId: string): Promise<SavedViewResponse> {
  return fetchJson(`/api/views/${hashId}`)
}

export async function saveView(request: SaveViewRequest): Promise<SavedViewResponse> {
  const response = await fetch('/api/views', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(detail.detail || `HTTP ${response.status}`)
  }
  return response.json()
}

export async function deleteView(hashId: string): Promise<void> {
  const response = await fetch(`/api/views/${hashId}`, { method: 'DELETE' })
  if (!response.ok && response.status !== 204) {
    throw new Error(`Failed to delete view: ${response.status}`)
  }
}

// Watchlist API functions

export async function fetchWatchlist(): Promise<WatchlistItem[]> {
  return fetchJson('/api/watchlist')
}

export async function addToWatchlist(
  request: WatchlistAddRequest,
): Promise<WatchlistItem> {
  const response = await fetch('/api/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(detail.detail || `HTTP ${response.status}`)
  }
  return response.json()
}

export async function checkWatchlist(): Promise<WatchlistCheckResponse> {
  return fetchJson('/api/watchlist/check')
}

export async function deleteWatchlistItem(itemId: number): Promise<void> {
  const response = await fetch(`/api/watchlist/${itemId}`, { method: 'DELETE' })
  if (!response.ok && response.status !== 204) {
    throw new Error(`Failed to delete watchlist item: ${response.status}`)
  }
}
