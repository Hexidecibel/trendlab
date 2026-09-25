import { useRef } from 'react'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import IconButton from '@mui/material/IconButton'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import { alpha } from '@mui/material/styles'
import DownloadIcon from '@mui/icons-material/Download'
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap'
import { Line } from 'react-chartjs-2'
import type { Chart as ChartJS } from 'chart.js'
import type { CorrelateResponse, DataPoint, TimeSeries, TrendAnalysis } from '../../api/types'
import { SmoothingControl } from '../SmoothingControl'
import { smoothedPoints } from '../../smoothing'
import type { SmoothingPreset } from '../../smoothing'
import type { CompareMode } from '../../urlState'
import { formatLagLong } from '../../utils/lag'
import { getFriendlyLabel } from '../../utils/labels'
import { compactTick, formatPrecise } from '../../utils/format'

const COLORS = ['#3b82f6', '#f97316', '#10b981']

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

// Get Y-axis label based on series metrics
function getYAxisLabel(seriesList: TimeSeries[]): string {
  if (seriesList.length === 0) return 'Value'

  // Check if any series is normalized (transforms stored as array in metadata)
  const isNormalized = seriesList.some(s => {
    const meta = s.metadata as Record<string, unknown>
    const transforms = meta.transforms as string[] | undefined
    return transforms?.includes('normalize')
  })
  if (isNormalized) return 'Normalized Value'

  // Collect all metric labels
  const labels = seriesList.map(s => {
    const meta = s.metadata as Record<string, unknown>
    return (meta.metric_label as string) || (meta.metric as string) || null
  })

  // Filter out nulls and get unique labels
  const uniqueLabels = [...new Set(labels.filter(Boolean))]

  if (uniqueLabels.length === 1) {
    return uniqueLabels[0] as string
  } else if (uniqueLabels.length > 1) {
    return 'Value (mixed metrics)'
  }

  return 'Value'
}

/** The analysis for a series (analyses skip empty series, so match by id). */
function analysisFor(s: TimeSeries, analyses: TrendAnalysis[] | null | undefined): TrendAnalysis | undefined {
  return analyses?.find((a) => a.source === s.source && a.query === s.query)
}

/**
 * Rebase each line to 100 at the first date every line has a positive value.
 * Returns null when there is no such date (then the raw values are shown).
 */
function rebaseToIndex(lines: DataPoint[][]): { lines: DataPoint[][]; baseDate: string } | null {
  if (lines.length === 0 || lines.some((l) => l.length === 0)) return null
  const maps = lines.map((l) => new Map(l.map((p) => [p.date, p.value])))
  const candidates = [...lines[0]].map((p) => p.date).sort()
  const baseDate = candidates.find((d) => maps.every((m) => (m.get(d) ?? 0) > 0))
  if (!baseDate) return null
  return {
    baseDate,
    lines: lines.map((l, i) => {
      const base = maps[i].get(baseDate) as number
      return l.map((p) => ({ date: p.date, value: (p.value / base) * 100 }))
    }),
  }
}

function describeStrength(r: number): string {
  const a = Math.abs(r)
  const sign = r < 0 ? ' negative' : ''
  if (a >= 0.7) return `strong${sign}`
  if (a >= 0.4) return `moderate${sign}`
  if (a >= 0.2) return `weak${sign}`
  return 'little or none'
}

/** e.g. "r = 0.82 (strong), best at lag 3 weeks (react leads)". */
function describeCorrelation(c: CorrelateResponse, nameA: string, nameB: string): string {
  const r = c.pearson.r
  let text = `r = ${r.toFixed(2)} (${describeStrength(r)})`
  const best = [...c.lag_analysis].sort((x, y) => Math.abs(y.correlation) - Math.abs(x.correlation))[0]
  if (best && best.lag !== 0 && Math.abs(best.correlation) > Math.abs(r) + 0.02) {
    // Positive lag pairs A[t] with B[t + lag]: A moves first
    const leader = best.lag > 0 ? nameA : nameB
    text += `, best at lag ${formatLagLong(best.lag, c.lag_step)} (${leader} leads, r = ${best.correlation.toFixed(2)})`
  } else {
    text += ', strongest with no lag'
  }
  return text
}

interface Props {
  seriesList: TimeSeries[]
  analyses?: TrendAnalysis[] | null
  resample?: string
  smoothing: SmoothingPreset
  onSmoothingChange: (preset: SmoothingPreset) => void
  mode: CompareMode
  onModeChange: (mode: CompareMode) => void
  /** Correlation between the two series (two-series compares only). */
  correlation?: CorrelateResponse | null
}

