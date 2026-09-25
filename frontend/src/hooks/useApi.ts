import { useState, useEffect, useCallback, useRef } from 'react'
import {
  ApiError,
  fetchSources,
  fetchSeries,
  fetchAnalysis,
  fetchForecast,
} from '../api/client'
import type {
  DataSourceInfo,
  TimeSeries,
  TrendAnalysis,
  ForecastComparison,
} from '../api/types'

/**
 * A request id the server accepts as `X-Request-ID` (<= 64 chars of
 * [A-Za-z0-9-]) and uses to key WebSocket progress events. Random, so ids
 * from different tabs/users can't collide.
 */
function generateRequestId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID()
    }
  } catch {
    // fall through (randomUUID needs a secure context)
  }
  const rand = () => Math.random().toString(36).slice(2, 10)
  return `${Date.now().toString(36)}-${rand()}-${rand()}`
}

export function useApi() {
  const [sources, setSources] = useState<DataSourceInfo[]>([])
  const [series, setSeries] = useState<TimeSeries | null>(null)
  const [analysis, setAnalysis] = useState<TrendAnalysis | null>(null)
  const [forecast, setForecast] = useState<ForecastComparison | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | ApiError | null>(null)
  const [requestId, setRequestId] = useState<string | null>(null)
  // Only the latest load may write results (a slow earlier one is dropped)
  const latestRef = useRef<string | null>(null)

  useEffect(() => {
    fetchSources()
      .then(setSources)
      .catch((err) => setError(err instanceof ApiError ? err : err.message))
  }, [])

  const loadData = useCallback(
    async (
      source: string,
      query: string,
      horizon: number,
      start?: string,
      end?: string,
      resample?: string,
      apply?: string,
      anomalyMethod?: string,
      refresh?: boolean,
    ): Promise<TimeSeries | null> => {
      const rid = generateRequestId()
      latestRef.current = rid
      setRequestId(rid)
      setLoading(true)
      setError(null)
      // The previous chart stays up (dimmed) until the new data arrives.

      try {
        // Only the forecast request carries the id: it runs the longest
        // pipeline (fetch -> forecast), and one request per id keeps the
        // progress bar monotonic and its "complete" event meaningful.
        const [s, a, f] = await Promise.all([
          fetchSeries(source, query, start, end, resample, apply, refresh),
          fetchAnalysis(source, query, start, end, resample, apply, anomalyMethod, refresh),
          fetchForecast(source, query, horizon, start, end, resample, apply, refresh, rid),
        ])
        if (latestRef.current !== rid) return null
        setSeries(s)
        setAnalysis(a)
        setForecast(f)
        return s
      } catch (err) {
        if (latestRef.current !== rid) return null
        setSeries(null)
        setAnalysis(null)
        setForecast(null)
        setError(err instanceof ApiError ? err : err instanceof Error ? err.message : String(err))
        return null
      } finally {
        if (latestRef.current === rid) {
          setLoading(false)
          setRequestId(null)
        }
      }
    },
    [],
  )

  return { sources, series, analysis, forecast, loading, error, loadData, requestId }
}
