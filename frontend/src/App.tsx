import { useState, useMemo, useEffect } from 'react'
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material'
import AppBar from '@mui/material/AppBar'
import Box from '@mui/material/Box'
import Container from '@mui/material/Container'
import IconButton from '@mui/material/IconButton'
import Toolbar from '@mui/material/Toolbar'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import LightModeIcon from '@mui/icons-material/LightMode'
import { Dashboard } from './components/Dashboard'
import { LockScreen } from './components/LockScreen'

const getTheme = (mode: 'light' | 'dark') =>
  createTheme({
    palette: {
      mode,
      primary: { main: '#6366f1' },  // Indigo
      secondary: { main: '#f97316' }, // Orange
      ...(mode === 'dark'
        ? {
            background: {
              default: '#0f172a',  // Slate 900
              paper: '#1e293b',    // Slate 800
            },
          }
        : {
            background: {
              default: '#f1f5f9',  // Slate 100
              paper: '#ffffff',
            },
          }),
    },
    typography: {
      fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    },
    components: {
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: 12,
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            textTransform: 'none',
            fontWeight: 600,
          },
        },
      },
    },
  })

export default function App() {
  const [mode, setMode] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('theme')
    return (saved as 'light' | 'dark') || 'dark'
  })
  const [authState, setAuthState] = useState<'checking' | 'locked' | 'unlocked'>('checking')

  const theme = useMemo(() => getTheme(mode), [mode])

  // Check auth status on load
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await fetch('/api/auth-status')
        const data = await response.json()

        if (!data.auth_required) {
          setAuthState('unlocked')
          return
        }

        // Auth required - check if we have a valid session
        // Try to hit a protected endpoint to verify cookie
        const testResponse = await fetch('/api/sources')
        if (testResponse.ok) {
          setAuthState('unlocked')
        } else {
          setAuthState('locked')
        }
      } catch {
        // If auth-status fails, assume locked
        setAuthState('locked')
      }
    }

    checkAuth()
  }, [])

  const toggleTheme = () => {
    const newMode = mode === 'light' ? 'dark' : 'light'
    setMode(newMode)
    localStorage.setItem('theme', newMode)
  }

  // Show nothing while checking
  if (authState === 'checking') {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
      </ThemeProvider>
    )
  }

  // Show lock screen
  if (authState === 'locked') {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <LockScreen onUnlock={() => setAuthState('unlocked')} />
      </ThemeProvider>
    )
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppBar
        position="static"
        color="default"
        elevation={0}
        sx={{
          borderBottom: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        <Toolbar>
          <Box sx={{ flexGrow: 1 }}>
            <Typography
              variant="h5"
              fontWeight={700}
              sx={{
                background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              TrendLab
            </Typography>
            <Typography variant="caption" color="text.secondary">
              AI-powered trend analysis and forecasting
            </Typography>
          </Box>
          <Tooltip title={mode === 'dark' ? 'Light mode' : 'Dark mode'}>
            <IconButton onClick={toggleTheme} color="inherit">
              {mode === 'dark' ? <LightModeIcon /> : <DarkModeIcon />}
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>
      <Container maxWidth="xl" sx={{ py: 3 }}>
        <Dashboard />
      </Container>
    </ThemeProvider>
  )
}
