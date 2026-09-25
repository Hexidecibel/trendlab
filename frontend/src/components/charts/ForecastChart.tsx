import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import FormControlLabel from '@mui/material/FormControlLabel'
import IconButton from '@mui/material/IconButton'
import Switch from '@mui/material/Switch'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import { alpha, useTheme } from '@mui/material/styles'
import DownloadIcon from '@mui/icons-material/Download'
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap'
import { Line } from 'react-chartjs-2'
import type { Chart as ChartJS } from 'chart.js'
import { fetchEventContext } from '../../api/client'
import type { EventContext, TimeSeries, ForecastComparison, TrendAnalysis } from '../../api/types'
import { SmoothingControl } from '../SmoothingControl'
import { smoothedPoints } from '../../smoothing'
import type { SmoothingPreset } from '../../smoothing'

// Map resample frequency to Chart.js time unit
type TimeUnit = 'day' | 'week' | 'month' | 'quarter' | 'year'
function getTimeUnit(resample?: string): TimeUnit {
  switch (resample) {
    case 'week': return 'week'
    case 'month': return 'month'
    case 'quarter': return 'quarter'
    case 'year': return 'year'
    // Custom resample periods - use year for seasonal aggregations
    case 'mls_season': return 'year'
    case 'football_season': return 'year'
    case 'meteorological_season': return 'quarter'
    default: return 'day'
  }
}

// Get a human-readable label for the y-axis
function getYAxisLabel(series: TimeSeries): string {
  const meta = series.metadata as Record<string, unknown>
  // Try metric_label first, then metric, then fall back to Value
  return (meta.metric_label as string) || (meta.metric as string) || 'Value'
}

interface Props {
  series: TimeSeries
  forecast: ForecastComparison
  selectedModel: string
  analysis?: TrendAnalysis | null
  /** Legend label for the forecast line, e.g. "Forecast (auto · ets)". */
  forecastLabel?: string
  /** One toggle for regimes (bands), breaks (lines) and anomalies (points). */
  showAnnotations: boolean
  onShowAnnotationsChange: (show: boolean) => void
  resample?: string
  /** Extra header actions (e.g. Save View icon button). */
  actions?: ReactNode
  /** Trend smoothing preset; the control is hidden when the analysis has no smoothed data. */
  smoothing: SmoothingPreset
  onSmoothingChange: (preset: SmoothingPreset) => void
}

const REGIME_COLORS: Record<string, string> = {
  rising: 'rgba(34, 197, 94, 0.07)',
  falling: 'rgba(239, 68, 68, 0.07)',
  stable: 'rgba(156, 163, 175, 0.05)',
}

