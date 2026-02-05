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
import type { CompareItem, TimeSeries, TrendAnalysis, DataContext } from '../api/types'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  items: CompareItem[]
  resample?: string
  apply?: string
  seriesList?: TimeSeries[]
  analyses?: TrendAnalysis[]
}

export function CompareInsightPanel({ items, resample, apply, seriesList, analyses }: Props) {
  const [initialInsight, setInitialInsight] = useState('')
  const [status, setStatus] = useState<
    'idle' | 'loading' | 'streaming' | 'done' | 'unavailable' | 'error'
  >('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [followupStatus, setFollowupStatus] = useState<'idle' | 'streaming'>('idle')
  const gotDataRef = useRef(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  // Build data contexts from available data
  const dataContexts = useMemo((): DataContext[] | undefined => {
    if (!seriesList || !analyses || seriesList.length === 0) return undefined

    return seriesList.map((series, i) => {
      const analysis = analyses[i]
      const points = series.points
      if (points.length === 0 || !analysis) {
        return {
          data_points_count: 0,
          date_range: '',
          min_value: 0,
          max_value: 0,
          mean_value: 0,
          recent_values: [],
          trend_direction: 'unknown',
          trend_momentum: 0,
          anomaly_count: 0,
          anomalies: [],
          structural_breaks: [],
          seasonality_detected: false,
        }
      }

      const values = points.map((p) => p.value)
      const minVal = Math.min(...values)
      const maxVal = Math.max(...values)
      const meanVal = values.reduce((a, b) => a + b, 0) / values.length

      return {
        data_points_count: points.length,
        date_range: `${points[0].date} to ${points[points.length - 1].date}`,
        min_value: minVal,
        max_value: maxVal,
        mean_value: meanVal,
        recent_values: points.slice(-5).map((p) => ({ date: p.date, value: p.value })),
        trend_direction: analysis.trend.direction,
        trend_momentum: analysis.trend.momentum,
        anomaly_count: analysis.anomalies.anomaly_count,
        anomalies: analysis.anomalies.anomalies.slice(0, 3).map((a) => ({
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
      }
    })
  }, [seriesList, analyses])

  // Scroll to bottom when messages change
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (items.length < 2) return

    setInitialInsight('')
    setMessages([])
    setStatus('loading')
    setErrorMsg('')
    gotDataRef.current = false

    const controller = new AbortController()

    const fetchStream = async () => {
      try {
        const response = await fetch('/api/compare-insight', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items, resample, apply }),
          signal: controller.signal,
        })

        if (!response.ok) {
          if (response.status === 503) {
            setStatus('unavailable')
            return
          }
          throw new Error(`HTTP ${response.status}`)
        }

        const reader = response.body?.getReader()
        if (!reader) throw new Error('No reader')

        const decoder = new TextDecoder()
        let buffer = ''
        let currentEvent = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          const messages = buffer.split('\n\n')
          buffer = messages.pop() || ''

          for (const message of messages) {
            const lines = message.split('\n')
            for (const line of lines) {
              if (line.startsWith('event: ')) {
                currentEvent = line.slice(7).trim()
              } else if (line.startsWith('data: ')) {
                const dataStr = line.slice(6)
                if (currentEvent === 'delta') {
                  gotDataRef.current = true
                  setStatus('streaming')
                  try {
                    const data = JSON.parse(dataStr)
                    if (typeof data === 'string') {
                      setInitialInsight((prev) => prev + data)
                    }
                  } catch {
                    // Ignore parse errors
                  }
                } else if (currentEvent === 'complete') {
                  setStatus('done')
                } else if (currentEvent === 'error') {
                  setStatus('error')
                  try {
                    setErrorMsg(JSON.parse(dataStr))
                  } catch {
                    setErrorMsg(dataStr)
                  }
                }
              }
            }
          }
        }

        if (buffer.trim()) {
          setStatus('done')
        }
      } catch (err) {
        if (controller.signal.aborted) return
        if (!gotDataRef.current) {
          setStatus('unavailable')
        } else {
          setStatus('error')
          setErrorMsg(err instanceof Error ? err.message : String(err))
        }
      }
    }

    fetchStream()

    return () => {
      controller.abort()
    }
  }, [items, resample, apply])

  const handleSendMessage = async () => {
    if (!input.trim() || followupStatus === 'streaming') return

    const userMessage = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
    setFollowupStatus('streaming')

    const conversationMessages = [
      ...messages,
      { role: 'user', content: userMessage },
    ]

    try {
      const response = await fetch('/api/compare-insight-followup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items,
          messages: conversationMessages,
          context_summary: initialInsight,
          data_contexts: dataContexts,
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
        ...prev.slice(0, -1),
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
      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="subtitle2" gutterBottom>
            AI Comparison
          </Typography>
          <Typography variant="caption" color="text.disabled" fontStyle="italic">
            AI comparison is not available. Configure ANTHROPIC_API_KEY to enable.
          </Typography>
        </CardContent>
      </Card>
    )
  }

  if (status === 'idle' && items.length < 2) {
    return null
  }

  return (
    <Card sx={{ mt: 3 }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography variant="subtitle2">AI Comparison</Typography>
          {status === 'streaming' && (
            <Typography
              variant="caption"
              color="primary"
              sx={{
                '@keyframes pulse': { '0%, 100%': { opacity: 1 }, '50%': { opacity: 0.5 } },
                animation: 'pulse 1.5s infinite',
              }}
            >
              streaming...
            </Typography>
          )}
          {status === 'loading' && (
            <Typography variant="caption" color="text.disabled">
              analyzing...
            </Typography>
          )}
        </Box>

        {(status === 'loading' || status === 'streaming') && <LinearProgress sx={{ mb: 1 }} />}

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
            {status === 'loading' ? 'Analyzing series for comparison...' : 'Waiting...'}
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

        {/* Input field */}
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
