import { useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Collapse from '@mui/material/Collapse'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import { Line } from 'react-chartjs-2'
import { ApiError, fetchCausalImpact } from '../api/client'
import type { CausalImpactResponse } from '../api/types'
import { ErrorAlert } from './ErrorAlert'

interface Props {
  source: string
  query: string
  resample?: string
  apply?: string
}

export function CausalImpactPanel({ source, query, resample, apply }: Props) {
  const [eventDate, setEventDate] = useState('')
  const [result, setResult] = useState<CausalImpactResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | ApiError | null>(null)
  const [expanded, setExpanded] = useState(false)

  const handleAnalyze = async () => {
    if (!eventDate) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await fetchCausalImpact(source, query, eventDate, {
        resample,
        apply,
      })
      setResult(data)
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err
          : err instanceof Error
            ? err.message
            : String(err),
      )
    } finally {
      setLoading(false)
    }
  }

  const chartData = result
    ? {
        datasets: [
          {
            label: 'Actual',
            data: result.pointwise.map((p) => ({ x: p.date, y: p.actual })),
            borderColor: '#3b82f6',
            backgroundColor: '#3b82f6',
            pointRadius: 0,
            borderWidth: 2,
          },
          {
            label: 'Counterfactual',
            data: result.pointwise.map((p) => ({
              x: p.date,
              y: p.predicted,
            })),
            borderColor: '#f97316',
            backgroundColor: '#f97316',
            borderDash: [5, 5],
            pointRadius: 0,
            borderWidth: 2,
          },
          {
            label: '95% CI Upper',
            data: result.pointwise.map((p) => ({
              x: p.date,
              y: p.upper_ci,
            })),
            borderColor: 'transparent',
            backgroundColor: 'transparent',
            pointRadius: 0,
            borderWidth: 0,
          },
          {
            label: '95% CI Lower',
            data: result.pointwise.map((p) => ({
              x: p.date,
              y: p.lower_ci,
            })),
            borderColor: 'transparent',
            backgroundColor: 'rgba(249, 115, 22, 0.1)',
            pointRadius: 0,
            borderWidth: 0,
            fill: '-1',
          },
        ],
      }
    : null

  const chartOptions = result
    ? {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index' as const,
          intersect: false,
        },
        scales: {
          x: {
            type: 'time' as const,
            time: { unit: 'day' as const },
            title: { display: true, text: 'Date' },
          },
          y: {
            title: { display: true, text: 'Value' },
          },
        },
        plugins: {
          legend: {
            labels: {
              filter: (item: { text: string }) =>
                !item.text.startsWith('95% CI'),
            },
          },
          annotation: {
            annotations: {
              eventLine: {
                type: 'line' as const,
                xMin: result.event_date,
                xMax: result.event_date,
                borderColor: 'rgba(239, 68, 68, 0.8)',
                borderWidth: 2,
                borderDash: [6, 4],
                label: {
                  display: true,
                  content: 'Event',
                  position: 'start' as const,
                  backgroundColor: 'rgba(239, 68, 68, 0.8)',
                  color: '#fff',
                  font: { size: 10 },
                },
              },
            },
          },
        },
      }
    : null

  return (
    <Card sx={{ mt: 2 }}>
      <CardContent>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'pointer',
          }}
          onClick={() => setExpanded(!expanded)}
        >
          <Typography variant="subtitle2">Causal Impact Analysis</Typography>
          {expanded ? (
            <ExpandLessIcon fontSize="small" />
          ) : (
            <ExpandMoreIcon fontSize="small" />
          )}
        </Box>

        <Collapse in={expanded}>
          <Box sx={{ mt: 2, display: 'flex', gap: 2, alignItems: 'flex-end' }}>
            <TextField
              label="Event date"
              type="date"
              size="small"
              value={eventDate}
              onChange={(e) => setEventDate(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              sx={{ width: 180 }}
            />
            <Button
              variant="contained"
              size="small"
              onClick={handleAnalyze}
              disabled={!eventDate || loading}
              sx={{ textTransform: 'none' }}
            >
              {loading ? (
                <CircularProgress size={16} sx={{ mr: 1 }} />
              ) : null}
              Analyze Impact
            </Button>
          </Box>

          {error && (
            <Box sx={{ mt: 2 }}>
              <ErrorAlert error={error} />
            </Box>
          )}

          {result && (
            <Box sx={{ mt: 2 }}>
              <Box
                sx={{
                  display: 'flex',
                  gap: 2,
                  flexWrap: 'wrap',
                  mb: 2,
                }}
              >
                <Chip
                  label={`Cumulative: ${result.cumulative_impact >= 0 ? '+' : ''}${result.cumulative_impact.toFixed(2)}`}
                  color={result.cumulative_impact >= 0 ? 'success' : 'error'}
                  variant="outlined"
                  size="small"
                />
                <Chip
                  label={`Relative: ${result.relative_impact_pct >= 0 ? '+' : ''}${result.relative_impact_pct.toFixed(1)}%`}
                  color={result.relative_impact_pct >= 0 ? 'success' : 'error'}
                  variant="outlined"
                  size="small"
                />
                <Chip
                  label={`p-value: ${result.p_value.toFixed(4)}`}
                  variant="outlined"
                  size="small"
                />
                <Chip
                  label={result.significant ? 'Significant' : 'Not significant'}
                  color={result.significant ? 'success' : 'default'}
                  size="small"
                />
              </Box>

              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mb: 2 }}
              >
                {result.summary}
              </Typography>

              {chartData && chartOptions && (
                <Box sx={{ height: 280 }}>
                  <Line data={chartData} options={chartOptions} />
                </Box>
              )}

              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mt: 1, display: 'block' }}
              >
                Pre-period: {result.pre_period_length} points | Post-period:{' '}
                {result.post_period_length} points
              </Typography>
            </Box>
          )}
        </Collapse>
      </CardContent>
    </Card>
  )
}
