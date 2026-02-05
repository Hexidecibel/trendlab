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
import type { CompareItem, NaturalCompareItem, TimeSeries } from '../api/types'
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

export function Dashboard() {
  const { sources, series, analysis, forecast, loading, error, loadData } =
    useApi()
  const [selectedModel, setSelectedModel] = useState('')
  const [lastQuery, setLastQuery] = useState({ source: '', query: '', horizon: 14 })
  const [showBreaks, setShowBreaks] = useState(true)
  const [showAnomalies, setShowAnomalies] = useState(true)

  const [activeTab, setActiveTab] = useState<'explore' | 'compare'>('explore')
  const [compareSeries, setCompareSeries] = useState<TimeSeries[] | null>(null)
  const [compareLoading, setCompareLoading] = useState(false)
  const [compareError, setCompareError] = useState<string | null>(null)
  const [anomalyMethod, setAnomalyMethod] = useState('zscore')
  const [queryPrefill, setQueryPrefill] = useState<QueryPrefill | null>(null)
  const [comparePrefill, setComparePrefill] = useState<ComparePrefill | null>(null)

  const handleSubmit = (source: string, query: string, horizon: number, start?: string, end?: string, resample?: string, apply?: string, refresh?: boolean) => {
    setActiveTab('explore')
    setLastQuery({ source, query, horizon })
    setSelectedModel('')
    loadData(source, query, horizon, start, end, resample, apply, anomalyMethod, refresh)
  }

  const handleNlExplore = (source: string, query: string, horizon: number, start?: string, end?: string, resample?: string, apply?: string) => {
    setQueryPrefill({ source, query, horizon, start, end, resample, apply })
    handleSubmit(source, query, horizon, start, end, resample, apply)
  }

  const handleCompare = async (items: CompareItem[], resample?: string, apply?: string) => {
    setCompareLoading(true)
    setCompareError(null)
    setCompareSeries(null)
    try {
      const result = await fetchCompare(items, resample, apply)
      setCompareSeries(result.series)
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
    handleCompare(compareItems, resample)
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

      <Tabs
        value={activeTab}
        onChange={(_, v) => setActiveTab(v)}
        sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
      >
        <Tab value="explore" label="Explore" />
        <Tab value="compare" label="Compare" />
      </Tabs>

      {activeTab === 'explore' && (
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
              <Box sx={{ mb: 2 }}>
                <ModelSelector
                  forecast={forecast}
                  selected={effectiveModel}
                  onChange={setSelectedModel}
                />
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
                </Grid>

                <Grid size={{ xs: 12, lg: 4 }}>
                  <AnalysisPanel analysis={analysis} />
                  {lastQuery.source && lastQuery.query && (
                    <Box sx={{ mt: 3 }}>
                      <InsightPanel
                        source={lastQuery.source}
                        query={lastQuery.query}
                        horizon={lastQuery.horizon}
                      />
                    </Box>
                  )}
                </Grid>
              </Grid>
            </>
          )}

          {!hasData && !loading && !error && (
            <Box sx={{ textAlign: 'center', py: 8 }}>
              <Typography variant="body1" color="text.secondary" gutterBottom>
                Select a data source and enter a query to get started
              </Typography>
              <Typography variant="body2" color="text.disabled">
                Try PyPI with "fastapi" or Crypto with "bitcoin"
              </Typography>
            </Box>
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
            <CompareChart seriesList={compareSeries} />
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
    </Box>
  )
}
