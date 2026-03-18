import { useState, useEffect, useCallback } from 'react'
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

let idCounter = 0
function generateRequestId(): string {
  idCounter += 1
  return `${Date.now()}-${idCounter}`
}

export function useApi() {
  const [sources, setSources] = useState<DataSourceInfo[]>([])
  const [series, setSeries] = useState<TimeSeries | null>(null)
  const [analysis, setAnalysis] = useState<TrendAnalysis | null>(null)
  const [forecast, setForecast] = useState<ForecastComparison | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | ApiError | null>(null)
  const [requestId, setRequestId] = useState<string | null>(null)

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
    ) => {
      const rid = generateRequestId()
      setRequestId(rid)
      setLoading(true)
      setError(null)
      setSeries(null)
      setAnalysis(null)
      setForecast(null)

      try {
        const [s, a, f] = await Promise.all([
          fetchSeries(source, query, start, end, resample, apply, refresh),
          fetchAnalysis(source, query, start, end, resample, apply, anomalyMethod, refresh),
          fetchForecast(source, query, horizon, start, end, resample, apply, refresh),
        ])
        setSeries(s)
        setAnalysis(a)
        setForecast(f)
      } catch (err) {
        setError(err instanceof ApiError ? err : err instanceof Error ? err.message : String(err))
      } finally {
        setLoading(false)
        setRequestId(null)
      }
    },
    [],
  )

  return { sources, series, analysis, forecast, loading, error, loadData, requestId }
}
