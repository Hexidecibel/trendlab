import { useState } from 'react'
import CircularProgress from '@mui/material/CircularProgress'
import IconButton from '@mui/material/IconButton'
import Snackbar from '@mui/material/Snackbar'
import Tooltip from '@mui/material/Tooltip'
import VisibilityIcon from '@mui/icons-material/Visibility'
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined'
import { useWatchlist } from './watchlistContext'

interface Props {
  source: string
  query: string
  resample?: string
  /** Friendly name for the watch, e.g. "requests (PyPI)". */
  name: string
}

/**
 * One click adds the chart's exact query (source, query fields, resample)
 * to the watchlist with a "trend changes direction" alert, then opens the
 * drawer on it so the alert can be changed. Already watched: opens it.
 */
export function WatchButton({ source, query, resample, name }: Props) {
  const { find, add, openDrawer } = useWatchlist()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const existing = find(source, query)

  const handleClick = async () => {
    if (existing) {
      openDrawer(existing.id)
      return
    }
    setBusy(true)
    try {
      const { item } = await add({
        name,
        source,
        query,
        resample: resample || undefined,
        alert_type: 'trend_flip',
      })
      openDrawer(item.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add to the watchlist')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Tooltip title={existing ? 'Watching: open watchlist' : 'Watch: alert me when this trend changes'}>
        <span>
          <IconButton
            size="small"
            sx={{ p: 0.75 }}
            onClick={handleClick}
            disabled={busy}
            aria-label={existing ? 'Watching' : 'Watch'}
            color={existing ? 'primary' : 'default'}
            data-testid="watch-button"
          >
            {busy ? (
              <CircularProgress size={18} />
            ) : existing ? (
              <VisibilityIcon fontSize="small" />
            ) : (
              <VisibilityOutlinedIcon fontSize="small" />
            )}
          </IconButton>
        </span>
      </Tooltip>
      <Snackbar
        open={!!error}
        autoHideDuration={5000}
        onClose={() => setError(null)}
        message={error}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />
    </>
  )
}
