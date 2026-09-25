import { useEffect, useEffectEvent, useRef, useState } from 'react'
import Accordion from '@mui/material/Accordion'
import AccordionDetails from '@mui/material/AccordionDetails'
import AccordionSummary from '@mui/material/AccordionSummary'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Collapse from '@mui/material/Collapse'
import Grid from '@mui/material/Grid'
import LinearProgress from '@mui/material/LinearProgress'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import Typography from '@mui/material/Typography'
import EditIcon from '@mui/icons-material/Edit'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { useApi } from '../hooks/useApi'
import { useWebSocket } from '../hooks/useWebSocket'
import { fetchView } from '../api/client'
import type { NaturalCompareItem } from '../api/types'
import { NaturalQueryInput } from './NaturalQueryInput'
import { QueryForm } from './QueryForm'
import type { QueryPrefill } from './QueryForm'
import { ForecastChart } from './charts/ForecastChart'
import { ModelSelector } from './ModelSelector'
import { AnalysisPanel } from './AnalysisPanel'
import { EvaluationTable } from './EvaluationTable'
import { InsightPanel } from './InsightPanel'
import { ChangeImpactPopover } from './ChangeImpactPopover'
import type { ImpactRequest } from './ChangeImpactPopover'
import { CompareView } from './compare/CompareView'
import type { CompareRequest } from './compare/CompareView'
import { SaveViewButton } from './SaveViewButton'
import { ViewsDropdown } from './ViewsDropdown'
import { ExportPdfButton } from './ExportPdfButton'
import { ForecastAccuracyPanel } from './ForecastAccuracyPanel'
import { WatchButton } from './watchlist/WatchButton'
import { WatchlistDrawer } from './watchlist/WatchlistDrawer'
import { useWatchlist } from './watchlist/watchlistContext'
import { ProgressBar } from './ProgressBar'
import { ErrorAlert } from './ErrorAlert'
import { RecentAndSavedViews } from './RecentAndSavedViews'
import type { SavedViewResponse } from '../api/types'
import { clearRecentQueries, loadRecentQueries, recordRecentQuery } from '../recentQueries'
import type { RecentQuery } from '../recentQueries'
import { preferredSmoothing, storeSmoothing } from '../smoothing'
import type { SmoothingPreset } from '../smoothing'
import { parseUrlState, replaceUrlState } from '../urlState'
import type { CompareUrlState, UrlState } from '../urlState'
import { getFriendlyLabel } from '../utils/labels'

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

  const [queryPrefill, setQueryPrefill] = useState<QueryPrefill | null>(null)
  const [lastApply, setLastApply] = useState('')

  // URL state read once on load (share links, bookmarks, reloads)
  const [initialUrl] = useState<UrlState | null>(() => parseUrlState(window.location.search))
  const initialUrlHandled = useRef(false)

  const [activeTab, setActiveTab] = useState<'forecast' | 'compare'>(() =>
    initialUrl?.kind === 'compare' ? 'compare' : 'forecast',
  )
  // Compare owns its own state; a new request (URL / plain-English box)
  // remounts it via the id key.
  const [compareRequest, setCompareRequest] = useState<(CompareRequest & { id: number }) | null>(() =>
    initialUrl?.kind === 'compare'
      ? {
          id: 1,
          items: initialUrl.items,
          resample: initialUrl.resample,
          tool: initialUrl.tool,
          smooth: initialUrl.smooth,
          mode: initialUrl.mode,
        }
      : null,
  )
  const [compareUrl, setCompareUrl] = useState<CompareUrlState | null>(null)
  const [impact, setImpact] = useState<ImpactRequest | null>(null)
  const watchlist = useWatchlist()

  // Smoothing: an explicit choice applies to the source it was made for;
  // otherwise the user's remembered choice or the source default is used.
  const [smoothingChoice, setSmoothingChoice] = useState<{ source: string; preset: SmoothingPreset } | null>(
    () =>
      initialUrl?.kind === 'forecast' && initialUrl.smooth
        ? { source: initialUrl.source, preset: initialUrl.smooth }
        : null,
  )
  const [urlError, setUrlError] = useState<string | null>(null)
  const handleSubmit = (source: string, query: string, horizon: number, start?: string, end?: string, resample?: string, apply?: string, refresh?: boolean) => {
    setActiveTab('forecast')
    setImpact(null)
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

  const handleNlCompare = (
    items: NaturalCompareItem[],
    _interpretation: string,
    resample?: string,
  ) => {
    setActiveTab('compare')
    setCompareRequest((prev) => ({
      id: (prev?.id ?? 0) + 1,
      tool: 'overlay',
      resample,
      items: items.map((i) => ({
        source: i.source,
        query: i.query,
        start: i.start ?? undefined,
        end: i.end ?? undefined,
      })),
    }))
  }

  // Opening a watched query from the watchlist drawer
  const openWatched = useEffectEvent((source: string, query: string, resample?: string | null) => {
    loadWithPrefill(source, query, 14, undefined, undefined, resample ?? undefined)
  })
  const { setOpenQueryHandler } = watchlist
  useEffect(() => {
    setOpenQueryHandler((item) => openWatched(item.source, item.query, item.resample))
    return () => setOpenQueryHandler(null)
  }, [setOpenQueryHandler])

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
    }
    // Compare links are applied by CompareView's initial request
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

  // Keep the URL in sync with what's on screen (replaceState, no history spam)
  const urlState: UrlState | null =
    activeTab === 'compare'
      ? compareUrl
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
        loading={loading}
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
                  onDateClick={setImpact}
                  actions={
                    <>
                    <WatchButton
                      source={lastQuery.source}
                      query={lastQuery.query}
                      resample={lastQuery.resample || undefined}
                      name={getFriendlyLabel(series)}
                    />
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
                    </>
                  }
                />
                <ChangeImpactPopover
                  request={impact}
                  onClose={() => setImpact(null)}
                  source={lastQuery.source}
                  query={lastQuery.query}
                  start={lastRange.start}
                  end={lastRange.end}
                  resample={lastQuery.resample || undefined}
                  apply={lastApply || undefined}
                />
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
                <AnalysisPanel analysis={analysis} onBreakClick={setImpact} />
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
            <RecentAndSavedViews
              recent={recent}
              onLoadRecent={handleLoadRecent}
              onLoadView={handleLoadView}
              onClearRecent={handleClearRecent}
            />
          )}
        </>
      )}

      {/* Kept mounted so a compare survives switching tabs */}
      <Box hidden={activeTab !== 'compare'}>
        <CompareView
          key={compareRequest?.id ?? 0}
          sources={sources}
          request={compareRequest}
          onUrlState={setCompareUrl}
        />
      </Box>

      <WatchlistDrawer sources={sources} />
    </Box>
  )
}
