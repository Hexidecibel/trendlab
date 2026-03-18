import Alert from '@mui/material/Alert'
import AlertTitle from '@mui/material/AlertTitle'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Typography from '@mui/material/Typography'
import { ApiError } from '../api/client'

interface ErrorAlertProps {
  error: string | ApiError
  sx?: Record<string, unknown>
}

export function ErrorAlert({ error, sx }: ErrorAlertProps) {
  if (typeof error === 'string') {
    return (
      <Alert severity="error" sx={{ mb: 3, ...sx }}>
        {error}
      </Alert>
    )
  }

  return (
    <Alert severity="error" sx={{ mb: 3, ...sx }}>
      <AlertTitle>{error.message}</AlertTitle>
      {error.hint && (
        <Typography variant="body2" sx={{ opacity: 0.85, mt: 0.5 }}>
          {error.hint}
        </Typography>
      )}
      {error.requestId && (
        <Box sx={{ mt: 1 }}>
          <Chip
            label={`Request ID: ${error.requestId}`}
            size="small"
            variant="outlined"
            sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}
          />
        </Box>
      )}
    </Alert>
  )
}
