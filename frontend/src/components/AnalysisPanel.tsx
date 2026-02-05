import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Chip from '@mui/material/Chip'
import Divider from '@mui/material/Divider'
import Typography from '@mui/material/Typography'
import type { TrendAnalysis } from '../api/types'

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
