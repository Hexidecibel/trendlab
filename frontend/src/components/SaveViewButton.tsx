import { useState } from 'react'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Link from '@mui/material/Link'
import CircularProgress from '@mui/material/CircularProgress'
import BookmarkIcon from '@mui/icons-material/Bookmark'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import { saveView } from '../api/client'
import type { SaveViewRequest, SavedViewResponse } from '../api/types'

interface Props {
  source: string
  query: string
  horizon: number
  start?: string
  end?: string
  resample?: string
  apply?: string
  anomalyMethod?: string
}

export function SaveViewButton({
  source,
  query,
  horizon,
  start,
  end,
  resample,
  apply,
  anomalyMethod = 'zscore',
}: Props) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedView, setSavedView] = useState<SavedViewResponse | null>(null)
  const [copied, setCopied] = useState(false)

  const handleOpen = () => {
    setOpen(true)
    setName(`${source}: ${query}`)
    setError(null)
    setSavedView(null)
  }

  const handleClose = () => {
    setOpen(false)
  }

  const handleSave = async () => {
    if (!name.trim()) return

    setLoading(true)
    setError(null)

    try {
      const request: SaveViewRequest = {
        name: name.trim(),
        source,
        query,
        horizon,
        start,
        end,
        resample,
        apply,
        anomaly_method: anomalyMethod,
      }
      const result = await saveView(request)
      setSavedView(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save view')
    } finally {
      setLoading(false)
    }
  }

  const shareUrl = savedView
    ? `${window.location.origin}?view=${savedView.hash_id}`
    : ''

  const handleCopy = async () => {
    await navigator.clipboard.writeText(shareUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <>
      <Button
        variant="outlined"
        size="small"
        startIcon={<BookmarkIcon />}
        onClick={handleOpen}
        sx={{ textTransform: 'none' }}
      >
        Save View
      </Button>

      <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
        <DialogTitle>
          {savedView ? 'View Saved!' : 'Save This View'}
        </DialogTitle>
        <DialogContent>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {savedView ? (
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Your view has been saved. Share this link:
              </Typography>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  p: 1.5,
                  bgcolor: 'action.hover',
                  borderRadius: 1,
                  mt: 1,
                }}
              >
                <Link
                  href={shareUrl}
                  target="_blank"
                  rel="noopener"
                  sx={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}
                >
                  {shareUrl}
                </Link>
                <Tooltip title={copied ? 'Copied!' : 'Copy link'}>
                  <IconButton size="small" onClick={handleCopy}>
                    <ContentCopyIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>
          ) : (
            <>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Save this analysis configuration to share or revisit later.
              </Typography>
              <TextField
                label="View Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                fullWidth
                size="small"
                sx={{ mt: 2 }}
                placeholder="e.g., PyPI FastAPI Analysis"
                autoFocus
              />
              <Box sx={{ mt: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  <strong>Source:</strong> {source}<br />
                  <strong>Query:</strong> {query}<br />
                  <strong>Horizon:</strong> {horizon} days
                  {resample && <><br /><strong>Resample:</strong> {resample}</>}
                  {apply && <><br /><strong>Transforms:</strong> {apply}</>}
                </Typography>
              </Box>
            </>
          )}
        </DialogContent>
        <DialogActions>
          {savedView ? (
            <Button onClick={handleClose}>Done</Button>
          ) : (
            <>
              <Button onClick={handleClose} disabled={loading}>
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                variant="contained"
                disabled={!name.trim() || loading}
                startIcon={loading ? <CircularProgress size={16} /> : undefined}
              >
                {loading ? 'Saving...' : 'Save'}
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>
    </>
  )
}
