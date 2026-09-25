import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, addToWatchlist, fetchWatchlist } from '../../api/client'
import type { WatchlistAddRequest, WatchlistItem } from '../../api/types'
import { WatchlistContext } from './watchlistContext'
import type { WatchlistContextValue, WatchResult } from './watchlistContext'

/**
 * Owns the watchlist for the whole app: the header badge, the drawer and
 * the chart's Watch button all read and write through it.
 */
export function WatchlistProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [loaded, setLoaded] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [highlightId, setHighlightId] = useState<number | null>(null)
  const openQueryRef = useRef<((item: WatchlistItem) => void) | null>(null)

  const refresh = useCallback(async () => {
    try {
      const data = await fetchWatchlist()
      setItems((prev) => {
        // Keep the triggered/message status from the last check in this session
        const byId = new Map(prev.map((p) => [p.id, p]))
        return data.map((d) => {
          const old = byId.get(d.id)
          return old ? { ...d, triggered: old.triggered, alert_message: old.alert_message } : d
        })
      })
    } catch {
      // Badge just stays as it was
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => {
    // Initial load; setState happens after the fetch resolves
    void refresh()
  }, [refresh])

  const find = useCallback(
    (source: string, query: string) => items.find((i) => i.source === source && i.query === query),
    [items],
  )

  const add = useCallback(
    async (request: WatchlistAddRequest): Promise<WatchResult> => {
      try {
        const item = await addToWatchlist(request)
        setItems((prev) => [item, ...prev.filter((p) => p.id !== item.id)])
        return { item, existed: false }
      } catch (err) {
        if (err instanceof ApiError && err.errorCode === 'WATCHLIST_DUPLICATE') {
          const data = await fetchWatchlist()
          setItems(data)
          const item = data.find((i) => i.source === request.source && i.query === request.query)
          if (item) return { item, existed: true }
        }
        throw err
      }
    },
    [],
  )

  const setOpenQueryHandler = useCallback((fn: ((item: WatchlistItem) => void) | null) => {
    openQueryRef.current = fn
  }, [])

  const value = useMemo<WatchlistContextValue>(
    () => ({
      items,
      alertCount: items.filter((i) => i.triggered).length,
      loaded,
      refresh,
      replaceItems: setItems,
      updateItem: (item) =>
        setItems((prev) =>
          prev.map((p) =>
            p.id === item.id ? { ...item, triggered: p.triggered, alert_message: p.alert_message } : p,
          ),
        ),
      removeItem: (id) => setItems((prev) => prev.filter((p) => p.id !== id)),
      add,
      find,
      drawerOpen,
      openDrawer: (id?: number) => {
        setHighlightId(id ?? null)
        setDrawerOpen(true)
      },
      closeDrawer: () => {
        setDrawerOpen(false)
        setHighlightId(null)
      },
      highlightId,
      setOpenQueryHandler,
      openQuery: (item) => {
        openQueryRef.current?.(item)
        setDrawerOpen(false)
      },
    }),
    [items, loaded, refresh, add, find, drawerOpen, highlightId, setOpenQueryHandler],
  )

  return <WatchlistContext.Provider value={value}>{children}</WatchlistContext.Provider>
}
