import { useState, useEffect } from 'react'
import Button from '@mui/material/Button'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import ListItemText from '@mui/material/ListItemText'
import ListItemIcon from '@mui/material/ListItemIcon'
import Divider from '@mui/material/Divider'
import Typography from '@mui/material/Typography'
import IconButton from '@mui/material/IconButton'
import CircularProgress from '@mui/material/CircularProgress'
import Box from '@mui/material/Box'
import BookmarksIcon from '@mui/icons-material/Bookmarks'
import DeleteIcon from '@mui/icons-material/Delete'
import { fetchViews, deleteView as apiDeleteView } from '../api/client'
import type { SavedViewResponse } from '../api/types'

interface Props {
  onLoadView: (view: SavedViewResponse) => void
}

export function ViewsDropdown({ onLoadView }: Props) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const [views, setViews] = useState<SavedViewResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const open = Boolean(anchorEl)

  const loadViews = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchViews()
      setViews(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load views')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Load views on mount to check if we have any
    loadViews()
  }, [])

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget)
    loadViews()
  }

  const handleClose = () => {
    setAnchorEl(null)
  }

  const handleSelect = (view: SavedViewResponse) => {
    onLoadView(view)
    handleClose()
  }

  const handleDelete = async (e: React.MouseEvent, hashId: string) => {
    e.stopPropagation()
    try {
      await apiDeleteView(hashId)
      setViews((prev) => prev.filter((v) => v.hash_id !== hashId))
    } catch {
      // Silently fail
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    })
  }

  return (
    <>
      <Button
        variant="outlined"
        size="small"
        startIcon={<BookmarksIcon />}
        onClick={handleClick}
        sx={{ textTransform: 'none' }}
      >
        My Views {views.length > 0 && `(${views.length})`}
      </Button>

      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        PaperProps={{
          sx: { minWidth: 280, maxHeight: 400 },
        }}
      >
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
            <CircularProgress size={24} />
          </Box>
        )}

        {error && (
          <MenuItem disabled>
            <Typography variant="body2" color="error">
              {error}
            </Typography>
          </MenuItem>
        )}

        {!loading && !error && views.length === 0 && (
          <MenuItem disabled>
            <Typography variant="body2" color="text.secondary">
              No saved views yet
            </Typography>
          </MenuItem>
        )}

        {!loading && !error && views.length > 0 && (
          <>
            <MenuItem disabled>
              <Typography variant="caption" color="text.secondary">
                Saved Views
              </Typography>
            </MenuItem>
            <Divider />
            {views.map((view) => (
              <MenuItem
                key={view.hash_id}
                onClick={() => handleSelect(view)}
                sx={{ pr: 1 }}
              >
                <ListItemText
                  primary={view.name}
                  secondary={
                    <Typography variant="caption" color="text.secondary">
                      {view.source}:{view.query} • {formatDate(view.created_at)}
                    </Typography>
                  }
                  primaryTypographyProps={{ variant: 'body2' }}
                />
                <ListItemIcon sx={{ minWidth: 'auto', ml: 1 }}>
                  <IconButton
                    size="small"
                    onClick={(e) => handleDelete(e, view.hash_id)}
                    sx={{ opacity: 0.5, '&:hover': { opacity: 1 } }}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </ListItemIcon>
              </MenuItem>
            ))}
          </>
        )}
      </Menu>
    </>
  )
}
