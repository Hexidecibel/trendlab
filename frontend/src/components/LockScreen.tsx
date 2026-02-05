import { useState } from 'react'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Container from '@mui/material/Container'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import InputAdornment from '@mui/material/InputAdornment'
import Chip from '@mui/material/Chip'
import SearchIcon from '@mui/icons-material/Search'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import ShowChartIcon from '@mui/icons-material/ShowChart'
import AutoGraphIcon from '@mui/icons-material/AutoGraph'

interface Props {
  onUnlock: () => void
}

export function LockScreen({ onUnlock }: Props) {
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    setLoading(true)
    setError('')

    try {
      const response = await fetch('/api/unlock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phrase: input.trim() }),
      })

      if (response.ok) {
        localStorage.setItem('trendlab_unlocked', 'true')
        onUnlock()
      } else {
        setError('No results found. Try a different search.')
        setInput('')
      }
    } catch {
      setError('Search unavailable. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const features = [
    { icon: <TrendingUpIcon />, label: 'Trend Analysis' },
    { icon: <ShowChartIcon />, label: 'Forecasting' },
    { icon: <AutoGraphIcon />, label: 'AI Insights' },
  ]

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: (theme) =>
          theme.palette.mode === 'dark'
            ? 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)'
            : 'linear-gradient(135deg, #f1f5f9 0%, #e0e7ff 50%, #f1f5f9 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
      }}
    >
      {/* Animated background orbs */}
      <Box
        sx={{
          position: 'fixed',
          top: '20%',
          left: '10%',
          width: 300,
          height: 300,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%)',
          filter: 'blur(40px)',
          animation: 'float 8s ease-in-out infinite',
          '@keyframes float': {
            '0%, 100%': { transform: 'translateY(0) scale(1)' },
            '50%': { transform: 'translateY(-20px) scale(1.1)' },
          },
        }}
      />
      <Box
        sx={{
          position: 'fixed',
          bottom: '20%',
          right: '10%',
          width: 250,
          height: 250,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(168,85,247,0.15) 0%, transparent 70%)',
          filter: 'blur(40px)',
          animation: 'float 10s ease-in-out infinite reverse',
        }}
      />

      <Container maxWidth="sm">
        <Card
          elevation={0}
          sx={{
            borderRadius: 4,
            backdropFilter: 'blur(20px)',
            bgcolor: (theme) =>
              theme.palette.mode === 'dark'
                ? 'rgba(30, 41, 59, 0.8)'
                : 'rgba(255, 255, 255, 0.9)',
            border: 1,
            borderColor: 'divider',
          }}
        >
          <CardContent sx={{ p: 4 }}>
            <Box sx={{ textAlign: 'center', mb: 4 }}>
              <Typography
                variant="h3"
                fontWeight={800}
                sx={{
                  background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%)',
                  backgroundClip: 'text',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  mb: 1,
                }}
              >
                TrendLab
              </Typography>
              <Typography variant="body1" color="text.secondary">
                AI-powered trend analysis and forecasting
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1, mb: 4 }}>
              {features.map((f) => (
                <Chip
                  key={f.label}
                  icon={f.icon}
                  label={f.label}
                  size="small"
                  variant="outlined"
                  sx={{
                    borderColor: 'primary.main',
                    color: 'primary.main',
                    '& .MuiChip-icon': { color: 'primary.main' },
                  }}
                />
              ))}
            </Box>

            <Box component="form" onSubmit={handleSubmit}>
              <TextField
                fullWidth
                placeholder="What would you like to explore?"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={loading}
                error={!!error}
                helperText={error}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon color="action" />
                    </InputAdornment>
                  ),
                }}
                sx={{
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 3,
                    bgcolor: 'background.paper',
                    '&:hover': {
                      boxShadow: '0 0 0 2px rgba(99, 102, 241, 0.2)',
                    },
                    '&.Mui-focused': {
                      boxShadow: '0 0 0 3px rgba(99, 102, 241, 0.3)',
                    },
                  },
                }}
              />
            </Box>

            <Box sx={{ mt: 4, textAlign: 'center' }}>
              <Typography variant="caption" color="text.disabled">
                Explore trends in Python packages, crypto, sports, weather, and more
              </Typography>
            </Box>
          </CardContent>
        </Card>
      </Container>
    </Box>
  )
}
