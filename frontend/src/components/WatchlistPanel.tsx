import { useState, useEffect } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Divider from '@mui/material/Divider'
import FormControl from '@mui/material/FormControl'
import FormControlLabel from '@mui/material/FormControlLabel'
import IconButton from '@mui/material/IconButton'
import InputLabel from '@mui/material/InputLabel'
import List from '@mui/material/List'
import ListItem from '@mui/material/ListItem'
import ListItemText from '@mui/material/ListItemText'
import MenuItem from '@mui/material/MenuItem'
import Select from '@mui/material/Select'
import Switch from '@mui/material/Switch'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import RefreshIcon from '@mui/icons-material/Refresh'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import TrendingDownIcon from '@mui/icons-material/TrendingDown'
import TrendingFlatIcon from '@mui/icons-material/TrendingFlat'
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive'
import SendIcon from '@mui/icons-material/Send'
import type {
  DataSourceInfo,
  NotificationConfig,
  NotificationStatus,
  WatchlistItem,
  WatchlistAddRequest,
} from '../api/types'
import {
  fetchWatchlist,
  addToWatchlist,
  checkWatchlist,
  deleteWatchlistItem,
  getNotificationConfig,
  saveNotificationConfig,
  getNotificationStatus,
  testNotification,
} from '../api/client'

interface Props {
  sources: DataSourceInfo[]
  onLoadQuery?: (source: string, query: string) => void
}

