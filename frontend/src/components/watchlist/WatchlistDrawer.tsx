import { useState } from 'react'
import Accordion from '@mui/material/Accordion'
import AccordionDetails from '@mui/material/AccordionDetails'
import AccordionSummary from '@mui/material/AccordionSummary'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Collapse from '@mui/material/Collapse'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Divider from '@mui/material/Divider'
import Drawer from '@mui/material/Drawer'
import FormControl from '@mui/material/FormControl'
import FormControlLabel from '@mui/material/FormControlLabel'
import IconButton from '@mui/material/IconButton'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import Select from '@mui/material/Select'
import Switch from '@mui/material/Switch'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import AddIcon from '@mui/icons-material/Add'
import CloseIcon from '@mui/icons-material/Close'
import DeleteIcon from '@mui/icons-material/DeleteOutline'
import EditNotificationsIcon from '@mui/icons-material/EditNotifications'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive'
import RefreshIcon from '@mui/icons-material/Refresh'
import SendIcon from '@mui/icons-material/Send'
import TrendingDownIcon from '@mui/icons-material/TrendingDown'
import TrendingFlatIcon from '@mui/icons-material/TrendingFlat'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import {
  checkWatchlist,
  deleteWatchlistItem,
  getNotificationConfig,
  getNotificationStatus,
  saveNotificationConfig,
  testNotification,
  updateWatchlistItem,
} from '../../api/client'
import type { DataSourceInfo, NotificationStatus, WatchlistItem } from '../../api/types'
import { formatCompact } from '../../utils/format'
import { formatSlope } from '../../smoothing'
import { AlertFields } from './AlertFields'
import { draftFromItem, draftIsValid, draftToRequest } from './alertDraft'
import type { AlertDraft } from './alertDraft'
import { describeAlert, useWatchlist } from './watchlistContext'

function TrendIcon({ direction }: { direction?: string | null }) {
  switch (direction) {
    case 'rising':
      return <TrendingUpIcon fontSize="small" color="success" titleAccess="rising" />
    case 'falling':
      return <TrendingDownIcon fontSize="small" color="error" titleAccess="falling" />
    case 'stable':
      return <TrendingFlatIcon fontSize="small" color="disabled" titleAccess="stable" />
    default:
      return null
  }
}

