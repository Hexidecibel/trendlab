import { useState, useEffect } from 'react'

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

/**
 * Subscribe to server progress events for `requestId` (sent to the API as
 * the `X-Request-ID` header, so the server publishes under the same id).
 * The server holds events emitted before we subscribe, so a late connect
 * still sees the early stages.
 */
export function useWebSocket(requestId: string | null): ProgressState {
  // Progress is stored with the request it belongs to, so a new request id
  // reads as INITIAL without resetting state inside the effect.
  const [state, setState] = useState<ProgressState & { rid: string | null }>({
    ...INITIAL,
    rid: null,
  })

  useEffect(() => {
    if (!requestId) return

    let ws: WebSocket | null = null
    let retries = 0
    let done = false
    let retryTimer: ReturnType<typeof setTimeout> | null = null

    const update = (patch: Partial<ProgressState>) =>
      setState((prev) =>
        prev.rid === requestId
          ? { ...prev, ...patch }
          : { ...INITIAL, ...patch, rid: requestId },
      )

    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      ws = new WebSocket(`${proto}//${window.location.host}/api/ws/progress`)
      const sock = ws

      sock.onopen = () => {
        update({ connected: true })
        sock.send(JSON.stringify({ request_id: requestId }))
      }

      sock.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.stage === 'heartbeat') return
          update({
            stage: data.stage,
            progress: data.progress,
            message: data.message,
            connected: true,
          })
          if (data.stage === 'complete') {
            done = true
            sock.close()
          }
        } catch {
          // Ignore malformed messages
        }
      }

      sock.onclose = () => {
        if (done) return
        update({ connected: false })
        if (retries < MAX_RETRIES) {
          retries += 1
          retryTimer = setTimeout(connect, retries * 1000)
        }
      }
    }

    connect()

    return () => {
      done = true
      if (retryTimer) clearTimeout(retryTimer)
      ws?.close()
    }
  }, [requestId])

  if (!requestId || state.rid !== requestId) return INITIAL
  return state
}
