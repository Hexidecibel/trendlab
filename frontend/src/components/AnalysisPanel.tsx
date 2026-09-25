import { useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Collapse from '@mui/material/Collapse'
import Divider from '@mui/material/Divider'
import Link from '@mui/material/Link'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import { fetchEventContext } from '../api/client'
import type { EventContext, StructuralBreak, TrendAnalysis, TrendSignal } from '../api/types'
import { formatCompact, formatPrecise, formatShortDate } from '../utils/format'
import type { ImpactRequest } from './ChangeImpactPopover'

/** Readable momentum: backend label if present, else a formatted percent per step. */
function formatMomentum(trend: TrendSignal): string {
  if (trend.momentum_label) return trend.momentum_label
  if (trend.momentum_pct_per_month != null && Number.isFinite(trend.momentum_pct_per_month)) {
    const v = trend.momentum_pct_per_month
    return `${v >= 0 ? '+' : ''}${v.toFixed(1)}% / month`
  }
  const pct = trend.momentum * 100
  if (!Number.isFinite(pct)) return 'n/a'
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}% / step`
}

/** Plain wording for a break: "big drop (-39%)", "trend change". */
function describeBreak(b: StructuralBreak): string {
  const kind = b.label || 'change'
  const pct = b.change_pct
  return pct != null && Number.isFinite(pct) && Math.abs(pct) >= 5
    ? `${kind} (${pct > 0 ? '+' : ''}${pct.toFixed(0)}%)`
    : kind
}

interface Props {
  analysis: TrendAnalysis
  compact?: boolean
  /** Ask "what changed after" a structural break. */
  onBreakClick?: (req: ImpactRequest) => void
}

const DIRECTION_COLORS: Record<string, 'success' | 'error' | 'default'> = {
  rising: 'success',
  falling: 'error',
  stable: 'default',
}

export function AnalysisPanel({ analysis, compact = false, onBreakClick }: Props) {
  const { trend, seasonality, anomalies, structural_breaks } = analysis
  const chipColor = DIRECTION_COLORS[trend.direction] || 'default'
  const momentumText = formatMomentum(trend)
  // From the smoothed trend's change in slope; null when not meaningful
  const accelText = trend.acceleration_label ?? null
  const summaryLines = (analysis.summary_lines ?? []).filter((l) => l && l.trim())

  const [eventContexts, setEventContexts] = useState<EventContext[]>([])
  const [contextLoading, setContextLoading] = useState(false)
  const [contextOpen, setContextOpen] = useState(false)
  const [contextFetched, setContextFetched] = useState(false)

  const handleWhyClick = async () => {
    if (contextFetched) {
      setContextOpen(!contextOpen)
      return
    }
    setContextLoading(true)
    try {
      const dates = anomalies.anomalies.slice(0, 5).map((a) => a.date)
      const results = await fetchEventContext(analysis.source, analysis.query, dates)
      setEventContexts(results)
      setContextFetched(true)
      setContextOpen(true)
    } catch {
      setEventContexts([])
      setContextFetched(true)
      setContextOpen(true)
    } finally {
      setContextLoading(false)
    }
  }

  if (compact) {
    return (
      <Card variant="outlined" sx={{ bgcolor: 'background.default' }}>
        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
          <Chip
            label={trend.direction.toUpperCase()}
            color={chipColor}
            size="small"
            sx={{ mr: 1 }}
          />
          <Typography variant="caption" color="text.secondary">
            Momentum: {momentumText}
          </Typography>
          <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
            {seasonality.detected
              ? `${seasonality.period_days}-day seasonality`
              : 'No seasonality'} · {anomalies.anomaly_count} anomalies · {structural_breaks.length} breaks
          </Typography>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardContent>
        {summaryLines.length > 0 && (
          <>
            <Typography variant="subtitle2" gutterBottom>
              What changed
            </Typography>
            <Box component="ul" sx={{ m: 0, mb: 1.5, pl: 2.5 }}>
              {summaryLines.slice(0, 5).map((line, i) => (
                <Typography key={i} component="li" variant="body2" sx={{ mb: 0.5 }}>
                  {line}
                </Typography>
              ))}
            </Box>
            <Divider sx={{ mb: 1.5 }} />
          </>
        )}

        <Typography variant="subtitle2" gutterBottom>
          Trend Analysis
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
          <Chip label={trend.direction.toUpperCase()} color={chipColor} size="small" />
          <Typography variant="body2" fontWeight={600}>
            {momentumText}
          </Typography>
          {accelText && (
            <Typography variant="caption" color="text.secondary">
              · {accelText}
            </Typography>
          )}
        </Box>

        <Divider sx={{ my: 1.5 }} />

        <Typography variant="caption" fontWeight={600} display="block" gutterBottom>
          Seasonality
        </Typography>
        {seasonality.detected ? (
          <Typography variant="caption" color="text.secondary">
            Detected: {seasonality.period_days}-day period (strength:{' '}
            {seasonality.strength?.toFixed(2)})
          </Typography>
        ) : (
          <Typography variant="caption" color="text.disabled">
            No seasonality detected
          </Typography>
        )}

        <Divider sx={{ my: 1.5 }} />

        <Typography variant="caption" fontWeight={600} display="block" gutterBottom>
          Anomalies
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {anomalies.anomaly_count === 0
            ? 'Nothing unusual against the trend'
            : `${anomalies.anomaly_count} unusual ${anomalies.anomaly_count === 1 ? 'day' : 'points'} of ${anomalies.total_points}`}
        </Typography>
        {anomalies.anomalies.slice(0, 5).map((a, i) => (
          <Tooltip
            key={i}
            placement="left"
            title={`${formatPrecise(a.value)} on ${a.date} · ${anomalies.method} score ${a.score.toFixed(2)} (threshold ${anomalies.threshold})`}
          >
            <Typography variant="caption" display="block" color="text.secondary" sx={{ ml: 1, width: 'fit-content' }} data-testid="anomaly-row">
              {formatShortDate(a.date)} · {formatCompact(a.value)} · {a.score.toFixed(1)}× unusual
            </Typography>
          </Tooltip>
        ))}

        {anomalies.anomaly_count > 0 && (
          <Box sx={{ mt: 1 }}>
            <Button
              size="small"
              variant="text"
              startIcon={contextLoading ? <CircularProgress size={14} /> : <HelpOutlineIcon />}
              onClick={handleWhyClick}
              disabled={contextLoading}
              sx={{ textTransform: 'none', fontSize: '0.75rem' }}
            >
              {contextOpen ? 'Hide context' : 'Why did this spike?'}
            </Button>
            <Collapse in={contextOpen}>
              <Box sx={{ ml: 1, mt: 0.5 }}>
                {eventContexts.length === 0 ? (
                  <Typography variant="caption" color="text.disabled">
                    No event context found for these dates.
                  </Typography>
                ) : (
                  eventContexts.map((ev, i) => (
                    <Box key={i} sx={{ mb: 0.5 }}>
                      <Typography variant="caption" color="text.secondary" display="block">
                        <strong>{ev.date}:</strong> {ev.headline}
                      </Typography>
                      {ev.source_url && (
                        <Link
                          href={ev.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          variant="caption"
                          sx={{ ml: 1 }}
                        >
                          Source
                        </Link>
                      )}
                    </Box>
                  ))
                )}
              </Box>
            </Collapse>
          </Box>
        )}

        <Divider sx={{ my: 1.5 }} />

        <Typography variant="caption" fontWeight={600} display="block" gutterBottom>
          Structural Breaks
        </Typography>
        {structural_breaks.length === 0 ? (
          <Typography variant="caption" color="text.disabled">
            None detected
          </Typography>
        ) : (
          structural_breaks.map((b, i) => (
            <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 1 }}>
              <Tooltip placement="left" title={`${b.date} · ${b.method} break, confidence ${b.confidence.toFixed(2)}`}>
                <Typography variant="caption" color="text.secondary" data-testid="break-row">
                  {formatShortDate(b.date)} · {describeBreak(b)}
                </Typography>
              </Tooltip>
              {onBreakClick && (
                <Link
                  component="button"
                  variant="caption"
                  onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
                    const r = e.currentTarget.getBoundingClientRect()
                    onBreakClick({ date: b.date, x: r.left + r.width / 2, y: r.bottom, label: b.label })
                  }}
                >
                  What changed?
                </Link>
              )}
            </Box>
          ))
        )}
      </CardContent>
    </Card>
  )
}
