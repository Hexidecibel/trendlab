import { useRef } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Typography from '@mui/material/Typography'
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap'
import { Line } from 'react-chartjs-2'
import type { ChartJS } from 'chart.js'
import type { TimeSeries } from '../../api/types'

const COLORS = ['#3b82f6', '#f97316', '#10b981']

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

// Map resample frequency to Chart.js time unit
type TimeUnit = 'day' | 'week' | 'month' | 'quarter' | 'year'
function getTimeUnit(resample?: string): TimeUnit {
  switch (resample) {
    case 'week': return 'week'
    case 'month': return 'month'
    case 'quarter': return 'quarter'
    case 'season': return 'quarter'
    case 'year': return 'year'
    default: return 'day'
  }
}

interface Props {
  seriesList: TimeSeries[]
  resample?: string
}

export function CompareChart({ seriesList, resample }: Props) {
  const chartRef = useRef<ChartJS<'line'>>(null)

  const handleResetZoom = () => {
    chartRef.current?.resetZoom()
  }

  if (seriesList.length === 0) return null

  const datasets = seriesList.map((s, i) => ({
    label: getFriendlyLabel(s),
    data: s.points.map((p) => ({ x: p.date, y: p.value })),
    borderColor: COLORS[i % COLORS.length],
    backgroundColor: COLORS[i % COLORS.length],
    pointRadius: 0,
    borderWidth: 2,
  }))

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    scales: {
      x: {
        type: 'time' as const,
        time: { unit: getTimeUnit(resample) },
        title: { display: true, text: 'Date' },
      },
      y: {
        title: { display: true, text: 'Value' },
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
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle2">
            Series Comparison
          </Typography>
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
        <Box sx={{ height: 400 }}>
          <Line ref={chartRef} data={{ datasets }} options={options} />
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          Tip: Drag to select a region to zoom in
        </Typography>
      </CardContent>
    </Card>
  )
}
