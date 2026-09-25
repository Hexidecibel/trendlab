import type { WatchlistItem, WatchlistUpdateRequest } from '../../api/types'

/** The alert choice as one value for a single dropdown. */
export type AlertChoice = 'none' | 'trend_flip' | 'slope' | 'above' | 'below'

export interface AlertDraft {
  choice: AlertChoice
  /** Slope in % / month, or the threshold value; kept as typed text. */
  amount: string
}

export function draftFromItem(item: WatchlistItem): AlertDraft {
  const type = item.alert_type ?? (item.threshold_direction ? 'threshold' : null)
  if (type === 'trend_flip') return { choice: 'trend_flip', amount: '' }
  if (type === 'slope') return { choice: 'slope', amount: String(item.slope_threshold ?? '') }
  if (type === 'threshold' && item.threshold_direction) {
    return { choice: item.threshold_direction, amount: String(item.threshold_value ?? '') }
  }
  return { choice: 'none', amount: '' }
}

export function draftNeedsAmount(d: AlertDraft): boolean {
  return d.choice === 'slope' || d.choice === 'above' || d.choice === 'below'
}

export function draftIsValid(d: AlertDraft): boolean {
  return !draftNeedsAmount(d) || (d.amount.trim() !== '' && Number.isFinite(Number(d.amount)))
}

/** The API fields for a draft (every alert field set, so edits replace fully). */
export function draftToRequest(d: AlertDraft): WatchlistUpdateRequest {
  const amount = Number(d.amount)
  switch (d.choice) {
    case 'trend_flip':
      return { alert_type: 'trend_flip', threshold_direction: null, threshold_value: null, slope_threshold: null }
    case 'slope':
      return { alert_type: 'slope', threshold_direction: null, threshold_value: null, slope_threshold: amount }
    case 'above':
    case 'below':
      return { alert_type: 'threshold', threshold_direction: d.choice, threshold_value: amount, slope_threshold: null }
    default:
      return { alert_type: null, threshold_direction: null, threshold_value: null, slope_threshold: null }
  }
}
