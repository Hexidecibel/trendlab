import { useEffect, useEffectEvent, useRef, useState } from 'react'
import Accordion from '@mui/material/Accordion'
import AccordionDetails from '@mui/material/AccordionDetails'
import AccordionSummary from '@mui/material/AccordionSummary'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CircularProgress from '@mui/material/CircularProgress'
import Collapse from '@mui/material/Collapse'
import Divider from '@mui/material/Divider'
import Grid from '@mui/material/Grid'
import LinearProgress from '@mui/material/LinearProgress'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import Typography from '@mui/material/Typography'
import EditIcon from '@mui/icons-material/Edit'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { useApi } from '../hooks/useApi'
import { useWebSocket } from '../hooks/useWebSocket'
import { ApiError, fetchCompare, fetchCorrelate, fetchView } from '../api/client'
import type { CompareItem, CorrelateResponse, NaturalCompareItem, TimeSeries, TrendAnalysis } from '../api/types'
import { NaturalQueryInput } from './NaturalQueryInput'
import { QueryForm } from './QueryForm'
import type { QueryPrefill } from './QueryForm'
import { CompareForm } from './CompareForm'
import type { ComparePrefill } from './CompareForm'
import { ForecastChart } from './charts/ForecastChart'
import { CompareChart } from './charts/CompareChart'
import { ModelSelector } from './ModelSelector'
import { AnalysisPanel } from './AnalysisPanel'
import { EvaluationTable } from './EvaluationTable'
import { InsightPanel } from './InsightPanel'
import { CompareInsightPanel } from './CompareInsightPanel'
import { CausalImpactPanel } from './CausalImpactPanel'
import { CohortPanel } from './CohortPanel'
import { CorrelateTab } from './CorrelateTab'
import { SaveViewButton } from './SaveViewButton'
import { ViewsDropdown } from './ViewsDropdown'
import { ExportPdfButton } from './ExportPdfButton'
import { ForecastAccuracyPanel } from './ForecastAccuracyPanel'
import { WatchlistPanel } from './WatchlistPanel'
import { ProgressBar } from './ProgressBar'
import { ErrorAlert } from './ErrorAlert'
import { RecentAndSavedViews } from './RecentAndSavedViews'
import type { SavedViewResponse } from '../api/types'
import { clearRecentQueries, loadRecentQueries, recordRecentQuery } from '../recentQueries'
import type { RecentQuery } from '../recentQueries'
import { preferredSmoothing, storeSmoothing } from '../smoothing'
import type { SmoothingPreset } from '../smoothing'
import { parseUrlState, replaceUrlState } from '../urlState'
import type { CompareMode, UrlState } from '../urlState'

// Generate a friendly label from series metadata or query
function getFriendlyLabel(s: TimeSeries): string {
  const meta = s.metadata || {}

  // Try to build from metadata
  if (meta.article) return `${meta.article} (Wikipedia)`
  if (meta.package) return `${meta.package} (${s.source === 'npm' ? 'npm' : 'PyPI'})`
  if (meta.coin) return `${meta.coin} (Crypto)`
  if (meta.symbol) return `${meta.symbol} (${meta.metric || 'Stock'})`
  if (meta.team) return `${meta.team} (${meta.metric_label || 'xG'})`
  if (meta.player) return `${meta.player} (${meta.metric_label || 'xG'})`
  if (meta.location) return `${meta.location} (${meta.metric_label || 'Weather'})`

  // Fallback: simplify query
  const query = s.query
  if (query.includes(':')) {
    const parts = query.split(':')
    return parts[1] || parts[0] || query
  }

  return `${s.source}: ${query}`
}

