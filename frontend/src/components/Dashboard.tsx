import { useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import FormControlLabel from '@mui/material/FormControlLabel'
import Checkbox from '@mui/material/Checkbox'
import Grid from '@mui/material/Grid'
import Typography from '@mui/material/Typography'
import { useApi } from '../hooks/useApi'
import { NaturalQueryInput } from './NaturalQueryInput'
import { QueryForm } from './QueryForm'
import { ForecastChart } from './charts/ForecastChart'
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

  const handleSubmit = (source: string, query: string, horizon: number, start?: string, end?: string) => {
    setLastQuery({ source, query, horizon })
    setSelectedModel('')
    loadData(source, query, horizon, start, end)
  }

  const effectiveModel =
    selectedModel || forecast?.recommended_model || ''

  const hasData = series && analysis && forecast

  return (
    <Box>
      <NaturalQueryInput loading={loading} onResult={handleSubmit} />

      <Divider sx={{ my: 3 }}>
        <Typography variant="caption" color="text.secondary">
          or use the form
        </Typography>
      </Divider>

      <QueryForm
        sources={sources}
        loading={loading}
        onSubmit={handleSubmit}
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
              <Box sx={{ mt: 1, display: 'flex', gap: 2 }}>
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
    </Box>
  )
}
