import { useState, useEffect, useRef, useMemo } from 'react'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import IconButton from '@mui/material/IconButton'
import InputAdornment from '@mui/material/InputAdornment'
import LinearProgress from '@mui/material/LinearProgress'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import SendIcon from '@mui/icons-material/Send'
import ReactMarkdown from 'react-markdown'
import { API_BASE } from '../api/client'
import type { TimeSeries, TrendAnalysis, ForecastComparison, DataContext } from '../api/types'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  source: string
  query: string
  horizon: number
  series?: TimeSeries
  analysis?: TrendAnalysis
  forecast?: ForecastComparison
}

export function InsightPanel({ source, query, horizon, series, analysis, forecast }: Props) {
  const [initialInsight, setInitialInsight] = useState('')
  const [status, setStatus] = useState<
    'idle' | 'loading' | 'streaming' | 'done' | 'unavailable' | 'error'
  >('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [followupStatus, setFollowupStatus] = useState<'idle' | 'streaming'>('idle')
  const eventSourceRef = useRef<EventSource | null>(null)
  const gotDataRef = useRef(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  // Build data context from available data
  const dataContext = useMemo((): DataContext | undefined => {
    if (!series || !analysis) return undefined

    const points = series.points
    if (points.length === 0) return undefined

    const values = points.map((p) => p.value)
    const minVal = Math.min(...values)
    const maxVal = Math.max(...values)
    const meanVal = values.reduce((a, b) => a + b, 0) / values.length

    const recommendedForecast = forecast?.forecasts.find(
      (f) => f.model_name === forecast.recommended_model
    )

    return {
      data_points_count: points.length,
      date_range: `${points[0].date} to ${points[points.length - 1].date}`,
      min_value: minVal,
      max_value: maxVal,
      mean_value: meanVal,
      recent_values: points.slice(-10).map((p) => ({ date: p.date, value: p.value })),
      trend_direction: analysis.trend.direction,
      trend_momentum: analysis.trend.momentum,
      anomaly_count: analysis.anomalies.anomaly_count,
      anomalies: analysis.anomalies.anomalies.map((a) => ({
        date: a.date,
        value: a.value,
        score: a.score,
      })),
      structural_breaks: analysis.structural_breaks.map((b) => ({
        date: b.date,
        method: b.method,
      })),
      seasonality_detected: analysis.seasonality.detected,
      seasonality_period: analysis.seasonality.period_days ?? undefined,
      forecast_horizon: forecast?.horizon,
      forecast_values: recommendedForecast?.points.slice(0, 10).map((p) => ({
        date: p.date,
        value: p.value,
        lower_ci: p.lower_ci,
        upper_ci: p.upper_ci,
      })),
    }
  }, [series, analysis, forecast])

  // Scroll to bottom when messages change
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Load initial insight
  useEffect(() => {
    eventSourceRef.current?.close()
    setInitialInsight('')
    setMessages([])
    setStatus('loading')
    setErrorMsg('')
    gotDataRef.current = false

    const params = new URLSearchParams({
      source,
      query,
      horizon: String(horizon),
    })
    const es = new EventSource(`${API_BASE}/insight?${params}`)
    eventSourceRef.current = es

    es.addEventListener('delta', (e) => {
      gotDataRef.current = true
      setStatus('streaming')
      setInitialInsight((prev) => prev + JSON.parse(e.data))
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
      if (!gotDataRef.current) {
        setStatus('unavailable')
      }
      es.close()
    }

    return () => es.close()
  }, [source, query, horizon])

  const handleSendMessage = async () => {
    if (!input.trim() || followupStatus === 'streaming') return

    const userMessage = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
    setFollowupStatus('streaming')

    // Build conversation for API
    const conversationMessages = [
      ...messages,
      { role: 'user', content: userMessage },
    ]

    try {
      const response = await fetch(`${API_BASE}/insight-followup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source,
          query,
          messages: conversationMessages,
          context_summary: initialInsight,
          data_context: dataContext,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to get response')
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No reader')

      const decoder = new TextDecoder()
      let assistantMessage = ''
      let buffer = ''

      // Add placeholder for assistant message
      setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event: delta')) {
            const dataLine = line.split('\n').find((l) => l.startsWith('data: '))
            if (dataLine) {
              const chunk = JSON.parse(dataLine.slice(6))
              assistantMessage += chunk
              setMessages((prev) => {
                const updated = [...prev]
                updated[updated.length - 1] = {
                  role: 'assistant',
                  content: assistantMessage,
                }
                return updated
              })
            }
          }
        }
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev.slice(0, -1), // Remove placeholder
        { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' },
      ])
    } finally {
      setFollowupStatus('idle')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

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
            <Typography
              variant="caption"
              color="primary"
              sx={{
                '@keyframes pulse': {
                  '0%, 100%': { opacity: 1 },
                  '50%': { opacity: 0.5 },
                },
                animation: 'pulse 1.5s infinite',
              }}
            >
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

        {/* Initial insight */}
        {initialInsight ? (
          <Box
            sx={{
              '& p': { my: 1, lineHeight: 1.7 },
              '& ul, & ol': { pl: 2, my: 1 },
              '& li': { my: 0.5 },
              '& strong': { fontWeight: 600 },
              '& h1, & h2, & h3': { mt: 2, mb: 1 },
              color: 'text.secondary',
              fontSize: '0.875rem',
            }}
          >
            <ReactMarkdown>{initialInsight}</ReactMarkdown>
          </Box>
        ) : (
          <Typography variant="body2" color="text.disabled" fontStyle="italic">
            {status === 'loading' ? 'Connecting to AI...' : 'Waiting for data...'}
          </Typography>
        )}

        {/* Chat messages */}
        {messages.length > 0 && (
          <Box sx={{ mt: 2, borderTop: 1, borderColor: 'divider', pt: 2 }}>
            {messages.map((msg, i) => (
              <Box
                key={i}
                sx={{
                  mb: 1.5,
                  p: 1.5,
                  borderRadius: 1,
                  bgcolor: msg.role === 'user' ? 'primary.main' : 'action.hover',
                  color: msg.role === 'user' ? 'primary.contrastText' : 'text.primary',
                  ml: msg.role === 'user' ? 4 : 0,
                  mr: msg.role === 'assistant' ? 4 : 0,
                }}
              >
                <Typography
                  variant="caption"
                  sx={{
                    fontWeight: 600,
                    display: 'block',
                    mb: 0.5,
                    opacity: 0.8,
                  }}
                >
                  {msg.role === 'user' ? 'You' : 'AI'}
                </Typography>
                {msg.role === 'assistant' ? (
                  <Box
                    sx={{
                      '& p': { my: 0.5, lineHeight: 1.6 },
                      '& ul, & ol': { pl: 2, my: 0.5 },
                      '& li': { my: 0.25 },
                      fontSize: '0.875rem',
                    }}
                  >
                    <ReactMarkdown>{msg.content || '...'}</ReactMarkdown>
                  </Box>
                ) : (
                  <Typography variant="body2">{msg.content}</Typography>
                )}
              </Box>
            ))}
            <div ref={chatEndRef} />
          </Box>
        )}

        {/* Input field - show after initial insight is done */}
        {status === 'done' && (
          <Box sx={{ mt: 2, pt: messages.length === 0 ? 2 : 0, borderTop: messages.length === 0 ? 1 : 0, borderColor: 'divider' }}>
            <TextField
              fullWidth
              size="small"
              placeholder="Ask a follow-up question..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={followupStatus === 'streaming'}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      size="small"
                      onClick={handleSendMessage}
                      disabled={!input.trim() || followupStatus === 'streaming'}
                      color="primary"
                    >
                      <SendIcon fontSize="small" />
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            {followupStatus === 'streaming' && <LinearProgress sx={{ mt: 1 }} />}
          </Box>
        )}
      </CardContent>
    </Card>
  )
}
