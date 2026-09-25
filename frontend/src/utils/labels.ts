import type { TimeSeries } from '../api/types'

const SOURCE_NAMES: Record<string, string> = {
  pypi: 'PyPI',
  npm: 'npm',
  crypto: 'Crypto',
  github_stars: 'GitHub',
  google_trends: 'Google Trends',
  csv: 'CSV',
}

/** Friendly label from series metadata, e.g. "requests (PyPI)", "BTC (Crypto)". */
export function getFriendlyLabel(s: TimeSeries): string {
  const meta = s.metadata || {}

  if (meta.article) return `${meta.article} (Wikipedia)`
  if (meta.package) return `${meta.package} (${s.source === 'npm' ? 'npm' : 'PyPI'})`
  if (meta.coin) return `${meta.coin} (Crypto)`
  if (meta.symbol) return `${meta.symbol} (${meta.metric || 'Stock'})`
  if (meta.team) return `${meta.team} (${meta.metric_label || 'xG'})`
  if (meta.player) return `${meta.player} (${meta.metric_label || 'xG'})`
  if (meta.location) return `${meta.location} (${meta.metric_label || 'Weather'})`

  // Fallback: simplify query
  const query = s.query
  if (query.includes(':')) {
    const parts = query.split(':')
    return parts[1] || parts[0] || query
  }

  return `${query} (${SOURCE_NAMES[s.source] ?? s.source})`
}
