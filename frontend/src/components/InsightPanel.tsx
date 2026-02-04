import { useState, useEffect, useRef } from 'react'

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
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">
          AI Commentary
        </h3>
        <p className="text-xs text-gray-400 italic">
          AI commentary is not available. Configure ANTHROPIC_API_KEY to enable.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">
        AI Commentary
        {status === 'streaming' && (
          <span className="ml-2 text-xs text-blue-500 animate-pulse">
            streaming...
          </span>
        )}
        {status === 'loading' && (
          <span className="ml-2 text-xs text-gray-400">connecting...</span>
        )}
      </h3>
      {status === 'error' && (
        <p className="text-xs text-red-600 mb-2">{errorMsg || 'An error occurred'}</p>
      )}
      <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
        {text || (
          <span className="text-gray-400 italic">
            {status === 'loading' ? 'Connecting to AI...' : 'Waiting for data...'}
          </span>
        )}
      </div>
    </div>
  )
}