export function ForecastChart({
  series,
  forecast,
  selectedModel,
  analysis,
  forecastLabel,
  showAnnotations,
  onShowAnnotationsChange,
  resample,
  actions,
  smoothing,
  onSmoothingChange,
}: Props) {
  const theme = useTheme()
  const isDark = theme.palette.mode === 'dark'
  const showBreaks = showAnnotations
  const showAnomalies = showAnnotations
  const showRegimes = showAnnotations
  const chartRef = useRef<ChartJS<'line', { x: string; y: number }[]>>(null)
  const [eventMap, setEventMap] = useState<Record<string, EventContext>>({})

  // Fetch event context for anomaly dates
  useEffect(() => {
    if (!analysis || !showAnomalies || analysis.anomalies.anomalies.length === 0) {
      return
    }
    const dates = analysis.anomalies.anomalies.slice(0, 5).map((a) => a.date)
    fetchEventContext(analysis.source, analysis.query, dates)
      .then((events) => {
        const map: Record<string, EventContext> = {}
        for (const ev of events) {
          map[ev.date] = ev
        }
        setEventMap(map)
      })
      .catch(() => {
        // Best-effort: ignore failures
      })
  }, [analysis, showAnomalies])

  const handleResetZoom = () => {
    chartRef.current?.resetZoom()
  }

  const handleDownloadPng = () => {
    const chart = chartRef.current
    if (!chart) return
    const url = chart.toBase64Image()
    const link = document.createElement('a')
    link.download = `forecast-${series.source}-${series.query}.png`
    link.href = url
    link.click()
  }

  const modelForecast = forecast.forecasts.find(
    (f) => f.model_name === selectedModel,
  )
  if (!modelForecast) return null

  const actualData = series.points.map((p) => ({ x: p.date, y: p.value }))
  const hasSmoothed = !!analysis?.trend.smoothed
  const trendPoints = hasSmoothed ? smoothedPoints(analysis?.trend, smoothing) : null
  // Primary for the line the eye should follow; lighter shade on dark paper
  const primary = isDark ? theme.palette.primary.light : theme.palette.primary.main
  const rawColor = trendPoints ? alpha(primary, isDark ? 0.35 : 0.3) : primary
  const trendDataset = trendPoints
    ? [
        {
          label: smoothing === 'line' ? 'Trend line' : `Trend (${smoothing})`,
          data: trendPoints.map((p) => ({ x: p.date, y: p.value })),
          borderColor: primary,
          backgroundColor: primary,
          pointRadius: 0,
          borderWidth: 3,
          tension: 0,
          order: 0,
        },
      ]
    : []
  const forecastData = modelForecast.points.map((p) => ({
    x: p.date,
    y: p.value,
  }))
  const upperCI = modelForecast.points.map((p) => ({
    x: p.date,
    y: p.upper_ci,
  }))
  const lowerCI = modelForecast.points.map((p) => ({
    x: p.date,
    y: p.lower_ci,
  }))

  const data = {
    datasets: [
      ...trendDataset,
      {
        label: 'Actual',
        data: actualData,
        borderColor: rawColor,
        backgroundColor: rawColor,
        pointRadius: 0,
        borderWidth: trendPoints ? 1.25 : 2,
        order: 1,
      },
      {
        label: forecastLabel || `Forecast (${selectedModel})`,
        data: forecastData,
        borderColor: '#f97316',
        backgroundColor: '#f97316',
        borderDash: [5, 5],
        pointRadius: 0,
        borderWidth: 2,
      },
      {
        label: '95% CI Upper',
        data: upperCI,
        borderColor: 'transparent',
        backgroundColor: 'transparent',
        pointRadius: 0,
        borderWidth: 0,
      },
      {
        label: '95% CI Lower',
        data: lowerCI,
        borderColor: 'transparent',
        backgroundColor: 'rgba(249, 115, 22, 0.1)',
        pointRadius: 0,
        borderWidth: 0,
        fill: '-1',
      },
    ],
  }

  // Build annotation config from analysis data
  const annotations: Record<string, object> = {}

  if (analysis && showBreaks) {
    analysis.structural_breaks.forEach((brk, i) => {
      annotations[`break-${i}`] = {
        type: 'line',
        xMin: brk.date,
        xMax: brk.date,
        borderColor: 'rgba(239, 68, 68, 0.55)',
        borderWidth: 1.5,
        borderDash: [6, 4],
        label: {
          display: false,
          content: `Break · ${brk.date}`,
          position: 'start',
          backgroundColor: 'rgba(30, 30, 30, 0.9)',
          color: '#fff',
          font: { size: 10 },
        },
        enter({ element }: { element: { label: { options: { display: boolean } } } }) {
          element.label.options.display = true
          return true
        },
        leave({ element }: { element: { label: { options: { display: boolean } } } }) {
          element.label.options.display = false
          return true
        },
      }
    })
  }

  if (analysis && showAnomalies) {
    analysis.anomalies.anomalies.forEach((a, i) => {
      const ev = eventMap[a.date]
      const labelContent = ev
        ? [`Anomaly: ${a.value.toFixed(1)}`, ev.headline.slice(0, 60)]
        : [`Anomaly: ${a.value.toFixed(1)}`]
      annotations[`anomaly-${i}`] = {
        type: 'point',
        xValue: a.date,
        yValue: a.value,
        radius: 5,
        backgroundColor: 'rgba(239, 68, 68, 0.4)',
        borderColor: 'rgb(239, 68, 68)',
        borderWidth: 2,
        label: {
          display: false,
          content: labelContent,
          backgroundColor: 'rgba(30, 30, 30, 0.9)',
          color: '#fff',
          font: { size: 10 },
          padding: 4,
        },
        enter({ element }: { element: { label: { options: { display: boolean } } } }) {
          element.label.options.display = true
          return true
        },
        leave({ element }: { element: { label: { options: { display: boolean } } } }) {
          element.label.options.display = false
          return true
        },
      }
    })
  }

  if (analysis && showRegimes && analysis.regimes && analysis.regimes.length > 0) {
    analysis.regimes.forEach((regime, i) => {
      annotations[`regime-${i}`] = {
        type: 'box',
        xMin: regime.start_date,
        xMax: regime.end_date,
        backgroundColor: REGIME_COLORS[regime.label] || REGIME_COLORS.stable,
        borderWidth: 0,
        drawTime: 'beforeDatasetsDraw',
      }
    })
  }

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
        title: { display: true, text: getYAxisLabel(series) },
      },
    },
    plugins: {
      legend: {
        labels: {
          filter: (item: { text: string }) =>
            !item.text.startsWith('95% CI'),
        },
      },
      zoom: {
        zoom: {
          drag: { enabled: true },
          mode: 'x' as const,
        },
      },
      annotation: {
        annotations,
      },
    },
  }

  const iconSx = { p: 0.75 }

  return (
    <Card>
      <CardContent>
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 1,
            mb: 1,
          }}
        >
          <Typography variant="subtitle2">Time Series & Forecast</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <FormControlLabel
              sx={{ mr: 0.5 }}
              control={
                <Switch
                  size="small"
                  checked={showAnnotations}
                  onChange={(e) => onShowAnnotationsChange(e.target.checked)}
                />
              }
              label={<Typography variant="body2">Annotations</Typography>}
            />
            <Tooltip title="Download PNG">
              <IconButton size="small" sx={iconSx} onClick={handleDownloadPng} aria-label="Download PNG">
                <DownloadIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Reset zoom">
              <IconButton size="small" sx={iconSx} onClick={handleResetZoom} aria-label="Reset zoom">
                <ZoomOutMapIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            {actions}
          </Box>
        </Box>
        {hasSmoothed && (
          <SmoothingControl
            value={smoothing}
            onChange={onSmoothingChange}
            slopePctPerMonth={analysis?.trend.smoothed?.slope_pct_per_month}
          />
        )}
        <Box sx={{ height: { xs: 260, sm: 320 } }}>
          <Line ref={chartRef} data={data} options={options} />
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          Tip: drag across the chart to zoom in
          {showAnnotations && ' · shaded bands = regimes, dashed lines = breaks, red dots = anomalies'}
        </Typography>
      </CardContent>
    </Card>
  )
}
