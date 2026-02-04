import type {
  DataSourceInfo,
  ForecastComparison,
  LookupItem,
  TimeSeries,
  TrendAnalysis,
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
): Promise<TimeSeries> {
  const qs = buildParams({ source, query, start, end })
  return fetchJson(`/api/series?${qs}`)
}

export async function fetchAnalysis(
  source: string,
  query: string,
  start?: string,
  end?: string,
): Promise<TrendAnalysis> {
  const qs = buildParams({ source, query, start, end })
  return fetchJson(`/api/analyze?${qs}`)
}

export async function fetchForecast(
  source: string,
  query: string,
  horizon?: number,
  start?: string,
  end?: string,
): Promise<ForecastComparison> {
  const qs = buildParams({ source, query, horizon, start, end })
  return fetchJson(`/api/forecast?${qs}`)
}

export async function fetchLookup(
  source: string,
  lookupType: string,
  league?: string,
  season?: string,
): Promise<LookupItem[]> {
  const qs = buildParams({
    source,
    lookup_type: lookupType,
    league,
    season,
  })
  return fetchJson(`/api/lookup?${qs}`)
}
