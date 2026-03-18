import Box from '@mui/material/Box'
import CircularProgress from '@mui/material/CircularProgress'
import LinearProgress from '@mui/material/LinearProgress'
import Typography from '@mui/material/Typography'
import type { ProgressState } from '../hooks/useWebSocket'

const STAGE_LABELS: Record<string, string> = {
  cache_check: 'Checking cache',
  fetch: 'Fetching data',
  analyze: 'Analyzing trends',
  forecast: 'Running forecasts',
  complete: 'Complete',
}

interface ProgressBarProps {
  progress: ProgressState
}

export function ProgressBar({ progress }: ProgressBarProps) {
  if (!progress.connected) {
    // Fallback to simple spinner when WS is not available
    return (
      <Box sx={{ textAlign: 'center', py: 6 }}>
        <CircularProgress size={32} />
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Fetching data and running analysis...
        </Typography>
      </Box>
    )
  }

  const pct = Math.round(progress.progress * 100)
  const label = STAGE_LABELS[progress.stage] || progress.message || 'Working...'

  return (
    <Box sx={{ py: 4, px: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="body2" color="text.secondary">
          {label}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {pct}%
        </Typography>
      </Box>
      <LinearProgress
        variant="determinate"
        value={pct}
        sx={{ height: 8, borderRadius: 4 }}
      />
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
        <Typography variant="caption" color="text.disabled">
          Fetch
        </Typography>
        <Typography variant="caption" color="text.disabled">
          Analyze
        </Typography>
        <Typography variant="caption" color="text.disabled">
          Forecast
        </Typography>
      </Box>
    </Box>
  )
}