export function Dashboard() {
  const { sources, series, analysis, forecast, loading, error, loadData, requestId } =
    useApi()
  const wsProgress = useWebSocket(requestId)
  const [selectedModel, setSelectedModel] = useState('')
  const [lastQuery, setLastQuery] = useState({ source: '', query: '', horizon: 14, resample: '' })
  const [lastRange, setLastRange] = useState<{ start?: string; end?: string }>({})
  const [showAnnotations, setShowAnnotations] = useState(true)
  const [editOpen, setEditOpen] = useState(false)
  const [recent, setRecent] = useState<RecentQuery[]>(() => loadRecentQueries())

  const [activeTab, setActiveTab] = useState<'forecast' | 'compare' | 'correlate'>('forecast')
  const [compareSeries, setCompareSeries] = useState<TimeSeries[] | null>(null)
  const [compareAnalyses, setCompareAnalyses] = useState<TrendAnalysis[] | null>(null)
  const [compareResample, setCompareResample] = useState('')
  const [compareApply, setCompareApply] = useState('')
  const [compareItems, setCompareItems] = useState<CompareItem[]>([])
  const [compareLoading, setCompareLoading] = useState(false)
  const [compareError, setCompareError] = useState<string | ApiError | null>(null)
  const [queryPrefill, setQueryPrefill] = useState<QueryPrefill | null>(null)
  const [comparePrefill, setComparePrefill] = useState<ComparePrefill | null>(null)
  const [lastApply, setLastApply] = useState('')

  // URL state read once on load (share links, bookmarks, reloads)
  const [initialUrl] = useState<UrlState | null>(() => parseUrlState(window.location.search))
  const initialUrlHandled = useRef(false)

  // Smoothing: an explicit choice applies to the source it was made for;
  // otherwise the user's remembered choice or the source default is used.
  const [smoothingChoice, setSmoothingChoice] = useState<{ source: string; preset: SmoothingPreset } | null>(
    () =>
      initialUrl?.kind === 'forecast' && initialUrl.smooth
        ? { source: initialUrl.source, preset: initialUrl.smooth }
        : null,
  )
  const [urlError, setUrlError] = useState<string | null>(null)
  const [compareSmoothingChoice, setCompareSmoothingChoice] = useState<SmoothingPreset | null>(
    () => (initialUrl?.kind === 'compare' && initialUrl.smooth) || null,
  )
  const [compareMode, setCompareMode] = useState<CompareMode>(
    () => (initialUrl?.kind === 'compare' && initialUrl.mode) || 'index',
  )
  const [compareCorrelation, setCompareCorrelation] = useState<CorrelateResponse | null>(null)
  const compareRunRef = useRef(0)

  const handleSubmit = (source: string, query: string, horizon: number, start?: string, end?: string, resample?: string, apply?: string, refresh?: boolean) => {
    setActiveTab('forecast')
    // Anomaly method is left to the backend default (trend-residual scoring).
    // The query/range describing the chart only change once the new data is
    // in: until then the previous chart stays up (dimmed) as it was.
    loadData(source, query, horizon, start, end, resample, apply, undefined, refresh).then((s) => {
      if (!s) return
      setLastQuery({ source, query, horizon, resample: resample || '' })
      setLastRange({ start, end })
      setLastApply(apply || '')
      setSelectedModel('')
      setRecent(
        recordRecentQuery({
          source,
          query,
          horizon,
          start,
          end,
          resample,
          apply,
          label: getFriendlyLabel(s),
        }),
      )
    })
  }

  const loadWithPrefill = (
    source: string,
    query: string,
    horizon: number,
    start?: string,
    end?: string,
    resample?: string,
    apply?: string,
  ) => {
    setQueryPrefill({ source, query, horizon, start, end, resample })
    handleSubmit(source, query, horizon, start, end, resample, apply)
  }

  const handleLoadView = (view: SavedViewResponse, smooth?: SmoothingPreset | null) => {
    if (smooth) setSmoothingChoice({ source: view.source, preset: smooth })
    loadWithPrefill(
      view.source,
      view.query,
      view.horizon,
      view.start ?? undefined,
      view.end ?? undefined,
      view.resample ?? undefined,
      view.apply ?? undefined,
    )
  }

  const handleLoadRecent = (r: RecentQuery) => {
    loadWithPrefill(r.source, r.query, r.horizon || 14, r.start, r.end, r.resample, r.apply)
  }

  const handleClearRecent = () => {
    clearRecentQueries()
    setRecent([])
  }

  const handleNlExplore = (source: string, query: string, horizon: number, start?: string, end?: string, resample?: string, apply?: string) => {
    loadWithPrefill(source, query, horizon, start, end, resample, apply)
  }

  const handleFormSourceChange = (source: string) => {
    // CSV needs the upload control, which lives in the form
    if (source === 'csv') setEditOpen(true)
  }

  const handleCompare = async (items: CompareItem[], resample?: string, apply?: string) => {
    const run = ++compareRunRef.current
    setCompareLoading(true)
    setCompareError(null)
    setCompareSeries(null)
    setCompareAnalyses(null)
    setCompareCorrelation(null)
    setCompareResample(resample || '')
    setCompareApply(apply || '')
    setCompareItems(items)
    // Correlation stat for two-series compares; best effort, never blocks
    if (items.length === 2) {
      fetchCorrelate({ series_a: items[0], series_b: items[1], resample: resample || undefined })
        .then((c) => {
          if (compareRunRef.current === run) setCompareCorrelation(c)
        })
        .catch(() => {})
    }
    try {
      const result = await fetchCompare(items, resample, apply)
      if (compareRunRef.current !== run) return
      setCompareSeries(result.series)
      setCompareAnalyses(result.analyses ?? null)
    } catch (err) {
      if (compareRunRef.current !== run) return
      setCompareError(err instanceof ApiError ? err : err instanceof Error ? err.message : String(err))
    } finally {
      if (compareRunRef.current === run) setCompareLoading(false)
    }
  }

  const handleNlCompare = (
    items: NaturalCompareItem[],
    _interpretation: string,
    resample?: string,
  ) => {
    setActiveTab('compare')
    setComparePrefill({
      items: items.map((i) => ({ source: i.source, query: i.query })),
      resample,
    })
    const compareItems: CompareItem[] = items.map((i) => ({
      source: i.source,
      query: i.query,
      start: i.start ?? undefined,
      end: i.end ?? undefined,
    }))
    // Wait for next tick to ensure state updates are flushed before API call
    setTimeout(() => handleCompare(compareItems, resample), 0)
  }

  // Restore the view encoded in the URL once, on first load
  const restoreFromUrl = useEffectEvent(() => {
    const u = initialUrl
    if (!u) return
    if (u.kind === 'view') {
      fetchView(u.hash)
        .then((view) => handleLoadView(view, u.smooth))
        .catch((err) => {
          setUrlError(
            `Couldn't open the shared view: ${err instanceof Error ? err.message : String(err)}`,
          )
        })
    } else if (u.kind === 'forecast') {
      loadWithPrefill(u.source, u.query, u.horizon, u.start, u.end, u.resample, u.apply)
    } else {
      setActiveTab('compare')
      setComparePrefill({ items: u.items, resample: u.resample })
      handleCompare(u.items, u.resample)
    }
  })
  useEffect(() => {
    if (initialUrlHandled.current) return
    initialUrlHandled.current = true
    restoreFromUrl()
  }, [])

  // Smoothing shown for the current chart
  const smoothing: SmoothingPreset =
    smoothingChoice && smoothingChoice.source === lastQuery.source
      ? smoothingChoice.preset
      : preferredSmoothing(lastQuery.source, sources)
  const handleSmoothingChange = (preset: SmoothingPreset) => {
    setSmoothingChoice({ source: lastQuery.source, preset })
    storeSmoothing(lastQuery.source, preset)
  }

  // Compare: Medium when every series is count-like, else Raw (or the choice)
  const compareSources = compareItems.map((i) => i.source)
  const compareSmoothing: SmoothingPreset =
    compareSmoothingChoice ??
    (compareSources.length > 0 && compareSources.every((src) => preferredSmoothing(src, sources) !== 'raw')
      ? 'medium'
      : 'raw')

  // Keep the URL in sync with what's on screen (replaceState, no history spam)
  const urlState: UrlState | null =
    activeTab === 'compare'
      ? compareItems.length >= 2
        ? {
            kind: 'compare',
            items: compareItems.map((i) => ({ source: i.source, query: i.query })),
            resample: compareResample || undefined,
            smooth: compareSmoothing,
            mode: compareMode,
          }
        : null
      : activeTab === 'forecast' && lastQuery.source && lastQuery.query
        ? {
            kind: 'forecast',
            source: lastQuery.source,
            query: lastQuery.query,
            horizon: lastQuery.horizon,
            start: lastRange.start,
            end: lastRange.end,
            resample: lastQuery.resample || undefined,
            apply: lastApply || undefined,
            smooth: smoothing,
          }
        : null
  // Serialized so the effect runs only when the content changes. Nothing on
  // screen (e.g. an empty tab, or a shared link still loading) leaves the
  // current URL alone.
  const urlKey = urlState ? JSON.stringify(urlState) : ''
  useEffect(() => {
    if (urlKey) replaceUrlState(JSON.parse(urlKey) as UrlState)
  }, [urlKey])

  const effectiveModel =
    selectedModel || forecast?.recommended_model || ''
  const isAutoModel = !!forecast && effectiveModel === forecast.recommended_model
  const forecastLabel = isAutoModel ? `Forecast (auto · ${effectiveModel})` : `Forecast (${effectiveModel})`

  const hasData = series && analysis && forecast
  const csvSelected = queryPrefill?.source === 'csv'

  return (
    <Box>
      <NaturalQueryInput
        loading={loading || compareLoading}
        onResult={handleNlExplore}
        onCompareResult={handleNlCompare}
      />

      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 1,
          mb: 2,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Tabs
          value={activeTab}
          onChange={(_, v) => setActiveTab(v)}
          variant="scrollable"
          scrollButtons={false}
          sx={{
            minWidth: 0,
            '& .MuiTab-root': { minWidth: { xs: 64, sm: 90 }, px: { xs: 1.25, sm: 2 } },
          }}
        >
          <Tab value="forecast" label="Forecast" />
          <Tab value="compare" label="Compare" />
          <Tab value="correlate" label="Correlate" />
        </Tabs>
        <Box sx={{ pb: 1, flexShrink: 0 }}>
          <ViewsDropdown onLoadView={handleLoadView} />
        </Box>
      </Box>

      {activeTab === 'forecast' && (
        <>
          <Box sx={{ mb: 2 }}>
            <Button
              size="small"
              variant="text"
              startIcon={<EditIcon fontSize="small" />}
              endIcon={
                <ExpandMoreIcon
                  sx={{ transition: 'transform 0.2s', transform: editOpen || csvSelected ? 'rotate(180deg)' : 'none' }}
                />
              }
              onClick={() => setEditOpen(!editOpen)}
              aria-expanded={editOpen || csvSelected}
            >
              Edit query
            </Button>
            <Collapse in={editOpen || csvSelected}>
              <Card sx={{ mt: 1 }}>
                <CardContent>
                  <QueryForm
                    sources={sources}
                    loading={loading}
                    onSubmit={handleSubmit}
                    prefill={queryPrefill}
                    onSourceChange={handleFormSourceChange}
                  />
                </CardContent>
              </Card>
            </Collapse>
          </Box>

          {error && <ErrorAlert error={error} />}
          {urlError && !hasData && <ErrorAlert error={urlError} />}

          {loading && !hasData && <ProgressBar progress={wsProgress} />}

          {loading && hasData && (
            <LinearProgress
              variant={wsProgress.connected && wsProgress.progress > 0 ? 'determinate' : 'indeterminate'}
              value={Math.round(wsProgress.progress * 100)}
              sx={{ mb: 1, borderRadius: 1 }}
              aria-label="Loading new data"
            />
          )}

          {hasData && (
            <Grid
              container
              spacing={3}
              sx={{
                opacity: loading ? 0.5 : 1,
                transition: 'opacity 0.2s',
                pointerEvents: loading ? 'none' : undefined,
              }}
              aria-busy={loading}
            >
              <Grid size={{ xs: 12, lg: 8 }}>
                <ForecastChart
                  series={series}
                  forecast={forecast}
                  selectedModel={effectiveModel}
                  forecastLabel={forecastLabel}
                  analysis={analysis}
                  showAnnotations={showAnnotations}
                  onShowAnnotationsChange={setShowAnnotations}
                  resample={lastQuery.resample}
                  smoothing={smoothing}
                  onSmoothingChange={handleSmoothingChange}
                  actions={
                    <SaveViewButton
                      iconOnly
                      smoothing={smoothing}
                      source={lastQuery.source}
                      query={lastQuery.query}
                      horizon={lastQuery.horizon}
                      start={lastRange.start}
                      end={lastRange.end}
                      resample={lastQuery.resample || undefined}
                      apply={lastApply || undefined}
                    />
                  }
                />
                {lastQuery.source && lastQuery.query && (
                  <CausalImpactPanel
                    source={lastQuery.source}
                    query={lastQuery.query}
                    start={lastRange.start}
                    end={lastRange.end}
                    resample={lastQuery.resample || undefined}
                    apply={lastApply || undefined}
                  />
                )}
                <Accordion
                  disableGutters
                  sx={{ mt: 2, borderRadius: 3, '&:before': { display: 'none' } }}
                >
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle2">Advanced</Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1, alignSelf: 'center' }}>
                      models, accuracy, PDF
                    </Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, alignItems: 'center', mb: 2 }}>
                      <Box sx={{ overflowX: 'auto', maxWidth: '100%' }}>
                        <ModelSelector
                          forecast={forecast}
                          selected={effectiveModel}
                          onChange={setSelectedModel}
                        />
                      </Box>
                      <ExportPdfButton
                        source={lastQuery.source}
                        query={lastQuery.query}
                        horizon={lastQuery.horizon}
                        start={lastRange.start}
                        end={lastRange.end}
                        resample={lastQuery.resample || undefined}
                        apply={lastApply || undefined}
                      />
                    </Box>
                    <Box sx={{ overflowX: 'auto' }}>
                      <EvaluationTable
                        evaluations={forecast.evaluations}
                        recommended={forecast.recommended_model}
                      />
                    </Box>
                    {lastQuery.source && lastQuery.query && (
                      <ForecastAccuracyPanel
                        source={lastQuery.source}
                        query={lastQuery.query}
                        forecast={forecast}
                      />
                    )}
                  </AccordionDetails>
                </Accordion>
              </Grid>

              <Grid size={{ xs: 12, lg: 4 }}>
                <AnalysisPanel analysis={analysis} />
                {lastQuery.source && lastQuery.query && (
                  <Box sx={{ mt: 3 }}>
                    <InsightPanel
                      source={lastQuery.source}
                      query={lastQuery.query}
                      horizon={lastQuery.horizon}
                      start={lastRange.start}
                      end={lastRange.end}
                      resample={lastQuery.resample || undefined}
                      apply={lastApply || undefined}
                      series={series}
                      analysis={analysis}
                      forecast={forecast}
                    />
                  </Box>
                )}
              </Grid>
            </Grid>
          )}

          {!hasData && !loading && (
            <Grid container spacing={3}>
              <Grid size={{ xs: 12, md: 8 }}>
                <RecentAndSavedViews
                  recent={recent}
                  onLoadRecent={handleLoadRecent}
                  onLoadView={handleLoadView}
                  onClearRecent={handleClearRecent}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <WatchlistPanel
                  sources={sources}
                  onLoadQuery={(source, query) => handleSubmit(source, query, 14)}
                />
              </Grid>
            </Grid>
          )}
        </>
      )}

      {activeTab === 'compare' && (
        <>
          <CompareForm
            sources={sources}
            loading={compareLoading}
            onSubmit={handleCompare}
            prefill={comparePrefill}
          />

          {compareError && <ErrorAlert error={compareError} />}

          {compareLoading && (
            <Box sx={{ textAlign: 'center', py: 6 }}>
              <CircularProgress size={32} />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                Fetching comparison data...
              </Typography>
            </Box>
          )}

          {compareSeries && !compareLoading && (
            <>
              <Grid container spacing={3}>
                <Grid size={{ xs: 12, lg: compareAnalyses ? 8 : 12 }}>
                  <CompareChart
                    seriesList={compareSeries}
                    analyses={compareAnalyses}
                    resample={compareResample}
                    smoothing={compareSmoothing}
                    onSmoothingChange={setCompareSmoothingChoice}
                    mode={compareMode}
                    onModeChange={setCompareMode}
                    correlation={compareCorrelation}
                  />
                </Grid>
                {compareAnalyses && (
                  <Grid size={{ xs: 12, lg: 4 }}>
                    {compareAnalyses.map((a, i) => (
                      <Box key={i} sx={{ mb: 2 }}>
                        <Typography
                          variant="subtitle2"
                          sx={{
                            mb: 1,
                            color: ['#3b82f6', '#f97316', '#10b981'][i],
                            fontWeight: 600,
                          }}
                        >
                          {getFriendlyLabel(compareSeries[i])}
                        </Typography>
                        <AnalysisPanel analysis={a} compact />
                      </Box>
                    ))}
                  </Grid>
                )}
              </Grid>
              {compareItems.length >= 2 && (
                <CompareInsightPanel
                  items={compareItems}
                  resample={compareResample}
                  apply={compareApply}
                  seriesList={compareSeries ?? undefined}
                  analyses={compareAnalyses ?? undefined}
                />
              )}
            </>
          )}

          {!compareSeries && !compareLoading && !compareError && (
            <Box sx={{ textAlign: 'center', py: 8 }}>
              <Typography variant="body1" color="text.secondary" gutterBottom>
                Pick 2-3 series to compare side by side
              </Typography>
              <Typography variant="body2" color="text.disabled">
                Or try "compare fastapi and django" in the search bar above
              </Typography>
            </Box>
          )}

          <Divider sx={{ my: 3 }}>
            <Typography variant="caption" color="text.secondary">
              Cohort Analysis
            </Typography>
          </Divider>

          <CohortPanel sources={sources} />
        </>
      )}

      {activeTab === 'correlate' && (
        <CorrelateTab sources={sources} />
      )}

    </Box>
  )
}
