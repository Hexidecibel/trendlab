import { useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import FormControl from '@mui/material/FormControl'
import FormControlLabel from '@mui/material/FormControlLabel'
import Checkbox from '@mui/material/Checkbox'
import Grid from '@mui/material/Grid'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import Select from '@mui/material/Select'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import Typography from '@mui/material/Typography'
import { useApi } from '../hooks/useApi'
import { fetchCompare } from '../api/client'
import type { CompareItem, NaturalCompareItem, TimeSeries, TrendAnalysis } from '../api/types'
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
import { CorrelateTab } from './CorrelateTab'
import { SaveViewButton } from './SaveViewButton'
import { ViewsDropdown } from './ViewsDropdown'
import { InsightsFeed } from './InsightsFeed'
import { ExportPdfButton } from './ExportPdfButton'
import { ForecastAccuracyPanel } from './ForecastAccuracyPanel'
import { WatchlistPanel } from './WatchlistPanel'
import type { SavedViewResponse } from '../api/types'

// Generate a friendly label from series metadata or query
function getFriendlyLabel(s: TimeSeries): string {
  const meta = s.metadata || {}

  // Try to build from metadata
  if (meta.article) return `${meta.article} (Wikipedia)`
  if (meta.package) return `${meta.package} (PyPI)`
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
  const { sources, series, analysis, forecast, loading, error, loadData } =
    useApi()
  const [selectedModel, setSelectedModel] = useState('')
  const [lastQuery, setLastQuery] = useState({ source: '', query: '', horizon: 14, resample: '' })
  const [showBreaks, setShowBreaks] = useState(true)
  const [showAnomalies, setShowAnomalies] = useState(true)

  const [activeTab, setActiveTab] = useState<'forecast' | 'compare' | 'correlate'>('forecast')
  const [compareSeries, setCompareSeries] = useState<TimeSeries[] | null>(null)
  const [compareAnalyses, setCompareAnalyses] = useState<TrendAnalysis[] | null>(null)
  const [compareResample, setCompareResample] = useState('')
  const [compareApply, setCompareApply] = useState('')
  const [compareItems, setCompareItems] = useState<CompareItem[]>([])
  const [compareLoading, setCompareLoading] = useState(false)
  const [compareError, setCompareError] = useState<string | null>(null)
  const [anomalyMethod, setAnomalyMethod] = useState('zscore')
  const [queryPrefill, setQueryPrefill] = useState<QueryPrefill | null>(null)
  const [comparePrefill, setComparePrefill] = useState<ComparePrefill | null>(null)
  const [lastApply, setLastApply] = useState('')

  const handleSubmit = (source: string, query: string, horizon: number, start?: string, end?: string, resample?: string, apply?: string, refresh?: boolean) => {
    setActiveTab('forecast')
    setLastQuery({ source, query, horizon, resample: resample || '' })
    setLastApply(apply || '')
    setSelectedModel('')
    loadData(source, query, horizon, start, end, resample, apply, anomalyMethod, refresh)
  }

  const handleLoadView = (view: SavedViewResponse) => {
    setActiveTab('forecast')
    setQueryPrefill({
      source: view.source,
      query: view.query,
      horizon: view.horizon,
      start: view.start ?? undefined,
      end: view.end ?? undefined,
      resample: view.resample ?? undefined,
      apply: view.apply ?? undefined,
    })
    handleSubmit(
      view.source,
      view.query,
      view.horizon,
      view.start ?? undefined,
      view.end ?? undefined,
      view.resample ?? undefined,
      view.apply ?? undefined,
    )
  }

  const handleNlExplore = (source: string, query: string, horizon: number, start?: string, end?: string, resample?: string, apply?: string) => {
    setQueryPrefill({ source, query, horizon, start, end, resample, apply })
    handleSubmit(source, query, horizon, start, end, resample, apply)
  }

  const handleCompare = async (items: CompareItem[], resample?: string, apply?: string) => {
    setCompareLoading(true)
    setCompareError(null)
    setCompareSeries(null)
    setCompareAnalyses(null)
    setCompareResample(resample || '')
    setCompareApply(apply || '')
    setCompareItems(items)
    try {
      const result = await fetchCompare(items, resample, apply)
      setCompareSeries(result.series)
      setCompareAnalyses(result.analyses ?? null)
    } catch (err) {
      setCompareError(err instanceof Error ? err.message : String(err))
    } finally {
      setCompareLoading(false)
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

  const effectiveModel =
    selectedModel || forecast?.recommended_model || ''

  const hasData = series && analysis && forecast

  return (
    <Box>
      <NaturalQueryInput
        loading={loading || compareLoading}
        onResult={handleNlExplore}
        onCompareResult={handleNlCompare}
      />

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={activeTab}
          onChange={(_, v) => setActiveTab(v)}
        >
          <Tab value="forecast" label="Forecast" />
          <Tab value="compare" label="Compare" />
          <Tab value="correlate" label="Correlate" />
        </Tabs>
        <Box sx={{ pb: 1 }}>
          <ViewsDropdown onLoadView={handleLoadView} />
        </Box>
      </Box>

      {activeTab === 'forecast' && (
        <>
          <Divider sx={{ my: 2 }}>
            <Typography variant="caption" color="text.secondary">
              or use the form
            </Typography>
          </Divider>

          <QueryForm
            sources={sources}
            loading={loading}
            onSubmit={handleSubmit}
            prefill={queryPrefill}
          />

          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          {loading && (
            <Box sx={{ textAlign: 'center', py: 6 }}>
              <CircularProgress size={32} />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                Fetching data and running analysis...
              </Typography>
            </Box>
          )}

          {hasData && (
            <>
              <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <ModelSelector
                  forecast={forecast}
                  selected={effectiveModel}
                  onChange={setSelectedModel}
                />
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <ExportPdfButton
                    source={lastQuery.source}
                    query={lastQuery.query}
                    horizon={lastQuery.horizon}
                    resample={lastQuery.resample || undefined}
                    apply={lastApply || undefined}
                  />
                  <SaveViewButton
                    source={lastQuery.source}
                    query={lastQuery.query}
                    horizon={lastQuery.horizon}
                    resample={lastQuery.resample || undefined}
                    apply={lastApply || undefined}
                    anomalyMethod={anomalyMethod}
                  />
                </Box>
              </Box>

              <Grid container spacing={3}>
                <Grid size={{ xs: 12, lg: 8 }}>
                  <ForecastChart
                    series={series}
                    forecast={forecast}
                    selectedModel={effectiveModel}
                    analysis={analysis}
                    showBreaks={showBreaks}
                    showAnomalies={showAnomalies}
                    resample={lastQuery.resample}
                  />
                  <Box sx={{ mt: 1, display: 'flex', gap: 2, alignItems: 'center' }}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          size="small"
                          checked={showBreaks}
                          onChange={(e) => setShowBreaks(e.target.checked)}
                        />
                      }
                      label={<Typography variant="body2">Structural breaks</Typography>}
                    />
                    <FormControlLabel
                      control={
                        <Checkbox
                          size="small"
                          checked={showAnomalies}
                          onChange={(e) => setShowAnomalies(e.target.checked)}
                        />
                      }
                      label={<Typography variant="body2">Anomalies</Typography>}
                    />
                    <FormControl size="small" sx={{ minWidth: 110 }}>
                      <InputLabel>Anomaly method</InputLabel>
                      <Select
                        value={anomalyMethod}
                        label="Anomaly method"
                        onChange={(e) => setAnomalyMethod(e.target.value)}
                      >
                        <MenuItem value="zscore">Z-score</MenuItem>
                        <MenuItem value="iqr">IQR</MenuItem>
                      </Select>
                    </FormControl>
                  </Box>
                  <Box sx={{ mt: 2 }}>
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
                </Grid>

                <Grid size={{ xs: 12, lg: 4 }}>
                  <AnalysisPanel analysis={analysis} />
                  {lastQuery.source && lastQuery.query && (
                    <Box sx={{ mt: 3 }}>
                      <InsightPanel
                        source={lastQuery.source}
                        query={lastQuery.query}
                        horizon={lastQuery.horizon}
                        series={series}
                        analysis={analysis}
                        forecast={forecast}
                      />
                    </Box>
                  )}
                </Grid>
              </Grid>
            </>
          )}

          {!hasData && !loading && !error && (
            <Grid container spacing={3}>
              <Grid size={{ xs: 12, md: 8 }}>
                <Box sx={{ textAlign: 'center', py: 8 }}>
                  <Typography variant="body1" color="text.secondary" gutterBottom>
                    Select a data source and enter a query to get started
                  </Typography>
                  <Typography variant="body2" color="text.disabled">
                    Try PyPI with "fastapi" or Crypto with "bitcoin"
                  </Typography>
                </Box>
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <InsightsFeed
                  onSelectInsight={(source, query) => handleSubmit(source, query, 14)}
                />
                <Box sx={{ mt: 2 }}>
                  <WatchlistPanel
                    sources={sources}
                    onLoadQuery={(source, query) => handleSubmit(source, query, 14)}
                  />
                </Box>
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

          {compareError && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {compareError}
            </Alert>
          )}

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
                  <CompareChart seriesList={compareSeries} resample={compareResample} />
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
        </>
      )}

      {activeTab === 'correlate' && (
        <CorrelateTab sources={sources} />
      )}
    </Box>
  )
}