function WatchRow({ item, highlighted }: { item: WatchlistItem; highlighted: boolean }) {
  const { updateItem, removeItem, openQuery } = useWatchlist()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<AlertDraft>(() => draftFromItem(item))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      updateItem(await updateWatchlistItem(item.id, draftToRequest(draft)))
      setEditing(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the alert')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    try {
      await deleteWatchlistItem(item.id)
      removeItem(item.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove it')
    }
  }

  const slope = formatSlope(item.last_slope)
  return (
    <Box
      data-testid="watch-row"
      sx={{
        p: 1.25,
        mb: 1,
        borderRadius: 2,
        border: 1,
        borderColor: highlighted ? 'primary.main' : item.triggered ? 'warning.main' : 'divider',
        bgcolor: highlighted ? 'action.selected' : 'transparent',
        transition: 'background-color 0.4s',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <Typography
          variant="body2"
          fontWeight={600}
          role="button"
          tabIndex={0}
          onClick={() => openQuery(item)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') openQuery(item)
          }}
          sx={{ cursor: 'pointer', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', '&:hover': { textDecoration: 'underline' } }}
          title="Open this chart"
        >
          {item.name}
        </Typography>
        <TrendIcon direction={item.trend_direction ?? item.last_direction} />
        <Tooltip title="Change alert">
          <IconButton size="small" onClick={() => setEditing((v) => !v)} aria-label="Change alert">
            <EditNotificationsIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Stop watching">
          <IconButton size="small" onClick={handleDelete} aria-label="Stop watching">
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mt: 0.25 }}>
        <Chip label={item.source} size="small" variant="outlined" sx={{ height: 18, fontSize: '0.65rem' }} />
        {item.resample && (
          <Chip label={item.resample} size="small" variant="outlined" sx={{ height: 18, fontSize: '0.65rem' }} />
        )}
        {item.last_value != null && (
          <Typography variant="caption" color="text.secondary">
            {formatCompact(item.last_value)}
          </Typography>
        )}
        {slope && (
          <Typography variant="caption" color="text.secondary">
            · {slope}
          </Typography>
        )}
      </Box>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.25 }}>
        {describeAlert(item, formatCompact)}
      </Typography>
      {item.triggered && item.alert_message && (
        <Alert severity="warning" icon={<NotificationsActiveIcon fontSize="small" />} sx={{ mt: 0.75, py: 0 }}>
          {item.alert_message}
        </Alert>
      )}
      <Collapse in={editing} unmountOnExit>
        <Box sx={{ mt: 1.25 }}>
          <AlertFields value={draft} onChange={setDraft} />
          <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
            <Button size="small" variant="contained" onClick={handleSave} disabled={saving || !draftIsValid(draft)}>
              {saving ? 'Saving…' : 'Save alert'}
            </Button>
            <Button size="small" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </Box>
        </Box>
      </Collapse>
      {error && (
        <Alert severity="error" sx={{ mt: 1, py: 0 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
    </Box>
  )
}

function AddWatchDialog({ open, onClose, sources }: { open: boolean; onClose: () => void; sources: DataSourceInfo[] }) {
  const { add, openDrawer } = useWatchlist()
  const [name, setName] = useState('')
  const [source, setSource] = useState('')
  const [query, setQuery] = useState('')
  const [draft, setDraft] = useState<AlertDraft>({ choice: 'trend_flip', amount: '' })
  const [error, setError] = useState<string | null>(null)

  const handleAdd = async () => {
    const alert = draftToRequest(draft)
    try {
      const { item } = await add({
        name: name || `${source}: ${query}`,
        source,
        query,
        alert_type: alert.alert_type ?? null,
        threshold_direction: alert.threshold_direction ?? undefined,
        threshold_value: alert.threshold_value ?? undefined,
        slope_threshold: alert.slope_threshold ?? undefined,
      })
      openDrawer(item.id)
      onClose()
      setName('')
      setQuery('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add it')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Watch a query</DialogTitle>
      <DialogContent>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
          Easier: load a chart and press the Watch button next to Save view.
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <FormControl size="small" fullWidth>
            <InputLabel>Source</InputLabel>
            <Select value={source} label="Source" onChange={(e) => setSource(e.target.value)}>
              {sources.map((s) => (
                <MenuItem key={s.name} value={s.name}>
                  {s.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField size="small" label="Query" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. requests" fullWidth />
          <TextField size="small" label="Name (optional)" value={name} onChange={(e) => setName(e.target.value)} fullWidth />
          <AlertFields value={draft} onChange={setDraft} />
          {error && <Alert severity="error">{error}</Alert>}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={handleAdd} disabled={!source || !query || !draftIsValid(draft)}>
          Watch
        </Button>
      </DialogActions>
    </Dialog>
  )
}

function WebhookSettings() {
  const [loaded, setLoaded] = useState(false)
  const [webhookUrl, setWebhookUrl] = useState('')
  const [channel, setChannel] = useState('generic')
  const [enabled, setEnabled] = useState(true)
  const [status, setStatus] = useState<NotificationStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const load = async () => {
    if (loaded) return
    setLoaded(true)
    try {
      const cfg = await getNotificationConfig()
      if (cfg) {
        setWebhookUrl(cfg.webhook_url)
        setChannel(cfg.channel)
        setEnabled(cfg.enabled)
      }
    } catch {
      // not configured yet
    }
    try {
      setStatus(await getNotificationStatus())
    } catch {
      // ignore
    }
  }

  const run = async (fn: () => Promise<string>) => {
    setBusy(true)
    setMsg(null)
    try {
      setMsg(await fn())
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Accordion
      disableGutters
      elevation={0}
      onChange={(_, expanded) => {
        if (expanded) void load()
      }}
      sx={{ bgcolor: 'transparent', '&:before': { display: 'none' } }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 0 }}>
        <Typography variant="subtitle2">Webhook notifications</Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ px: 0, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <Typography variant="caption" color="text.secondary">
          Alerts are checked in the background and posted here (Slack, Discord or any URL).
        </Typography>
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
            <Select value={channel} label="Channel" onChange={(e) => setChannel(e.target.value)}>
              <MenuItem value="generic">Generic</MenuItem>
              <MenuItem value="slack">Slack</MenuItem>
              <MenuItem value="discord">Discord</MenuItem>
            </Select>
          </FormControl>
          <FormControlLabel
            control={<Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} size="small" />}
            label="Enabled"
          />
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            size="small"
            variant="outlined"
            disabled={busy || !webhookUrl}
            onClick={() =>
              run(async () => {
                await saveNotificationConfig({ webhook_url: webhookUrl, channel, enabled })
                setStatus(await getNotificationStatus())
                return 'Notification settings saved'
              })
            }
          >
            Save
          </Button>
          <Button
            size="small"
            startIcon={<SendIcon />}
            disabled={busy || !webhookUrl}
            onClick={() => run(async () => (await testNotification()).message || 'Test sent')}
          >
            Test
          </Button>
        </Box>
        {msg && (
          <Alert severity="info" sx={{ py: 0 }} onClose={() => setMsg(null)}>
            {msg}
          </Alert>
        )}
        {status && (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
            <Chip
              label={status.running ? 'Scheduler running' : 'Scheduler stopped'}
              size="small"
              color={status.running ? 'success' : 'default'}
              sx={{ height: 20, fontSize: '0.65rem' }}
            />
            {status.next_check && (
              <Typography variant="caption" color="text.secondary">
                Next check {new Date(status.next_check).toLocaleTimeString()}
              </Typography>
            )}
          </Box>
        )}
      </AccordionDetails>
    </Accordion>
  )
}

export function WatchlistDrawer({ sources }: { sources: DataSourceInfo[] }) {
  const { items, drawerOpen, closeDrawer, highlightId, replaceItems, alertCount } = useWatchlist()
  const [checking, setChecking] = useState(false)
  const [lastChecked, setLastChecked] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [addOpen, setAddOpen] = useState(false)

  const handleCheck = async () => {
    setChecking(true)
    setError(null)
    try {
      const res = await checkWatchlist()
      replaceItems(res.items)
      setLastChecked(new Date(res.checked_at).toLocaleTimeString())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Check failed')
    } finally {
      setChecking(false)
    }
  }

  return (
    <Drawer
      anchor="right"
      open={drawerOpen}
      onClose={closeDrawer}
      slotProps={{ paper: { sx: { width: { xs: '100%', sm: 420 }, maxWidth: '100vw' } } }}
    >
      <Box sx={{ p: 2 }} data-testid="watchlist-drawer">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography variant="h6" sx={{ flex: 1 }}>
            Watchlist
          </Typography>
          <Tooltip title="Close">
            <IconButton onClick={closeDrawer} aria-label="Close watchlist">
              <CloseIcon />
            </IconButton>
          </Tooltip>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1.5 }}>
          <Button
            size="small"
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={handleCheck}
            disabled={checking || items.length === 0}
          >
            {checking ? 'Checking…' : 'Check now'}
          </Button>
          <Button size="small" startIcon={<AddIcon />} onClick={() => setAddOpen(true)}>
            Add
          </Button>
          {lastChecked && (
            <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
              Checked {lastChecked}
            </Typography>
          )}
        </Box>
        {error && (
          <Alert severity="error" sx={{ mb: 1.5 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        {alertCount > 0 && (
          <Alert severity="warning" icon={<NotificationsActiveIcon />} sx={{ mb: 1.5 }}>
            {alertCount} alert{alertCount > 1 ? 's' : ''} fired on the last check
          </Alert>
        )}
        {items.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>
            Nothing watched yet. Load a chart and press <strong>Watch</strong> to get told when its trend changes.
          </Typography>
        ) : (
          items.map((item) => <WatchRow key={item.id} item={item} highlighted={item.id === highlightId} />)
        )}
        <Divider sx={{ my: 1.5 }} />
        <WebhookSettings />
      </Box>
      <AddWatchDialog open={addOpen} onClose={() => setAddOpen(false)} sources={sources} />
    </Drawer>
  )
}
