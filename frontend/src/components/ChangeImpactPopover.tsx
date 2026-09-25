import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import IconButton from '@mui/material/IconButton'
import Popover from '@mui/material/Popover'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import CloseIcon from '@mui/icons-material/Close'
import { ApiError, fetchCausalImpact } from '../api/client'
import type { CausalImpactResponse } from '../api/types'
import { formatCompact, formatShortDate } from '../utils/format'
import { CausalImpactChart } from './CausalImpactChart'
import { ErrorAlert } from './ErrorAlert'

export interface ImpactRequest {
  /** ISO date of the change to test. */
  date: string
  /** Screen position to anchor the popover at. */
  x: number
  y: number
  /** Where it came from, e.g. "big drop" for a structural break. */
  label?: string | null
}

interface QueryProps {
  source: string
  query: string
  start?: string
  end?: string
  resample?: string
  apply?: string
}

interface Props extends QueryProps {
  request: ImpactRequest | null
  onClose: () => void
}

/** Plain-words verdict for a p-value. */
function describeSignificance(p: number): { text: string; color: 'success' | 'warning' | 'default' } {
  if (p < 0.01) return { text: 'Very unlikely to be chance', color: 'success' }
  if (p < 0.05) return { text: 'Unlikely to be chance', color: 'success' }
  if (p < 0.1) return { text: 'Weak evidence: might be chance', color: 'warning' }
  return { text: 'Could easily be chance', color: 'default' }
}

/** "days" / "weeks" / "months" from the spacing of the result's points. */
function stepUnit(result: CausalImpactResponse): string {
  const pts = result.pointwise
  if (pts.length < 2) return 'points'
  const gaps: number[] = []
  for (let i = 1; i < Math.min(pts.length, 20); i++) {
    gaps.push((Date.parse(pts[i].date) - Date.parse(pts[i - 1].date)) / 86_400_000)
  }
  gaps.sort((a, b) => a - b)
  const g = gaps[Math.floor(gaps.length / 2)]
  if (g <= 1.5) return 'days'
  if (g <= 8) return 'weeks'
  if (g <= 32) return 'months'
  if (g <= 95) return 'quarters'
  return 'periods'
}

function ImpactResult({ result }: { result: CausalImpactResponse }) {
  const pct = result.relative_impact_pct
  const cum = result.cumulative_impact
  const sig = describeSignificance(result.p_value)
  const up = pct >= 0
  const pctText = Number.isFinite(pct) ? `${Math.abs(pct) >= 10 ? Math.abs(pct).toFixed(0) : Math.abs(pct).toFixed(1)}%` : '?'
  const n = result.post_period_length
  return (
    <Box data-testid="impact-result">
      <Typography variant="h6" sx={{ color: up ? 'success.main' : 'error.main', lineHeight: 1.3 }}>
        {pctText} {up ? 'higher' : 'lower'} than expected
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {formatCompact(Math.abs(cum))} {up ? 'more' : 'less'} in total over the {n} {stepUnit(result)} after,
        vs. what the earlier trend predicted
      </Typography>
      <Tooltip title={`${result.summary} Pre-period ${result.pre_period_length} points, post-period ${n}.`}>
        <Chip size="small" color={sig.color} variant="outlined" label={`${sig.text} (p = ${result.p_value < 0.001 ? '<0.001' : result.p_value.toFixed(3)})`} sx={{ mb: 1 }} />
      </Tooltip>
      <CausalImpactChart result={result} height={150} compact />
    </Box>
  )
}

type State = { status: 'loading' } | { status: 'done'; result: CausalImpactResponse } | { status: 'error'; error: string | ApiError }

/** Runs the causal-impact endpoint for one date; remounted (keyed) per date. */
function ImpactBody({ date, source, query, start, end, resample, apply }: QueryProps & { date: string }) {
  const [state, setState] = useState<State>({ status: 'loading' })
  useEffect(() => {
    let alive = true
    fetchCausalImpact(source, query, date, { start, end, resample, apply })
      .then((result) => {
        if (alive) setState({ status: 'done', result })
      })
      .catch((err: unknown) => {
        if (!alive) return
        setState({
          status: 'error',
          error: err instanceof ApiError ? err : err instanceof Error ? err.message : String(err),
        })
      })
    return () => {
      alive = false
    }
  }, [date, source, query, start, end, resample, apply])

  if (state.status === 'loading') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 2 }}>
        <CircularProgress size={18} />
        <Typography variant="body2" color="text.secondary">
          Comparing before and after…
        </Typography>
      </Box>
    )
  }
  if (state.status === 'error') return <ErrorAlert error={state.error} />
  return <ImpactResult result={state.result} />
}

/** "What changed after <date>?" popover, opened by clicking the chart or a break. */
export function ChangeImpactPopover({ request, onClose, ...query }: Props) {
  return (
    <Popover
      open={!!request}
      onClose={onClose}
      anchorReference="anchorPosition"
      anchorPosition={request ? { top: request.y, left: request.x } : undefined}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      transformOrigin={{ vertical: 'top', horizontal: 'center' }}
      slotProps={{ paper: { sx: { p: 2, width: 380, maxWidth: 'calc(100vw - 32px)' }, 'data-testid': 'impact-popover' } as object }}
    >
      {request && (
        <>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Typography variant="subtitle1" fontWeight={600} sx={{ flex: 1 }}>
              What changed after {formatShortDate(request.date)}?
            </Typography>
            {request.label && <Chip size="small" label={request.label} />}
            <IconButton size="small" onClick={onClose} aria-label="Close">
              <CloseIcon fontSize="small" />
            </IconButton>
          </Box>
          <ImpactBody key={request.date} date={request.date} {...query} />
        </>
      )}
    </Popover>
  )
}
