import { useState, useRef } from 'react'
import Autocomplete from '@mui/material/Autocomplete'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Checkbox from '@mui/material/Checkbox'
import CircularProgress from '@mui/material/CircularProgress'
import FormControl from '@mui/material/FormControl'
import FormControlLabel from '@mui/material/FormControlLabel'
import Grid from '@mui/material/Grid'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import Select from '@mui/material/Select'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import DownloadIcon from '@mui/icons-material/Download'
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap'
import { Line } from 'react-chartjs-2'
import type { ChartJS } from 'chart.js'
import type { CohortResponse, DataSourceInfo, LookupItem } from '../api/types'
import { ApiError, fetchCohort, fetchLookup } from '../api/client'
import { ErrorAlert } from './ErrorAlert'

const COLORS = [
  '#3b82f6', '#f97316', '#10b981', '#ef4444', '#8b5cf6',
  '#06b6d4', '#f59e0b', '#ec4899', '#14b8a6', '#6366f1',
  '#84cc16', '#f43f5e', '#22d3ee', '#a855f7', '#fb923c',
  '#2dd4bf', '#e879f9', '#4ade80', '#f87171', '#38bdf8',
]

interface Props {
  sources: DataSourceInfo[]
}

export function CohortPanel({ sources }: Props) {
  const [source, setSource] = useState('')
  const [queriesText, setQueriesText] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [normalize, setNormalize] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | ApiError | null>(null)
  const [result, setResult] = useState<CohortResponse | null>(null)
  const [lookup, setLookup] = useState<LookupItem[]>([])
  const chartRef = useRef<ChartJS<'line'>>(null)

  const loadLookup = async (src: string) => {
    if (!src) {
      setLookup([])
      return
    }
    try {
      const items = await fetchLookup(src, 'query')
      setLookup(items)
    } catch {
      setLookup([])
    }
  }

  const handleSourceChange = (src: string) => {
    setSource(src)
    setQueriesText('')
    loadLookup(src)
  }

  const getSourceFormType = (): 'text' | 'autocomplete' => {
    const s = sources.find(s => s.name === source)
    if (!s) return 'text'
    const field = s.form_fields.find(f => f.name === 'query')
    return field?.field_type === 'autocomplete' ? 'autocomplete' : 'text'
  }

  const parseQueries = (): string[] => {
    return queriesText
      .split(/[,\n]/)
      .map(q => q.trim())
      .filter(q => q.length > 0)
  }

  const handleSubmit = async () => {
    const queries = parseQueries()
    if (!source || queries.length < 2) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await fetchCohort({
        source,
        queries,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        normalize,
      })
      setResult(response)
    } catch (err) {
      setError(err instanceof ApiError ? err : err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  const handleResetZoom = () => {
    chartRef.current?.resetZoom()
  }

  const handleDownloadPng = () => {
    const chart = chartRef.current
    if (!chart) return
    const url = chart.toBase64Image()
    const link = document.createElement('a')
    link.download = `cohort-${source}.png`
    link.href = url
    link.click()
  }

  const queries = parseQueries()
  const isValid = source && queries.length >= 2
  const formType = getSourceFormType()

  return (
    <Box>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="subtitle1" gutterBottom>
            Cohort Comparison
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Compare multiple series from the same source, normalized and ranked by performance
          </Typography>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Source</InputLabel>
              <Select
                value={source}
                label="Source"
                onChange={(e) => handleSourceChange(e.target.value)}
              >
                {sources.map((s) => (
                  <MenuItem key={s.name} value={s.name}>{s.name}</MenuItem>
                ))}
              </Select>
            </FormControl>

            {formType === 'autocomplete' ? (
              <Autocomplete
                multiple
                size="small"
                options={lookup}
                getOptionLabel={(opt) => opt.label}
                value={lookup.filter(l => queries.includes(l.value))}
                onChange={(_e, newValue) => {
                  setQueriesText(newValue.map(v => v.value).join(', '))
                }}
                disabled={!source}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Queries"
                    placeholder="Select items to compare..."
                  />
                )}
              />
            ) : (
              <TextField
                size="small"
                label="Queries (comma or newline separated)"
                value={queriesText}
                onChange={(e) => setQueriesText(e.target.value)}
                disabled={!source}
                placeholder="e.g., bitcoin, ethereum, solana"
                multiline
                minRows={2}
                maxRows={6}
                helperText={queries.length > 0 ? `${queries.length} queries` : undefined}
              />
            )}

            <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <TextField
                size="small"
                label="Start date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                sx={{ width: 160 }}
              />
              <TextField
                size="small"
                label="End date"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                sx={{ width: 160 }}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    size="small"
                    checked={normalize}
                    onChange={(e) => setNormalize(e.target.checked)}
                  />
                }
                label={<Typography variant="body2">Normalize</Typography>}
              />
              <Button
                variant="contained"
                onClick={handleSubmit}
                disabled={loading || !isValid}
              >
                {loading ? 'Comparing...' : 'Compare Cohort'}
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
            Fetching and analyzing cohort...
          </Typography>
        </Box>
      )}

      {result && !loading && (
        <Grid container spacing={3}>
          {/* Normalized line chart */}
          <Grid size={{ xs: 12, lg: 8 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="subtitle2">
                    {normalize ? 'Normalized Performance (% change from day 1)' : 'Raw Values'}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<DownloadIcon />}
                      onClick={handleDownloadPng}
                      sx={{ textTransform: 'none', fontSize: '0.75rem' }}
                    >
                      PNG
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<ZoomOutMapIcon />}
                      onClick={handleResetZoom}
                      sx={{ textTransform: 'none', fontSize: '0.75rem' }}
                    >
                      Reset Zoom
                    </Button>
                  </Box>
                </Box>
                <Box sx={{ height: 400 }}>
                  <Line
                    ref={chartRef}
                    data={{
                      datasets: result.members.map((m, i) => ({
                        label: m.query,
                        data: m.normalized_points.map((p) => ({ x: p.date, y: p.value })),
                        borderColor: COLORS[i % COLORS.length],
                        backgroundColor: COLORS[i % COLORS.length],
                        pointRadius: 0,
                        borderWidth: 2,
                      })),
                    }}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      interaction: {
                        mode: 'index' as const,
                        intersect: false,
                      },
                      scales: {
                        x: {
                          type: 'time' as const,
                          time: { unit: 'day' },
                          title: { display: true, text: 'Date' },
                        },
                        y: {
                          title: {
                            display: true,
                            text: normalize ? '% Change' : 'Value',
                          },
                        },
                      },
                      plugins: {
                        zoom: {
                          zoom: {
                            drag: { enabled: true },
                            mode: 'x' as const,
                          },
                        },
                      },
                    }}
                  />
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  Tip: Drag to select a region to zoom in
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          {/* Ranking table */}
          <Grid size={{ xs: 12, lg: 4 }}>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>
                  Cohort Rankings
                </Typography>
                {result.period_start && result.period_end && (
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                    Period: {result.period_start} to {result.period_end}
                  </Typography>
                )}
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>#</TableCell>
                        <TableCell>Query</TableCell>
                        <TableCell align="right">Return %</TableCell>
                        <TableCell align="right">Drawdown %</TableCell>
                        <TableCell align="right">Volatility</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {result.members.map((m) => (
                        <TableRow key={m.query}>
                          <TableCell>{m.rank}</TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Box
                                sx={{
                                  width: 10,
                                  height: 10,
                                  borderRadius: '50%',
                                  bgcolor: COLORS[(m.rank - 1) % COLORS.length],
                                  flexShrink: 0,
                                }}
                              />
                              {m.query}
                            </Box>
                          </TableCell>
                          <TableCell
                            align="right"
                            sx={{
                              color: m.total_return >= 0 ? 'success.main' : 'error.main',
                              fontWeight: 600,
                            }}
                          >
                            {m.total_return >= 0 ? '+' : ''}{m.total_return.toFixed(2)}%
                          </TableCell>
                          <TableCell
                            align="right"
                            sx={{ color: 'error.main' }}
                          >
                            {m.max_drawdown.toFixed(2)}%
                          </TableCell>
                          <TableCell align="right">
                            {m.volatility.toFixed(2)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {!result && !loading && !error && (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Typography variant="body1" color="text.secondary" gutterBottom>
            Enter multiple queries to compare as a cohort
          </Typography>
          <Typography variant="body2" color="text.disabled">
            Try crypto with "bitcoin, ethereum, solana" or PyPI with "fastapi, django, flask"
          </Typography>
        </Box>
      )}
    </Box>
  )
}
