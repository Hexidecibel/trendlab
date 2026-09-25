import Badge from '@mui/material/Badge'
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import NotificationsIcon from '@mui/icons-material/NotificationsNone'
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive'
import { useWatchlist } from './watchlistContext'

/** Header icon: badge = number of watches (alerts that fired, in orange). */
export function WatchlistHeaderButton() {
  const { items, alertCount, openDrawer } = useWatchlist()
  const label =
    alertCount > 0
      ? `Watchlist: ${alertCount} alert${alertCount > 1 ? 's' : ''}`
      : `Watchlist (${items.length})`
  return (
    <Tooltip title={label}>
      <IconButton color="inherit" onClick={() => openDrawer()} aria-label={label} data-testid="watchlist-header-button">
        <Badge
          badgeContent={alertCount > 0 ? alertCount : items.length}
          color={alertCount > 0 ? 'warning' : 'primary'}
          max={99}
        >
          {alertCount > 0 ? <NotificationsActiveIcon /> : <NotificationsIcon />}
        </Badge>
      </IconButton>
    </Tooltip>
  )
}
