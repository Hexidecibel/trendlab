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
import Typography from '@mui/material/Typography'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import { fetchEventContext } from '../api/client'
import type { EventContext, TrendAnalysis } from '../api/types'

interface Props {
  analysis: TrendAnalysis
  compact?: boolean
}

const DIRECTION_COLORS: Record<string, 'success' | 'error' | 'default'> = {
  rising: 'success',
  falling: 'error',
  stable: 'default',
}

export function AnalysisPanel({ analysis, compact = false }: Props) {
  const { trend, seasonality, anomalies, structural_breaks } = analysis
  const chipColor = DIRECTION_COLORS[trend.direction] || 'default'

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
            Momentum: {trend.momentum.toFixed(4)}
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
        <Typography variant="subtitle2" gutterBottom>
          Trend Analysis
        </Typography>

        <Chip
          label={trend.direction.toUpperCase()}
          color={chipColor}
          size="small"
          sx={{ mb: 1 }}
        />
        <Typography variant="caption" display="block" color="text.secondary">
          Momentum: {trend.momentum.toFixed(4)} | Acceleration:{' '}
          {trend.acceleration.toFixed(4)}
        </Typography>

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
          {anomalies.anomaly_count} of {anomalies.total_points} points flagged
          ({anomalies.method})
        </Typography>
        {anomalies.anomalies.slice(0, 5).map((a, i) => (
          <Typography key={i} variant="caption" display="block" color="text.secondary" sx={{ ml: 1 }}>
            {a.date}: {a.value.toFixed(1)} (score: {a.score.toFixed(2)})
          </Typography>
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
            <Typography key={i} variant="caption" display="block" color="text.secondary" sx={{ ml: 1 }}>
              {b.date} ({b.method}, confidence: {b.confidence.toFixed(2)})
            </Typography>
          ))
        )}
      </CardContent>
    </Card>
  )
}
