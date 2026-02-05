import { useState, useEffect } from 'react'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Typography from '@mui/material/Typography'
import CircularProgress from '@mui/material/CircularProgress'
import Chip from '@mui/material/Chip'
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import RefreshIcon from '@mui/icons-material/Refresh'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import TrendingDownIcon from '@mui/icons-material/TrendingDown'
import TrendingFlatIcon from '@mui/icons-material/TrendingFlat'

interface InsightItem {
  source: string
  query: string
  headline: string
  trend_direction: string
  momentum: number
}

interface Props {
  onSelectInsight?: (source: string, query: string) => void
}

export function InsightsFeed({ onSelectInsight }: Props) {
  const [insights, setInsights] = useState<InsightItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadInsights = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/insights-feed?limit=5')
      if (!response.ok) {
        const detail = await response.json().catch(() => ({ detail: response.statusText }))
        throw new Error(detail.detail || `HTTP ${response.status}`)
      }
      const data = await response.json()
      setInsights(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load insights')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadInsights()
  }, [])

  const getTrendIcon = (direction: string) => {
    switch (direction) {
      case 'rising':
        return <TrendingUpIcon sx={{ color: 'success.main' }} />
      case 'falling':
        return <TrendingDownIcon sx={{ color: 'error.main' }} />
      default:
        return <TrendingFlatIcon sx={{ color: 'text.secondary' }} />
    }
  }

  const getTrendColor = (direction: string) => {
    switch (direction) {
      case 'rising':
        return 'success'
      case 'falling':
        return 'error'
      default:
        return 'default'
    }
  }

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="subtitle2">
            Trending Insights
          </Typography>
          <Tooltip title="Refresh insights">
            <IconButton size="small" onClick={loadInsights} disabled={loading}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>

        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <CircularProgress size={24} />
          </Box>
        )}

        {error && (
          <Typography variant="body2" color="error" sx={{ py: 2 }}>
            {error}
          </Typography>
        )}

        {!loading && !error && insights.length === 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
            No insights available. AI key may not be configured.
          </Typography>
        )}

        {!loading && !error && insights.length > 0 && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {insights.map((insight, index) => (
              <Box
                key={index}
                sx={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 1.5,
                  p: 1.5,
                  borderRadius: 1,
                  bgcolor: 'action.hover',
                  cursor: onSelectInsight ? 'pointer' : 'default',
                  transition: 'background-color 0.2s',
                  '&:hover': onSelectInsight
                    ? { bgcolor: 'action.selected' }
                    : {},
                }}
                onClick={() => onSelectInsight?.(insight.source, insight.query)}
              >
                <Box sx={{ mt: 0.5 }}>
                  {getTrendIcon(insight.trend_direction)}
                </Box>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="body2" sx={{ mb: 0.5 }}>
                    {insight.headline}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <Chip
                      label={insight.source}
                      size="small"
                      variant="outlined"
                      sx={{ height: 20, fontSize: '0.7rem' }}
                    />
                    <Chip
                      label={insight.trend_direction}
                      size="small"
                      color={getTrendColor(insight.trend_direction) as 'success' | 'error' | 'default'}
                      sx={{ height: 20, fontSize: '0.7rem' }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      {insight.query}
                    </Typography>
                  </Box>
                </Box>
              </Box>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  )
}
