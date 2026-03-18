import { useState, useEffect } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Grid from '@mui/material/Grid'
import Typography from '@mui/material/Typography'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ErrorIcon from '@mui/icons-material/Error'
import WarningIcon from '@mui/icons-material/Warning'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import RefreshIcon from '@mui/icons-material/Refresh'
import { fetchPlugins, reloadPlugins } from '../api/client'
import type { PluginInfo } from '../api/types'

const statusConfig: Record<string, {
  color: 'success' | 'warning' | 'error' | 'default'
  icon: React.ReactNode
  label: string
}> = {
  active: {
    color: 'success',
    icon: <CheckCircleIcon fontSize="small" />,
    label: 'Active',
  },
  missing_deps: {
    color: 'warning',
    icon: <WarningIcon fontSize="small" />,
    label: 'Missing Deps',
  },
  error: {
    color: 'error',
    icon: <ErrorIcon fontSize="small" />,
    label: 'Error',
  },
  no_manifest: {
    color: 'default',
    icon: <HelpOutlineIcon fontSize="small" />,
    label: 'No Manifest',
  },
}

export function PluginsPage() {
  const [plugins, setPlugins] = useState<PluginInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [reloading, setReloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadPlugins = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchPlugins()
      setPlugins(data)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load plugins'
      )
    } finally {
      setLoading(false)
    }
  }

  const handleReload = async () => {
    try {
      setReloading(true)
      setError(null)
      const data = await reloadPlugins()
      setPlugins(data)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to reload plugins'
      )
    } finally {
      setReloading(false)
    }
  }

  useEffect(() => {
    loadPlugins()
  }, [])

  const activeCount = plugins.filter(
    (p) => p.status === 'active'
  ).length

  if (loading) {
    return (
      <Box sx={{ textAlign: 'center', py: 6 }}>
        <CircularProgress size={32} />
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mt: 2 }}
        >
          Scanning plugins...
        </Typography>
      </Box>
    )
  }

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 3,
        }}
      >
        <Typography variant="body2" color="text.secondary">
          {activeCount} active / {plugins.length} total plugins
        </Typography>
        <Button
          variant="outlined"
          size="small"
          startIcon={<RefreshIcon />}
          onClick={handleReload}
          disabled={reloading}
        >
          {reloading ? 'Reloading...' : 'Reload Plugins'}
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {plugins.length === 0 && !error && (
        <Alert severity="info">
          No plugins found. Add .py files or directories to the
          plugins/ folder.
        </Alert>
      )}

      <Grid container spacing={2}>
        {plugins.map((plugin) => {
          const cfg = statusConfig[plugin.status] ||
            statusConfig.no_manifest
          return (
            <Grid item xs={12} sm={6} md={4} key={plugin.name}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardContent>
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      mb: 1,
                    }}
                  >
                    <Typography variant="h6" fontWeight={600}>
                      {plugin.name}
                    </Typography>
                    <Chip
                      icon={cfg.icon}
                      label={cfg.label}
                      color={cfg.color}
                      size="small"
                      variant="outlined"
                    />
                  </Box>

                  {plugin.version && (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                    >
                      v{plugin.version}
                      {plugin.author && ` by ${plugin.author}`}
                    </Typography>
                  )}

                  {plugin.description && (
                    <Typography
                      variant="body2"
                      sx={{ mt: 1 }}
                      color="text.secondary"
                    >
                      {plugin.description}
                    </Typography>
                  )}

                  {plugin.error_message && (
                    <Alert
                      severity={
                        plugin.status === 'missing_deps'
                          ? 'warning'
                          : 'error'
                      }
                      sx={{ mt: 1 }}
                    >
                      {plugin.error_message}
                    </Alert>
                  )}

                  {plugin.required_env_vars.length > 0 && (
                    <Box sx={{ mt: 1 }}>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                      >
                        Required env vars:
                      </Typography>
                      <Box
                        sx={{
                          display: 'flex',
                          flexWrap: 'wrap',
                          gap: 0.5,
                          mt: 0.5,
                        }}
                      >
                        {plugin.required_env_vars.map((v) => (
                          <Chip
                            key={v}
                            label={v}
                            size="small"
                            variant="outlined"
                            color={
                              plugin.status === 'missing_deps'
                                ? 'warning'
                                : 'default'
                            }
                          />
                        ))}
                      </Box>
                    </Box>
                  )}

                  {plugin.has_readme && (
                    <Typography
                      variant="caption"
                      color="primary"
                      sx={{ mt: 1, display: 'block' }}
                    >
                      README available
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
          )
        })}
      </Grid>
    </Box>
  )
}
