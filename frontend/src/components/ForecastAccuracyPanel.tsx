import { useState, useEffect } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CircularProgress from '@mui/material/CircularProgress'
import Collapse from '@mui/material/Collapse'
import IconButton from '@mui/material/IconButton'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Typography from '@mui/material/Typography'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import SaveIcon from '@mui/icons-material/Save'
import type { ForecastComparison } from '../api/types'

interface Snapshot {
  id: number
  source: string
  query: string
  forecast_date: string
  horizon: number
  model_name: string
  created_at: string
}

interface AccuracyResult {
  snapshot_id: number
  forecast_date: string | null
  model_name: string | null
  matched_points: number
  mae: number | null
  rmse: number | null
  within_ci_pct: number | null
}

interface Props {
  source: string
  query: string
  forecast: ForecastComparison
}

export function ForecastAccuracyPanel({ source, query, forecast }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [accuracyResults, setAccuracyResults] = useState<Record<number, AccuracyResult>>({})
  const [loadingAccuracy, setLoadingAccuracy] = useState<Record<number, boolean>>({})

  const loadSnapshots = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ source, query, limit: '10' })
      const response = await fetch(`/api/forecast-snapshots?${params}`)
      if (response.ok) {
        const data = await response.json()
        setSnapshots(data)
      }
    } catch {
      // Silently fail
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (expanded) {
      loadSnapshots()
    }
  }, [expanded, source, query])

  const handleSaveSnapshot = async () => {
    setSaving(true)
    try {
      const params = new URLSearchParams({
        source,
        query,
        model_name: forecast.recommended_model,
        horizon: String(forecast.horizon),
      })
      const response = await fetch(`/api/forecast-snapshot?${params}`, {
        method: 'POST',
      })
      if (response.ok) {
        // Refresh snapshots list
        loadSnapshots()
      }
    } catch {
      // Silently fail
    } finally {
      setSaving(false)
    }
  }

  const handleCheckAccuracy = async (snapshotId: number) => {
    setLoadingAccuracy((prev) => ({ ...prev, [snapshotId]: true }))
    try {
      const params = new URLSearchParams({
        snapshot_id: String(snapshotId),
        source,
        query,
      })
      const response = await fetch(`/api/forecast-accuracy?${params}`)
      if (response.ok) {
        const data = await response.json()
        setAccuracyResults((prev) => ({ ...prev, [snapshotId]: data }))
      }
    } catch {
      // Silently fail
    } finally {
      setLoadingAccuracy((prev) => ({ ...prev, [snapshotId]: false }))
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  return (
    <Card sx={{ mt: 2 }}>
      <CardContent sx={{ py: 1.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="subtitle2">
              Forecast Accuracy Tracker
            </Typography>
            <IconButton
              size="small"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          </Box>
          <Button
            size="small"
            variant="outlined"
            startIcon={saving ? <CircularProgress size={14} /> : <SaveIcon />}
            onClick={handleSaveSnapshot}
            disabled={saving}
            sx={{ textTransform: 'none', fontSize: '0.75rem' }}
          >
            Save Snapshot
          </Button>
        </Box>

        <Collapse in={expanded}>
          <Box sx={{ mt: 2 }}>
            {loading && (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                <CircularProgress size={20} />
              </Box>
            )}

            {!loading && snapshots.length === 0 && (
              <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                No saved snapshots yet. Save a snapshot to track forecast accuracy over time.
              </Typography>
            )}

            {!loading && snapshots.length > 0 && (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Date</TableCell>
                    <TableCell>Model</TableCell>
                    <TableCell>Horizon</TableCell>
                    <TableCell>MAE</TableCell>
                    <TableCell>RMSE</TableCell>
                    <TableCell>CI Coverage</TableCell>
                    <TableCell></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {snapshots.map((snapshot) => {
                    const accuracy = accuracyResults[snapshot.id]
                    const isLoading = loadingAccuracy[snapshot.id]

                    return (
                      <TableRow key={snapshot.id}>
                        <TableCell>{formatDate(snapshot.forecast_date)}</TableCell>
                        <TableCell>{snapshot.model_name}</TableCell>
                        <TableCell>{snapshot.horizon}d</TableCell>
                        <TableCell>
                          {accuracy ? (
                            accuracy.mae !== null ? accuracy.mae.toFixed(2) : '-'
                          ) : '-'}
                        </TableCell>
                        <TableCell>
                          {accuracy ? (
                            accuracy.rmse !== null ? accuracy.rmse.toFixed(2) : '-'
                          ) : '-'}
                        </TableCell>
                        <TableCell>
                          {accuracy ? (
                            accuracy.within_ci_pct !== null ? `${accuracy.within_ci_pct}%` : '-'
                          ) : '-'}
                        </TableCell>
                        <TableCell>
                          {!accuracy && (
                            <Button
                              size="small"
                              onClick={() => handleCheckAccuracy(snapshot.id)}
                              disabled={isLoading}
                              sx={{ textTransform: 'none', fontSize: '0.7rem', minWidth: 'auto' }}
                            >
                              {isLoading ? <CircularProgress size={12} /> : 'Check'}
                            </Button>
                          )}
                          {accuracy && accuracy.matched_points > 0 && (
                            <Typography variant="caption" color="text.secondary">
                              {accuracy.matched_points} pts
                            </Typography>
                          )}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}

            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
              Save snapshots of your forecasts to compare against actual values later.
            </Typography>
          </Box>
        </Collapse>
      </CardContent>
    </Card>
  )
}
