import type {
  ApiErrorResponse,
  CausalImpactResponse,
  CohortRequest,
  CohortResponse,
  CompareItem,
  CompareResponse,
  CorrelateRequest,
  CorrelateResponse,
  DataSourceInfo,
  EventContext,
  ForecastComparison,
  LookupItem,
  NaturalQueryResult,
  PluginInfo,
  SavedViewResponse,
  SaveViewRequest,
  TimeSeries,
  TrendAnalysis,
  NotificationConfig,
  NotificationConfigRequest,
  NotificationStatus,
  WatchlistAddRequest,
  WatchlistCheckResponse,
  WatchlistItem,
} from './types'

export const API_BASE = '/api/v1'

export class ApiError extends Error {
  hint: string | null
  errorCode: string | null
  requestId: string | null

  constructor(response: ApiErrorResponse) {
    super(response.detail)
    this.name = 'ApiError'
    this.hint = response.hint ?? null
    this.errorCode = response.error_code ?? null
    this.requestId = response.request_id ?? null
  }
}

function parseErrorResponse(body: unknown): ApiErrorResponse {
  if (
    typeof body === 'object' &&
    body !== null &&
    'detail' in body &&
    typeof (body as Record<string, unknown>).detail === 'string'
  ) {
    const b = body as Record<string, unknown>
    return {
      detail: b.detail as string,
      hint: (b.hint as string) ?? null,
      error_code: (b.error_code as string) ?? null,
      request_id: (b.request_id as string) ?? null,
    }
  }
  // If detail is a dict (e.g. from NaturalQueryError), pass through as-is for special handling
  if (
    typeof body === 'object' &&
    body !== null &&
    'detail' in body &&
    typeof (body as Record<string, unknown>).detail === 'object'
  ) {
    return {
      detail: JSON.stringify((body as Record<string, unknown>).detail),
      hint: null,
      error_code: null,
      request_id: (body as Record<string, unknown>).request_id as string ?? null,
    }
  }
  return {
    detail: 'An unexpected error occurred',
    hint: null,
    error_code: null,
    request_id: null,
  }
}

async function extractError(response: Response): Promise<ApiError> {
  try {
    const body = await response.json()
    return new ApiError(parseErrorResponse(body))
  } catch {
    return new ApiError({
      detail: response.statusText || `HTTP ${response.status}`,
      hint: null,
      error_code: null,
      request_id: null,
    })
  }
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    throw await extractError(response)
  }
  return response.json()
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw await extractError(response)
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
  return fetchJson(`${API_BASE}/sources`)
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
  return fetchJson(`${API_BASE}/series?${qs}`)
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
  return fetchJson(`${API_BASE}/analyze?${qs}`)
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
  return fetchJson(`${API_BASE}/forecast?${qs}`)
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
  return fetchJson(`${API_BASE}/lookup?${qs}`)
}

export async function fetchCompare(
  items: CompareItem[],
  resample?: string,
  apply?: string,
): Promise<CompareResponse> {
  return postJson(`${API_BASE}/compare`, { items, resample, apply })
}

export async function parseNaturalQuery(
  text: string,
): Promise<NaturalQueryResult> {
  const response = await fetch(`${API_BASE}/natural-query`, {
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
  return postJson(`${API_BASE}/correlate`, request)
}

export async function fetchCausalImpact(
  source: string,
  query: string,
  eventDate: string,
  options?: {
    start?: string
    end?: string
    resample?: string
    apply?: string
    refresh?: boolean
  },
): Promise<CausalImpactResponse> {
  return postJson(`${API_BASE}/causal-impact`, {
    source,
    query,
    event_date: eventDate,
    start: options?.start,
    end: options?.end,
    resample: options?.resample,
    apply: options?.apply,
    refresh: options?.refresh,
  })
}

export async function fetchCohort(
  request: CohortRequest,
): Promise<CohortResponse> {
  return postJson(`${API_BASE}/cohort`, request)
}

export async function fetchViews(): Promise<SavedViewResponse[]> {
  return fetchJson(`${API_BASE}/views`)
}

export async function fetchView(hashId: string): Promise<SavedViewResponse> {
  return fetchJson(`${API_BASE}/views/${hashId}`)
}

export async function saveView(request: SaveViewRequest): Promise<SavedViewResponse> {
  return postJson(`${API_BASE}/views`, request)
}

export async function deleteView(hashId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/views/${hashId}`, { method: 'DELETE' })
  if (!response.ok && response.status !== 204) {
    throw await extractError(response)
  }
}

// Watchlist API functions

export async function fetchWatchlist(): Promise<WatchlistItem[]> {
  return fetchJson(`${API_BASE}/watchlist`)
}

export async function addToWatchlist(
  request: WatchlistAddRequest,
): Promise<WatchlistItem> {
  return postJson(`${API_BASE}/watchlist`, request)
}

export async function checkWatchlist(): Promise<WatchlistCheckResponse> {
  return fetchJson(`${API_BASE}/watchlist/check`)
}

export async function deleteWatchlistItem(itemId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/watchlist/${itemId}`, { method: 'DELETE' })
  if (!response.ok && response.status !== 204) {
    throw await extractError(response)
  }
}

export async function fetchEventContext(
  source: string,
  query: string,
  dates: string[],
): Promise<EventContext[]> {
  const qs = buildParams({ source, query, dates: dates.join(',') })
  return fetchJson(`${API_BASE}/event-context?${qs}`)
}

// Notification API functions

export async function getNotificationConfig(): Promise<NotificationConfig | null> {
  return fetchJson(`${API_BASE}/notifications/config`)
}

export async function saveNotificationConfig(
  config: NotificationConfigRequest,
): Promise<NotificationConfig> {
  return postJson(`${API_BASE}/notifications/config`, config)
}

export async function getNotificationStatus(): Promise<NotificationStatus> {
  return fetchJson(`${API_BASE}/notifications/status`)
}

export async function testNotification(): Promise<{ status: string; message: string }> {
  return postJson(`${API_BASE}/notifications/test`, {})
}

// Plugin API functions

export async function fetchPlugins(): Promise<PluginInfo[]> {
  return fetchJson(`${API_BASE}/plugins`)
}

export async function reloadPlugins(): Promise<PluginInfo[]> {
  return postJson(`${API_BASE}/plugins/reload`, {})
}