export function CompareChart({
  seriesList,
  analyses,
  resample,
  smoothing,
  onSmoothingChange,
  mode,
  onModeChange,
  correlation,
}: Props) {
  const chartRef = useRef<ChartJS<'line', { x: string; y: number }[]>>(null)

  const handleResetZoom = () => {
    chartRef.current?.resetZoom()
  }

  const handleDownloadPng = () => {
    const chart = chartRef.current
    if (!chart) return
    const url = chart.toBase64Image()
    const link = document.createElement('a')
    const labels = seriesList.map(s => s.query).join('-vs-')
    link.download = `compare-${labels}.png`
    link.href = url
    link.click()
  }

  if (seriesList.length === 0) return null

  const hasSmoothed = seriesList.every((s) => !!analysisFor(s, analyses)?.trend.smoothed)
  const trendLines = seriesList.map((s) =>
    hasSmoothed ? smoothedPoints(analysisFor(s, analyses)?.trend, smoothing) : null,
  )
  const showTrend = trendLines.every((t) => t !== null)
  const rawLines = seriesList.map((s) => s.points)

  // Index each series by the line the reader follows: the trend when
  // smoothing is on (a single noisy day makes a poor base), else the raw data.
  let displayRaw = rawLines
  let displayTrend = showTrend ? (trendLines as DataPoint[][]) : null
  let baseDate: string | null = null
  let indexFailed = false
  if (mode === 'index') {
    const primaryLines = displayTrend ?? displayRaw
    const rebased = rebaseToIndex(primaryLines)
    if (rebased) {
      baseDate = rebased.baseDate
      const factors = primaryLines.map((l) => {
        const v = l.find((p) => p.date === rebased.baseDate)?.value ?? 1
        return 100 / v
      })
      displayRaw = rawLines.map((l, i) => l.map((p) => ({ date: p.date, value: p.value * factors[i] })))
      if (displayTrend) displayTrend = rebased.lines
    } else {
      indexFailed = true
    }
  }
  const indexed = mode === 'index' && !indexFailed

  const datasets = seriesList.flatMap((s, i) => {
    const color = COLORS[i % COLORS.length]
    const label = getFriendlyLabel(s)
    const raw = {
      label: displayTrend ? `${label} (raw)` : label,
      data: displayRaw[i].map((p) => ({ x: p.date, y: p.value })),
      borderColor: displayTrend ? alpha(color, 0.3) : color,
      backgroundColor: displayTrend ? alpha(color, 0.3) : color,
      pointRadius: 0,
      borderWidth: displayTrend ? 1 : 2,
      order: 1,
    }
    if (!displayTrend) return [raw]
    return [
      {
        label,
        data: displayTrend[i].map((p) => ({ x: p.date, y: p.value })),
        borderColor: color,
        backgroundColor: color,
        pointRadius: 0,
        borderWidth: 3,
        order: 0,
      },
      raw,
    ]
  })

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
        time: { unit: getTimeUnit(resample), tooltipFormat: 'MMM d, yyyy' },
        title: { display: true, text: 'Date' },
      },
      y: {
        title: {
          display: true,
          text: indexed ? `Index (${baseDate} = 100)` : getYAxisLabel(seriesList),
        },
        ticks: { callback: compactTick },
      },
    },
    plugins: {
      legend: {
        labels: {
          // Hide the faint raw lines from the legend when a trend is drawn
          filter: (item: { text: string }) => !(displayTrend && item.text.endsWith(' (raw)')),
        },
      },
      tooltip: {
        callbacks: {
          label: (ctx: { dataset: { label?: string }; parsed: { y: number | null } }) => {
            const y = ctx.parsed.y
            if (y == null) return ctx.dataset.label ?? ''
            const v = indexed ? y.toFixed(1) : formatPrecise(y)
            return `${ctx.dataset.label}: ${v}`
          },
        },
      },
      zoom: {
        zoom: {
          drag: { enabled: true },
          mode: 'x' as const,
        },
      },
    },
  }

  const corrText =
    correlation && seriesList.length === 2
      ? describeCorrelation(correlation, getFriendlyLabel(seriesList[0]), getFriendlyLabel(seriesList[1]))
      : null

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography variant="subtitle2">Series Comparison</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <ToggleButtonGroup
              size="small"
              exclusive
              value={mode}
              onChange={(_, v) => {
                if (v === 'index' || v === 'raw') onModeChange(v)
              }}
              aria-label="Scale"
              sx={{ mr: 0.5, '& .MuiToggleButton-root': { px: 1.25, py: 0.25, textTransform: 'none', fontSize: '0.8rem', lineHeight: 1.6 } }}
            >
              <ToggleButton value="index" title="Rebase every series to 100 at the first common date">
                Index = 100
              </ToggleButton>
              <ToggleButton value="raw" title="Actual values">
                Raw values
              </ToggleButton>
            </ToggleButtonGroup>
            <Tooltip title="Download PNG">
              <IconButton size="small" sx={{ p: 0.75 }} onClick={handleDownloadPng} aria-label="Download PNG">
                <DownloadIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Reset zoom">
              <IconButton size="small" sx={{ p: 0.75 }} onClick={handleResetZoom} aria-label="Reset zoom">
                <ZoomOutMapIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
        {hasSmoothed && <SmoothingControl value={smoothing} onChange={onSmoothingChange} />}
        {smoothing === 'line' && showTrend && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
            {seriesList
              .map((s) => {
                const pct = analysisFor(s, analyses)?.trend.smoothed?.slope_pct_per_month
                if (pct == null || !Number.isFinite(pct)) return null
                return `${getFriendlyLabel(s)}: ${pct >= 0 ? '+' : ''}${pct.toFixed(1)}% / month`
              })
              .filter(Boolean)
              .join(' · ')}
          </Typography>
        )}
        <Box sx={{ height: { xs: 280, sm: 400 } }}>
          <Line ref={chartRef} data={{ datasets }} options={options} />
        </Box>
        {corrText && (
          <Typography variant="body2" sx={{ mt: 1 }} data-testid="compare-correlation">
            <Box component="span" sx={{ color: 'text.secondary' }}>Correlation: </Box>
            {corrText}
          </Typography>
        )}
        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
          {indexFailed
            ? 'Index view needs a date where every series has a positive value; showing actual values. · '
            : indexed
              ? `Each series is rebased to 100 on ${baseDate}, so lines show relative growth. · `
              : ''}
          Drag across the chart to zoom in
        </Typography>
      </CardContent>
    </Card>
  )
}
