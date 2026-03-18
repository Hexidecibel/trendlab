import { useState, useEffect, useRef, useCallback } from 'react'

export interface ProgressState {
  stage: string
  progress: number
  message: string
  connected: boolean
}

const INITIAL: ProgressState = {
  stage: '',
  progress: 0,
  message: '',
  connected: false,
}

const MAX_RETRIES = 3

export function useWebSocket(requestId: string | null): ProgressState {
  const [state, setState] = useState<ProgressState>(INITIAL)
  const wsRef = useRef<WebSocket | null>(null)
  const retriesRef = useRef(0)

  const cleanup = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!requestId) {
      setState(INITIAL)
      return
    }

    retriesRef.current = 0

    const connect = () => {
      cleanup()

      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${proto}//${window.location.host}/api/ws/progress`)
      wsRef.current = ws

      ws.onopen = () => {
        setState((prev) => ({ ...prev, connected: true }))
        ws.send(JSON.stringify({ request_id: requestId }))
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.stage === 'heartbeat') return
          setState({
            stage: data.stage,
            progress: data.progress,
            message: data.message,
            connected: true,
          })
          if (data.stage === 'complete') {
            ws.close()
          }
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onerror = () => {
        // Will trigger onclose
      }

      ws.onclose = () => {
        setState((prev) => ({ ...prev, connected: false }))
        if (retriesRef.current < MAX_RETRIES) {
          retriesRef.current += 1
          const delay = retriesRef.current * 1000
          setTimeout(connect, delay)
        }
      }
    }

    connect()

    return cleanup
  }, [requestId, cleanup])

  return state
}