export function WatchlistPanel({ sources, onLoadQuery }: Props) {
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [alerts, setAlerts] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [lastChecked, setLastChecked] = useState<string | null>(null)

  // Form state for adding new watch
  const [newName, setNewName] = useState('')
  const [newSource, setNewSource] = useState('')
  const [newQuery, setNewQuery] = useState('')
  const [newThresholdDir, setNewThresholdDir] = useState<'above' | 'below' | ''>('')
  const [newThresholdVal, setNewThresholdVal] = useState('')

  // Notification settings state
  const [webhookUrl, setWebhookUrl] = useState('')
  const [channel, setChannel] = useState('generic')
  const [notifEnabled, setNotifEnabled] = useState(true)
  const [notifStatus, setNotifStatus] = useState<NotificationStatus | null>(null)
  const [notifSaving, setNotifSaving] = useState(false)
  const [notifTesting, setNotifTesting] = useState(false)
  const [notifMsg, setNotifMsg] = useState<string | null>(null)

  const loadWatchlist = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchWatchlist()
      setItems(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load watchlist')
    } finally {
      setLoading(false)
    }
  }

  const loadNotificationConfig = async () => {
    try {
      const cfg = await getNotificationConfig()
      if (cfg) {
        setWebhookUrl(cfg.webhook_url)
        setChannel(cfg.channel)
        setNotifEnabled(cfg.enabled)
      }
    } catch {
      // Config not set yet — that's fine
    }
    try {
      const status = await getNotificationStatus()
      setNotifStatus(status)
    } catch {
      // Ignore
    }
  }

  const handleCheck = async () => {
    setChecking(true)
    setError(null)
    try {
      const response = await checkWatchlist()
      setItems(response.items)
      setAlerts(response.alerts)
      setLastChecked(new Date(response.checked_at).toLocaleTimeString())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to check watchlist')
    } finally {
      setChecking(false)
    }
  }

  const handleAdd = async () => {
    if (!newName || !newSource || !newQuery) return

    const request: WatchlistAddRequest = {
      name: newName,
      source: newSource,
      query: newQuery,
    }
    if (newThresholdDir && newThresholdVal) {
      request.threshold_direction = newThresholdDir
      request.threshold_value = parseFloat(newThresholdVal)
    }

    try {
      const added = await addToWatchlist(request)
      setItems((prev) => [added, ...prev])
      setDialogOpen(false)
      resetForm()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add to watchlist')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteWatchlistItem(id)
      setItems((prev) => prev.filter((item) => item.id !== id))
      setAlerts((prev) => prev.filter((item) => item.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete')
    }
  }

  const handleSaveNotification = async () => {
    if (!webhookUrl) return
    setNotifSaving(true)
    setNotifMsg(null)
    try {
      await saveNotificationConfig({
        webhook_url: webhookUrl,
        channel,
        enabled: notifEnabled,
      })
      setNotifMsg('Notification settings saved')
      const status = await getNotificationStatus()
      setNotifStatus(status)
    } catch (err) {
      setNotifMsg(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setNotifSaving(false)
    }
  }

  const handleTestNotification = async () => {
    setNotifTesting(true)
    setNotifMsg(null)
    try {
      const result = await testNotification()
      setNotifMsg(result.message || 'Test sent successfully')
    } catch (err) {
      setNotifMsg(err instanceof Error ? err.message : 'Test failed')
    } finally {
      setNotifTesting(false)
    }
  }

  const resetForm = () => {
    setNewName('')
    setNewSource('')
    setNewQuery('')
    setNewThresholdDir('')
    setNewThresholdVal('')
  }

  const getTrendIcon = (direction?: string) => {
    switch (direction) {
      case 'rising':
        return <TrendingUpIcon fontSize="small" color="success" />
      case 'falling':
        return <TrendingDownIcon fontSize="small" color="error" />
      case 'stable':
        return <TrendingFlatIcon fontSize="small" color="disabled" />
      default:
        return null
    }
  }

  const formatValue = (value?: number) => {
    if (value === undefined || value === null) return '-'
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
    return value.toFixed(1)
  }

  useEffect(() => {
    loadWatchlist()
    loadNotificationConfig()
  }, [])

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Typography variant="subtitle1" sx={{ flex: 1 }}>
            Watchlist
          </Typography>
          <Button
            size="small"
            startIcon={<RefreshIcon />}
            onClick={handleCheck}
            disabled={checking || items.length === 0}
            sx={{ mr: 1 }}
          >
            {checking ? 'Checking...' : 'Check'}
          </Button>
          <Button
            size="small"
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setDialogOpen(true)}
          >
            Add
          </Button>
        </Box>

        {lastChecked && (
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
            Last checked: {lastChecked}
          </Typography>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {alerts.length > 0 && (
          <Alert
            severity="warning"
            icon={<NotificationsActiveIcon />}
            sx={{ mb: 2 }}
          >
            {alerts.length} alert{alerts.length > 1 ? 's' : ''} triggered!
          </Alert>
        )}

        {loading ? (
          <Box sx={{ textAlign: 'center', py: 3 }}>
            <CircularProgress size={24} />
          </Box>
        ) : items.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
            No trends being watched. Add one to get started.
          </Typography>
        ) : (
          <List dense disablePadding>
            {items.map((item) => (
              <ListItem
                key={item.id}
                sx={{
                  bgcolor: item.triggered ? 'warning.light' : 'transparent',
                  borderRadius: 1,
                  mb: 0.5,
                }}
                secondaryAction={
                  <IconButton
                    edge="end"
                    size="small"
                    onClick={() => handleDelete(item.id)}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                }
              >
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography
                        variant="body2"
                        sx={{
                          cursor: onLoadQuery ? 'pointer' : 'default',
                          '&:hover': onLoadQuery ? { textDecoration: 'underline' } : {},
                        }}
                        onClick={() => onLoadQuery?.(item.source, item.query)}
                      >
                        {item.name}
                      </Typography>
                      {getTrendIcon(item.trend_direction)}
                      {item.triggered && (
                        <Chip
                          label="Alert"
                          size="small"
                          color="warning"
                          sx={{ height: 18, fontSize: '0.65rem' }}
                        />
                      )}
                    </Box>
                  }
                  secondary={
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                      <Chip
                        label={item.source}
                        size="small"
                        variant="outlined"
                        sx={{ height: 18, fontSize: '0.65rem' }}
                      />
                      <Typography variant="caption" color="text.secondary">
                        {formatValue(item.last_value)}
                      </Typography>
                      {item.threshold_direction && item.threshold_value && (
                        <Typography variant="caption" color="text.secondary">
                          ({item.threshold_direction} {formatValue(item.threshold_value)})
                        </Typography>
                      )}
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        )}

        {/* Notification Settings */}
        <Divider sx={{ my: 2 }} />
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Webhook Notifications
        </Typography>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <TextField
            label="Webhook URL"
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
            placeholder="https://hooks.slack.com/services/..."
            size="small"
            fullWidth
          />

          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Channel</InputLabel>
              <Select
                value={channel}
                label="Channel"
                onChange={(e) => setChannel(e.target.value)}
              >
                <MenuItem value="generic">Generic</MenuItem>
                <MenuItem value="slack">Slack</MenuItem>
                <MenuItem value="discord">Discord</MenuItem>
              </Select>
            </FormControl>

            <FormControlLabel
              control={
                <Switch
                  checked={notifEnabled}
                  onChange={(e) => setNotifEnabled(e.target.checked)}
                  size="small"
                />
              }
              label="Enabled"
            />
          </Box>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              size="small"
              variant="outlined"
              onClick={handleSaveNotification}
              disabled={notifSaving || !webhookUrl}
            >
              {notifSaving ? 'Saving...' : 'Save'}
            </Button>
            <Button
              size="small"
              startIcon={<SendIcon />}
              onClick={handleTestNotification}
              disabled={notifTesting || !webhookUrl}
            >
              {notifTesting ? 'Sending...' : 'Test'}
            </Button>
          </Box>

          {notifMsg && (
            <Alert
              severity="info"
              sx={{ py: 0 }}
              onClose={() => setNotifMsg(null)}
            >
              {notifMsg}
            </Alert>
          )}

          {notifStatus && (
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Chip
                label={notifStatus.running ? 'Scheduler running' : 'Scheduler stopped'}
                size="small"
                color={notifStatus.running ? 'success' : 'default'}
                sx={{ height: 20, fontSize: '0.65rem' }}
              />
              {notifStatus.last_check && (
                <Typography variant="caption" color="text.secondary">
                  Last: {new Date(notifStatus.last_check).toLocaleTimeString()}
                </Typography>
              )}
              {notifStatus.next_check && (
                <Typography variant="caption" color="text.secondary">
                  Next: {new Date(notifStatus.next_check).toLocaleTimeString()}
                </Typography>
              )}
            </Box>
          )}
        </Box>

        {/* Add Dialog */}
        <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Add to Watchlist</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
              <TextField
                label="Name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g., Bitcoin Price Alert"
                size="small"
                fullWidth
              />

              <FormControl size="small" fullWidth>
                <InputLabel>Source</InputLabel>
                <Select
                  value={newSource}
                  label="Source"
                  onChange={(e) => setNewSource(e.target.value)}
                >
                  {sources.map((s) => (
                    <MenuItem key={s.name} value={s.name}>
                      {s.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <TextField
                label="Query"
                value={newQuery}
                onChange={(e) => setNewQuery(e.target.value)}
                placeholder="e.g., bitcoin:price"
                size="small"
                fullWidth
              />

              <Typography variant="caption" color="text.secondary">
                Optional: Set a threshold alert
              </Typography>

              <Box sx={{ display: 'flex', gap: 2 }}>
                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel>Direction</InputLabel>
                  <Select
                    value={newThresholdDir}
                    label="Direction"
                    onChange={(e) => setNewThresholdDir(e.target.value as 'above' | 'below' | '')}
                  >
                    <MenuItem value="">None</MenuItem>
                    <MenuItem value="above">Above</MenuItem>
                    <MenuItem value="below">Below</MenuItem>
                  </Select>
                </FormControl>

                <TextField
                  label="Threshold"
                  type="number"
                  value={newThresholdVal}
                  onChange={(e) => setNewThresholdVal(e.target.value)}
                  disabled={!newThresholdDir}
                  size="small"
                  sx={{ flex: 1 }}
                />
              </Box>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              onClick={handleAdd}
              disabled={!newName || !newSource || !newQuery}
            >
              Add
            </Button>
          </DialogActions>
        </Dialog>
      </CardContent>
    </Card>
  )
}
