import { createContext, useContext } from 'react'
import type { WatchlistAddRequest, WatchlistItem } from '../../api/types'

export interface WatchResult {
  item: WatchlistItem
  /** True when the query was already on the watchlist (nothing was added). */
  existed: boolean
}

export interface WatchlistContextValue {
  items: WatchlistItem[]
  /** Items whose alert fired on the most recent check. */
  alertCount: number
  loaded: boolean
  refresh: () => Promise<void>
  /** Replace the list (e.g. with the result of a check, which carries alert status). */
  replaceItems: (items: WatchlistItem[]) => void
  /** Swap in an edited item, keeping its alert status from the last check. */
  updateItem: (item: WatchlistItem) => void
  removeItem: (id: number) => void
  /** Add a watch; an already-watched source/query resolves to the existing item. */
  add: (request: WatchlistAddRequest) => Promise<WatchResult>
  /** The watch for a source/query, if any. */
  find: (source: string, query: string) => WatchlistItem | undefined
  drawerOpen: boolean
  openDrawer: (highlightId?: number) => void
  closeDrawer: () => void
  highlightId: number | null
  /** Called when the user opens a watched query from the drawer. */
  setOpenQueryHandler: (fn: ((item: WatchlistItem) => void) | null) => void
  openQuery: (item: WatchlistItem) => void
}

export const WatchlistContext = createContext<WatchlistContextValue | null>(null)

export function useWatchlist(): WatchlistContextValue {
  const ctx = useContext(WatchlistContext)
  if (!ctx) throw new Error('useWatchlist must be used inside <WatchlistProvider>')
  return ctx
}

/** "Alert when the trend flips" style description of a watch's alert. */
export function describeAlert(item: Pick<WatchlistItem, 'alert_type' | 'threshold_direction' | 'threshold_value' | 'slope_threshold'>, fmt: (v: number) => string): string {
  const type = item.alert_type ?? (item.threshold_direction ? 'threshold' : null)
  if (type === 'trend_flip') return 'Alert when the trend changes direction'
  if (type === 'slope' && item.slope_threshold != null) {
    const x = item.slope_threshold
    return `Alert when the trend crosses ${x >= 0 ? '+' : ''}${x}% / month`
  }
  if (type === 'threshold' && item.threshold_direction && item.threshold_value != null) {
    return `Alert when the value goes ${item.threshold_direction} ${fmt(item.threshold_value)}`
  }
  return 'No alert'
}
