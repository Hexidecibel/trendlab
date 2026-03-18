import { useState, useRef } from 'react'
import Autocomplete from '@mui/material/Autocomplete'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CircularProgress from '@mui/material/CircularProgress'
import FormControl from '@mui/material/FormControl'
import Grid from '@mui/material/Grid'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import Select from '@mui/material/Select'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import DownloadIcon from '@mui/icons-material/Download'
import { Scatter, Bar } from 'react-chartjs-2'
import type { ChartJS } from 'chart.js'
import {
  Chart as ChartJSClass,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  CategoryScale,
  Tooltip,
  Legend,
} from 'chart.js'
import type { CorrelateResponse, DataSourceInfo, LookupItem } from '../api/types'
import { ApiError, fetchCorrelate, fetchLookup } from '../api/client'
import { ErrorAlert } from './ErrorAlert'

// Register Chart.js components
ChartJSClass.register(LinearScale, PointElement, LineElement, BarElement, CategoryScale, Tooltip, Legend)

interface SeriesInput {
  source: string
  query: string
}

interface Props {
  sources: DataSourceInfo[]
}

export function CorrelateTab({ sources }: Props) {
  const [seriesA, setSeriesA] = useState<SeriesInput>({ source: '', query: '' })
  const [seriesB, setSeriesB] = useState<SeriesInput>({ source: '', query: '' })
  const [resample, setResample] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | ApiError | null>(null)
  const [result, setResult] = useState<CorrelateResponse | null>(null)
  const [lookupA, setLookupA] = useState<LookupItem[]>([])
  const [lookupB, setLookupB] = useState<LookupItem[]>([])
  const scatterChartRef = useRef<ChartJS<'scatter'>>(null)
  const lagChartRef = useRef<ChartJS<'bar'>>(null)

  const loadLookup = async (source: string, setLookup: (items: LookupItem[]) => void) => {
    if (!source) {
      setLookup([])
      return
    }
    try {
      const items = await fetchLookup(source, 'query')
      setLookup(items)
    } catch {
      setLookup([])
    }
  }

  const handleSourceAChange = (source: string) => {
    setSeriesA({ source, query: '' })
    loadLookup(source, setLookupA)
  }

  const handleSourceBChange = (source: string) => {
    setSeriesB({ source, query: '' })
    loadLookup(source, setLookupB)
  }

  const handleSubmit = async () => {
    if (!seriesA.source || !seriesA.query || !seriesB.source || !seriesB.query) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await fetchCorrelate({
        series_a: { source: seriesA.source, query: seriesA.query },
        series_b: { source: seriesB.source, query: seriesB.query },
        resample: resample || undefined,
      })
      setResult(response)
    } catch (err) {
      setError(err instanceof ApiError ? err : err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadScatter = () => {
    const chart = scatterChartRef.current
    if (!chart) return
    const url = chart.toBase64Image()
    const link = document.createElement('a')
    link.download = `correlation-scatter-${seriesA.query}-vs-${seriesB.query}.png`
    link.href = url
    link.click()
  }

  const handleDownloadLag = () => {
    const chart = lagChartRef.current
    if (!chart) return
    const url = chart.toBase64Image()
    const link = document.createElement('a')
    link.download = `correlation-lag-${seriesA.query}-vs-${seriesB.query}.png`
    link.href = url
    link.click()
  }

  const isComplete = seriesA.source && seriesA.query && seriesB.source && seriesB.query

  const getSourceFormType = (sourceName: string): 'text' | 'autocomplete' => {
    const source = sources.find(s => s.name === sourceName)
    if (!source) return 'text'
    const field = source.form_fields.find(f => f.name === 'query')
    return field?.field_type === 'autocomplete' ? 'autocomplete' : 'text'
  }

  const renderSeriesInput = (
    label: string,
    series: SeriesInput,
    setSeries: (s: SeriesInput) => void,
    lookup: LookupItem[],
    onSourceChange: (source: string) => void,
  ) => {
    const formType = getSourceFormType(series.source)

    return (
      <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <Typography variant="subtitle2" sx={{ minWidth: 80 }}>{label}:</Typography>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Source</InputLabel>
          <Select
            value={series.source}
            label="Source"
            onChange={(e) => onSourceChange(e.target.value)}
          >
            {sources.map((s) => (
              <MenuItem key={s.name} value={s.name}>{s.name}</MenuItem>
            ))}
          </Select>
        </FormControl>

        {formType === 'autocomplete' ? (
          <Autocomplete
            size="small"
            sx={{ minWidth: 200 }}
            options={lookup}
            getOptionLabel={(opt) => opt.label}
            value={lookup.find(l => l.value === series.query) || null}
            onChange={(_e, newValue) => setSeries({ ...series, query: newValue?.value || '' })}
            disabled={!series.source}
            renderInput={(params) => (
              <TextField {...params} label="Query" placeholder="Select..." />
            )}
          />
        ) : (
          <TextField
            size="small"
            label="Query"
            value={series.query}
            onChange={(e) => setSeries({ ...series, query: e.target.value })}
            disabled={!series.source}
            placeholder="e.g., fastapi"
            sx={{ minWidth: 200 }}
          />
        )}
      </Box>
    )
  }

  return (
    <Box>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="subtitle1" gutterBottom>
            Correlation Analysis
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Compare two time series to find statistical correlations
          </Typography>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {renderSeriesInput('Series A', seriesA, setSeriesA, lookupA, handleSourceAChange)}
            {renderSeriesInput('Series B', seriesB, setSeriesB, lookupB, handleSourceBChange)}

            <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-end' }}>
              <FormControl size="small" sx={{ minWidth: 130 }}>
                <InputLabel>Resample</InputLabel>
                <Select
                  value={resample}
                  label="Resample"
                  onChange={(e) => setResample(e.target.value)}
                >
                  <MenuItem value="">None</MenuItem>
                  <MenuItem value="week">Weekly</MenuItem>
                  <MenuItem value="month">Monthly</MenuItem>
                  <MenuItem value="quarter">Quarterly</MenuItem>
                  <MenuItem value="year">Yearly</MenuItem>
                  {/* Show custom resample periods from selected sources */}
                  {Array.from(new Set(
                    [seriesA.source, seriesB.source]
                      .map(src => sources.find(s => s.name === src))
                      .filter(Boolean)
                      .flatMap(s => s?.resample_periods || [])
                      .map(p => JSON.stringify(p))
                  )).map(json => {
                    const p = JSON.parse(json)
                    return <MenuItem key={p.value} value={p.value}>{p.label}</MenuItem>
                  })}
                </Select>
              </FormControl>

              <Button
                variant="contained"
                onClick={handleSubmit}
                disabled={loading || !isComplete}
              >
                {loading ? 'Analyzing...' : 'Analyze Correlation'}
              </Button>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {error && <ErrorAlert error={error} />}

      {loading && (
        <Box sx={{ textAlign: 'center', py: 6 }}>
          <CircularProgress size={32} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Computing correlation...
          </Typography>
        </Box>
      )}

      {result && !loading && (
        <Grid container spacing={3}>
          {/* Stats Card */}
          <Grid size={{ xs: 12, md: 4 }}>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>
                  Correlation Statistics
                </Typography>
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    Aligned Data Points
                  </Typography>
                  <Typography variant="h6">{result.aligned_points}</Typography>
                </Box>
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    Pearson Correlation (r)
                  </Typography>
                  <Typography
                    variant="h5"
                    sx={{
                      color: Math.abs(result.pearson.r) > 0.5 ? 'success.main' : 'text.primary',
                    }}
                  >
                    {result.pearson.r.toFixed(4)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    p-value: {result.pearson.p_value < 0.001 ? '<0.001' : result.pearson.p_value.toFixed(4)}
                  </Typography>
                </Box>
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    Spearman Correlation
                  </Typography>
                  <Typography
                    variant="h5"
                    sx={{
                      color: Math.abs(result.spearman.r) > 0.5 ? 'success.main' : 'text.primary',
                    }}
                  >
                    {result.spearman.r.toFixed(4)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    p-value: {result.spearman.p_value < 0.001 ? '<0.001' : result.spearman.p_value.toFixed(4)}
                  </Typography>
                </Box>
                <Box sx={{ mt: 3, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                  <Typography variant="caption">
                    {Math.abs(result.pearson.r) > 0.7 && 'Strong correlation detected. '}
                    {Math.abs(result.pearson.r) > 0.3 && Math.abs(result.pearson.r) <= 0.7 && 'Moderate correlation detected. '}
                    {Math.abs(result.pearson.r) <= 0.3 && 'Weak or no correlation. '}
                    {result.pearson.p_value < 0.05 ? 'Statistically significant.' : 'Not statistically significant.'}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Scatter Plot */}
          <Grid size={{ xs: 12, md: 8 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="subtitle2">
                    Scatter Plot
                  </Typography>
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<DownloadIcon />}
                    onClick={handleDownloadScatter}
                    sx={{ textTransform: 'none', fontSize: '0.75rem' }}
                  >
                    PNG
                  </Button>
                </Box>
                <Box sx={{ height: 300 }}>
                  <Scatter
                    ref={scatterChartRef}
                    data={{
                      datasets: [{
                        label: `${result.series_a_label} vs ${result.series_b_label}`,
                        data: result.scatter,
                        backgroundColor: 'rgba(59, 130, 246, 0.5)',
                        borderColor: '#3b82f6',
                      }],
                    }}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      scales: {
                        x: { title: { display: true, text: result.series_a_label } },
                        y: { title: { display: true, text: result.series_b_label } },
                      },
                    }}
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Lag Correlation Chart */}
          <Grid size={{ xs: 12 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="subtitle2">
                    Lag Correlation Analysis
                  </Typography>
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<DownloadIcon />}
                    onClick={handleDownloadLag}
                    sx={{ textTransform: 'none', fontSize: '0.75rem' }}
                  >
                    PNG
                  </Button>
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                  Shows correlation at different time offsets (positive lag = Series B leads Series A)
                </Typography>
                <Box sx={{ height: 250 }}>
                  <Bar
                    ref={lagChartRef}
                    data={{
                      labels: result.lag_analysis.map(l => `${l.lag > 0 ? '+' : ''}${l.lag}d`),
                      datasets: [{
                        label: 'Correlation',
                        data: result.lag_analysis.map(l => l.correlation),
                        backgroundColor: result.lag_analysis.map(l =>
                          l.correlation >= 0 ? 'rgba(16, 185, 129, 0.7)' : 'rgba(239, 68, 68, 0.7)'
                        ),
                        borderColor: result.lag_analysis.map(l =>
                          l.correlation >= 0 ? '#10b981' : '#ef4444'
                        ),
                        borderWidth: 1,
                      }],
                    }}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      scales: {
                        y: {
                          min: -1,
                          max: 1,
                          title: { display: true, text: 'Correlation' },
                        },
                        x: {
                          title: { display: true, text: 'Lag (days)' },
                        },
                      },
                      plugins: {
                        legend: { display: false },
                      },
                    }}
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {!result && !loading && !error && (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Typography variant="body1" color="text.secondary" gutterBottom>
            Select two series to analyze their correlation
          </Typography>
          <Typography variant="body2" color="text.disabled">
            Try comparing "bitcoin" (crypto) with "web3" (PyPI)
          </Typography>
        </Box>
      )}
    </Box>
  )
}
