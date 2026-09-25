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
import type { ActiveElement, ChartEvent, Chart as ChartJS } from 'chart.js'
import { fetchEventContext } from '../../api/client'
import type { DataPoint, EventContext, TimeSeries, ForecastComparison, TrendAnalysis } from '../../api/types'
import { SmoothingControl } from '../SmoothingControl'
import { smoothedPoints } from '../../smoothing'
import type { SmoothingPreset } from '../../smoothing'
import { compactTick, formatCompact, formatPrecise, formatShortDate } from '../../utils/format'
import type { ImpactRequest } from '../ChangeImpactPopover'
import { buildYearLines, spansMoreThanAYear } from './yearOverlay'

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
  /** Plain click on a date (or a break line): ask what changed after it. */
  onDateClick?: (req: ImpactRequest) => void
}

// A click that moved further than this (px) since mousedown was a drag-zoom
const CLICK_SLOP_PX = 5
// Clicks this close (px) to a break line pick the break's date
const BREAK_HIT_PX = 8

/** Hover label for a structural break: "Aug 25 · big drop (-39%)". */
function breakLabel(brk: TrendAnalysis['structural_breaks'][number]): string {
  const kind = brk.label || 'change'
  const pct =
    brk.change_pct != null && Number.isFinite(brk.change_pct) && Math.abs(brk.change_pct) >= 5
      ? ` (${brk.change_pct > 0 ? '+' : ''}${brk.change_pct.toFixed(0)}%)`
      : ''
  return `${formatShortDate(brk.date)} · ${kind}${pct}`
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
  onDateClick,
}: Props) {
  const theme = useTheme()
  const isDark = theme.palette.mode === 'dark'
  const showBreaks = showAnnotations
  const showAnomalies = showAnnotations
  const showRegimes = showAnnotations
  const chartRef = useRef<ChartJS<'line', { x: string; y: number }[]>>(null)
  const [eventMap, setEventMap] = useState<Record<string, EventContext>>({})
  const [compareYears, setCompareYears] = useState(false)
  const downAt = useRef<{ x: number; y: number } | null>(null)

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

  const canCompareYears = spansMoreThanAYear(series.points)
  const yoy = compareYears && canCompareYears

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
          content: [breakLabel(brk), onDateClick ? 'Click: what changed after?' : ''].filter(Boolean),
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
      const head = `${formatShortDate(a.date)} · ${formatCompact(a.value)} · ${a.score.toFixed(1)}× unusual`
      const labelContent = ev ? [head, ev.headline.slice(0, 60)] : [head]
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

  // Plain click -> "what changed after this date?" (drags are zooms)
  const handleChartClick = (event: ChartEvent, _els: ActiveElement[], chart: ChartJS) => {
    if (!onDateClick || yoy || event.x == null) return
    const native = event.native as MouseEvent | null
    const start = downAt.current
    if (native && start && Math.hypot(native.clientX - start.x, native.clientY - start.y) > CLICK_SLOP_PX) {
      return
    }
    const xScale = chart.scales.x
    const cx = native?.clientX ?? 0
    const cy = native?.clientY ?? 0
    // A break line under the pointer wins
    if (analysis && showBreaks) {
      for (const brk of analysis.structural_breaks) {
        const px = xScale.getPixelForValue(Date.parse(brk.date))
        if (Math.abs(px - event.x) <= BREAK_HIT_PX) {
          onDateClick({ date: brk.date, x: cx, y: cy, label: brk.label })
          return
        }
      }
    }
    const t = xScale.getValueForPixel(event.x)
    const pts = series.points
    if (t == null || pts.length < 2) return
    // Past the last actual point (the forecast) there's nothing to compare
    const last = Date.parse(pts[pts.length - 1].date)
    const step = (last - Date.parse(pts[0].date)) / (pts.length - 1)
    if (t > last + step / 2) return
    let best = pts[0]
    let bestDist = Infinity
    for (const p of pts) {
      const d = Math.abs(Date.parse(p.date) - t)
      if (d < bestDist) {
        best = p
        bestDist = d
      }
    }
    onDateClick({ date: best.date, x: cx, y: cy })
  }

  const tooltipLabel = (ctx: { dataset: { label?: string }; parsed: { y: number | null } }) =>
    `${ctx.dataset.label ?? ''}: ${formatPrecise(ctx.parsed.y)}`

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    onClick: handleChartClick,
    onHover: (_e: ChartEvent, _els: ActiveElement[], chart: ChartJS) => {
      // Hint that a click does something
      if (onDateClick && chart.canvas) chart.canvas.style.cursor = 'crosshair'
    },
    scales: {
      x: {
        type: 'time' as const,
        time: { unit: getTimeUnit(resample), tooltipFormat: 'MMM d, yyyy' },
        title: { display: true, text: 'Date' },
      },
      y: {
        title: { display: true, text: getYAxisLabel(series) },
        ticks: { callback: compactTick },
      },
    },
    plugins: {
      legend: {
        labels: {
          filter: (item: { text: string }) =>
            !item.text.startsWith('95% CI'),
        },
      },
      tooltip: {
        filter: (item: { dataset: { label?: string } }) => !item.dataset.label?.startsWith('95% CI'),
        callbacks: { label: tooltipLabel },
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

  // --- Year-over-year overlay: one line per calendar year, Jan-Dec ---
  const yearTrend = smoothing === 'light' || smoothing === 'medium' || smoothing === 'heavy'
  const yearSource: DataPoint[] =
    (yearTrend ? smoothedPoints(analysis?.trend, smoothing) : null) ?? series.points
  const yearLines = yoy ? buildYearLines(yearSource) : []
  const monthly = ['month', 'quarter', 'year'].includes(getTimeUnit(resample))
  const pastColors = isDark
    ? ['#94a3b8', '#a78bfa', '#5eead4', '#fca5a5', '#fcd34d', '#93c5fd']
    : ['#64748b', '#8b5cf6', '#14b8a6', '#ef4444', '#d97706', '#3b82f6']
  const yearData = {
    datasets: yearLines.map((line, i) => {
      const age = yearLines.length - 1 - i
      const current = age === 0
      const color = current ? primary : alpha(pastColors[(age - 1) % pastColors.length], Math.max(0.35, 0.75 - 0.12 * (age - 1)))
      return {
        label: String(line.year),
        data: line.points,
        borderColor: color,
        backgroundColor: color,
        borderWidth: current ? 3 : 1.5,
        pointRadius: monthly ? (current ? 3 : 2) : 0,
        order: current ? 0 : 1 + age,
        spanGaps: false,
      }
    }),
  }
  const yearOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'x' as const, intersect: false },
    scales: {
      x: {
        type: 'time' as const,
        min: '2000-01-01',
        max: '2000-12-31',
        time: { unit: 'month' as const, displayFormats: { month: 'MMM' }, tooltipFormat: monthly ? 'MMMM' : 'MMM d' },
        title: { display: false, text: '' },
      },
      y: {
        title: { display: true, text: getYAxisLabel(series) },
        ticks: { callback: compactTick },
      },
    },
    plugins: {
      legend: { labels: { boxWidth: 24 } },
      tooltip: { callbacks: { label: tooltipLabel } },
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
          <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 0.5 }}>
            {canCompareYears && (
              <FormControlLabel
                sx={{ mr: 0.5 }}
                control={
                  <Switch
                    size="small"
                    checked={compareYears}
                    onChange={(e) => setCompareYears(e.target.checked)}
                    slotProps={{ input: { 'aria-label': 'Compare years' } }}
                  />
                }
                label={<Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>Compare years</Typography>}
                title="Overlay each calendar year, aligned Jan-Dec"
              />
            )}
            <FormControlLabel
              sx={{ mr: 0.5 }}
              disabled={yoy}
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
        <Box
          sx={{ height: { xs: 260, sm: 320 } }}
          onPointerDown={(e) => {
            downAt.current = { x: e.clientX, y: e.clientY }
          }}
        >
          {yoy ? (
            <Line key="yoy" data={yearData} options={yearOptions} />
          ) : (
            <Line key="series" ref={chartRef} data={data} options={options} />
          )}
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          {yoy ? (
            <>
              Each line is one calendar year{monthly ? ' (by month)' : ', aligned by day of year'}
              {yearTrend && yearSource !== series.points ? `, ${smoothing} trend` : ''}; the current year is bold.
            </>
          ) : (
            <>
              Drag across the chart to zoom{onDateClick ? ' · click a date to see what changed after it' : ''}
              {showAnnotations && ' · shaded bands = regimes, dashed lines = breaks, red dots = anomalies'}
            </>
          )}
        </Typography>
      </CardContent>
    </Card>
  )
}
