import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Link from '@mui/material/Link'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import Typography from '@mui/material/Typography'
import BookmarkIcon from '@mui/icons-material/Bookmark'
import HistoryIcon from '@mui/icons-material/History'
import { fetchViews } from '../api/client'
import type { SavedViewResponse } from '../api/types'
import type { RecentQuery } from '../recentQueries'

interface Props {
  recent: RecentQuery[]
  onLoadRecent: (entry: RecentQuery) => void
  onLoadView: (view: SavedViewResponse) => void
  onClearRecent: () => void
}

function timeAgo(ts: number): string {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000))
  if (s < 60) return 'just now'
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 48) return `${h}h ago`
  return `${Math.round(h / 24)}d ago`
}

const itemTextProps = {
  slotProps: {
    primary: { variant: 'body2' as const, noWrap: true },
    secondary: { variant: 'caption' as const, noWrap: true },
  },
}

export function RecentAndSavedViews({ recent, onLoadRecent, onLoadView, onClearRecent }: Props) {
  const [views, setViews] = useState<SavedViewResponse[]>([])
  const [viewsLoaded, setViewsLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchViews()
      .then((v) => {
        if (!cancelled) setViews(v)
      })
      .catch(() => {
        // best effort: the section just stays empty
      })
      .finally(() => {
        if (!cancelled) setViewsLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const empty = recent.length === 0 && views.length === 0

  return (
    <Card>
      <CardContent>
        <Typography variant="subtitle2" gutterBottom>
          Recent & saved views
        </Typography>

        {empty && viewsLoaded && (
          <Box sx={{ py: 3, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Nothing here yet. Ask a question above to get started.
            </Typography>
            <Typography variant="caption" color="text.disabled">
              e.g. "fastapi downloads this year" or "bitcoin price last 6 months"
            </Typography>
          </Box>
        )}

        {recent.length > 0 && (
          <>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 1 }}>
              <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
                Recent
              </Typography>
              <Link component="button" type="button" variant="caption" onClick={onClearRecent}>
                Clear
              </Link>
            </Box>
            <List dense disablePadding>
              {recent.map((r) => (
                <ListItemButton
                  key={`${r.source}|${r.query}|${r.resample || ''}|${r.start || ''}|${r.end || ''}|${r.apply || ''}`}
                  onClick={() => onLoadRecent(r)}
                  sx={{ borderRadius: 1, px: 1 }}
                >
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <HistoryIcon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText
                    primary={r.label}
                    secondary={`${r.source}${r.resample ? ` · ${r.resample}` : ''} · ${timeAgo(r.ts)}`}
                    {...itemTextProps}
                  />
                </ListItemButton>
              ))}
            </List>
          </>
        )}

        {views.length > 0 && (
          <>
            <Typography
              variant="caption"
              color="text.secondary"
              display="block"
              sx={{ mt: recent.length > 0 ? 2 : 1, textTransform: 'uppercase', letterSpacing: 0.5 }}
            >
              Saved views
            </Typography>
            <List dense disablePadding>
              {views.map((v) => (
                <ListItemButton key={v.hash_id} onClick={() => onLoadView(v)} sx={{ borderRadius: 1, px: 1 }}>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <BookmarkIcon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText primary={v.name} secondary={`${v.source}:${v.query}`} {...itemTextProps} />
                </ListItemButton>
              ))}
            </List>
          </>
        )}
      </CardContent>
    </Card>
  )
}
