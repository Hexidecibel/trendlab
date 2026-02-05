import { useState, useEffect, useRef } from 'react'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import LinearProgress from '@mui/material/LinearProgress'
import Typography from '@mui/material/Typography'

interface Props {
  source: string
  query: string
  horizon: number
}

export function InsightPanel({ source, query, horizon }: Props) {
  const [text, setText] = useState('')
  const [status, setStatus] = useState<
    'idle' | 'loading' | 'streaming' | 'done' | 'unavailable' | 'error'
  >('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const eventSourceRef = useRef<EventSource | null>(null)
  const gotDataRef = useRef(false)

  useEffect(() => {
    // Close any previous connection
    eventSourceRef.current?.close()
    setText('')
    setStatus('loading')
    setErrorMsg('')
    gotDataRef.current = false

    const params = new URLSearchParams({
      source,
      query,
      horizon: String(horizon),
    })
    const es = new EventSource(`/api/insight?${params}`)
    eventSourceRef.current = es

    es.addEventListener('delta', (e) => {
      gotDataRef.current = true
      setStatus('streaming')
      setText((prev) => prev + JSON.parse(e.data))
    })

    es.addEventListener('complete', () => {
      setStatus('done')
      es.close()
    })

    es.addEventListener('error', (e) => {
      if (e instanceof MessageEvent && e.data) {
        setErrorMsg(JSON.parse(e.data))
      }
      setStatus('error')
      es.close()
    })

    es.onerror = () => {
      // Connection failed entirely (503, network error, etc.)
      if (!gotDataRef.current) {
        setStatus('unavailable')
      }
      es.close()
    }

    return () => es.close()
  }, [source, query, horizon])

  if (status === 'unavailable') {
    return (
      <Card>
        <CardContent>
          <Typography variant="subtitle2" gutterBottom>
            AI Commentary
          </Typography>
          <Typography variant="caption" color="text.disabled" fontStyle="italic">
            AI commentary is not available. Configure ANTHROPIC_API_KEY to enable.
          </Typography>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography variant="subtitle2">AI Commentary</Typography>
          {status === 'streaming' && (
            <Typography variant="caption" color="primary" sx={{ '@keyframes pulse': { '0%, 100%': { opacity: 1 }, '50%': { opacity: 0.5 } }, animation: 'pulse 1.5s infinite' }}>
              streaming...
            </Typography>
          )}
          {status === 'loading' && (
            <Typography variant="caption" color="text.disabled">
              connecting...
            </Typography>
          )}
        </Box>
        {(status === 'loading' || status === 'streaming') && (
          <LinearProgress sx={{ mb: 1 }} />
        )}
        {status === 'error' && (
          <Typography variant="caption" color="error" display="block" sx={{ mb: 1 }}>
            {errorMsg || 'An error occurred'}
          </Typography>
        )}
        <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
          {text || (
            <Typography component="span" variant="body2" color="text.disabled" fontStyle="italic">
              {status === 'loading' ? 'Connecting to AI...' : 'Waiting for data...'}
            </Typography>
          )}
        </Typography>
      </CardContent>
    </Card>
  )
}
