import { useEffect, useEffectEvent, useRef, useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import CircularProgress from '@mui/material/CircularProgress'
import Grid from '@mui/material/Grid'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Typography from '@mui/material/Typography'
import { ApiError, fetchCompare, fetchCorrelate } from '../../api/client'
import type { CompareItem, CorrelateResponse, DataSourceInfo, TimeSeries, TrendAnalysis } from '../../api/types'
import { preferredSmoothing } from '../../smoothing'
import type { SmoothingPreset } from '../../smoothing'
import { MAX_ITEMS, isCompareTool } from '../../urlState'
import type { CompareMode, CompareTool, CompareUrlState } from '../../urlState'
import { getFriendlyLabel } from '../../utils/labels'
import { AnalysisPanel } from '../AnalysisPanel'
import { CompareForm } from '../CompareForm'
import type { ComparePrefill } from '../CompareForm'
import { CompareInsightPanel } from '../CompareInsightPanel'
import { ErrorAlert } from '../ErrorAlert'
import { CompareChart } from '../charts/CompareChart'
import { CohortMode } from './CohortMode'
import type { CohortPrefill } from './CohortMode'
import { CorrelationView } from './CorrelationView'

const SERIES_COLORS = ['#3b82f6', '#f97316', '#10b981']

const TOOL_INFO: Record<CompareTool, { label: string; hint: string }> = {
  overlay: { label: 'Overlay', hint: '2-3 series on one chart, rebased to 100' },
  cohort: { label: 'Cohort', hint: 'Many series from one source, ranked by return' },
  correlation: { label: 'Correlation', hint: 'Do two series move together, and which leads?' },
}

/** A compare to run on mount (from the URL or the plain-English box). */
export interface CompareRequest {
  items: CompareItem[]
  resample?: string
  tool?: CompareTool
  smooth?: SmoothingPreset
  mode?: CompareMode
}

interface Props {
  sources: DataSourceInfo[]
  /** Remount (key) CompareView to apply a new request. */
  request?: CompareRequest | null
  /** What's on screen, for the page URL (null = nothing to encode). */
  onUrlState: (state: CompareUrlState | null) => void
}

type Corr = { status: 'idle' } | { status: 'loading' } | { status: 'done'; result: CorrelateResponse } | { status: 'error'; error: string | ApiError }

function errorOf(err: unknown): string | ApiError {
  return err instanceof ApiError ? err : err instanceof Error ? err.message : String(err)
}

/**
 * The Compare tab: one form of series, three tools.
 * - Overlay: 2-3 series on one chart (Index = 100 by default) + analyses
 * - Cohort: many series from one source, ranked
 * - Correlation: stats, lag chart and scatter for two series
 */
export function CompareView({ sources, request, onUrlState }: Props) {
  const [tool, setTool] = useState<CompareTool>(request?.tool ?? 'overlay')
  const [items, setItems] = useState<CompareItem[]>([])
  const [resample, setResample] = useState('')
  const [apply, setApply] = useState('')
  const [seriesList, setSeriesList] = useState<TimeSeries[] | null>(null)
  const [analyses, setAnalyses] = useState<TrendAnalysis[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | ApiError | null>(null)
  const [corr, setCorr] = useState<Corr>({ status: 'idle' })
  const [smoothingChoice, setSmoothingChoice] = useState<SmoothingPreset | null>(request?.smooth ?? null)
  const [scale, setScale] = useState<CompareMode>(request?.mode ?? 'index')
  const [formPrefill] = useState<ComparePrefill | null>(() =>
    request && request.items.length > 0 && request.tool !== 'cohort'
      ? { items: request.items.map((i) => ({ source: i.source, query: i.query })), resample: request.resample }
      : null,
  )
  // Cohort is mounted on first visit and then kept (hidden) so its results survive tool switches
  const [cohortPrefill, setCohortPrefill] = useState<CohortPrefill | null>(() =>
    request?.tool === 'cohort' && request.items.length >= 2
      ? { source: request.items[0].source, queries: request.items.map((i) => i.query), run: true }
      : null,
  )
  const [cohortMounted, setCohortMounted] = useState(request?.tool === 'cohort')
  const [cohortRun, setCohortRun] = useState<{ source: string; queries: string[] } | null>(null)
  const runRef = useRef(0)

  const runCompare = async (next: CompareItem[], nextResample?: string, nextApply?: string) => {
    const run = ++runRef.current
    setItems(next)
    setResample(nextResample || '')
    setApply(nextApply || '')
    setLoading(true)
    setError(null)
    setSeriesList(null)
    setAnalyses(null)
    if (next.length >= 2) {
      setCorr({ status: 'loading' })
      fetchCorrelate({ series_a: next[0], series_b: next[1], resample: nextResample || undefined })
        .then((result) => {
          if (runRef.current === run) setCorr({ status: 'done', result })
        })
        .catch((err: unknown) => {
          if (runRef.current === run) setCorr({ status: 'error', error: errorOf(err) })
        })
    } else {
      setCorr({ status: 'idle' })
    }
    try {
      const result = await fetchCompare(next, nextResample, nextApply)
      if (runRef.current !== run) return
      setSeriesList(result.series)
      setAnalyses(result.analyses ?? null)
    } catch (err) {
      if (runRef.current === run) setError(errorOf(err))
    } finally {
      if (runRef.current === run) setLoading(false)
    }
  }

  // Run the request this view was mounted with
  const runInitial = useEffectEvent(() => {
    if (request && request.items.length >= 2 && request.tool !== 'cohort') {
      void runCompare(request.items.slice(0, MAX_ITEMS[request.tool ?? 'overlay']), request.resample)
    }
  })
  useEffect(() => {
    runInitial()
  }, [])

  const handleToolChange = (next: CompareTool) => {
    if (next === 'cohort' && !cohortMounted) {
      // Start the cohort from the loaded series when they share a source
      const same = items.length >= 2 && items.every((i) => i.source === items[0].source)
      setCohortPrefill(same ? { source: items[0].source, queries: items.map((i) => i.query) } : null)
      setCohortMounted(true)
    }
    setTool(next)
  }

  // Smoothing: Medium when every series is count-like, else Raw (or the choice)
  const smoothing: SmoothingPreset =
    smoothingChoice ??
    (items.length > 0 && items.every((i) => preferredSmoothing(i.source, sources) !== 'raw') ? 'medium' : 'raw')

  // Report what's on screen for the URL
  let url: CompareUrlState | null = null
  if (tool === 'cohort') {
    url = cohortRun
      ? { kind: 'compare', tool, items: cohortRun.queries.map((q) => ({ source: cohortRun.source, query: q })) }
      : { kind: 'compare', tool, items: [] }
  } else if (items.length >= 2) {
    url = {
      kind: 'compare',
      tool,
      items: items.map((i) => ({ source: i.source, query: i.query })),
      resample: resample || undefined,
      smooth: tool === 'overlay' ? smoothing : undefined,
      mode: tool === 'overlay' ? scale : undefined,
    }
  } else {
    url = { kind: 'compare', tool, items: [] }
  }
  const urlKey = JSON.stringify(url)
  const reportUrl = useEffectEvent((key: string) => onUrlState(JSON.parse(key) as CompareUrlState))
  useEffect(() => {
    reportUrl(urlKey)
  }, [urlKey])

  const labels = seriesList?.map(getFriendlyLabel) ?? items.map((i) => `${i.source}: ${i.query}`)

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1.5, mb: 2 }}>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={tool}
          onChange={(_, v) => {
            if (isCompareTool(v)) handleToolChange(v)
          }}
          aria-label="Compare tool"
          sx={{ '& .MuiToggleButton-root': { px: { xs: 1.25, sm: 2 }, py: 0.5, textTransform: 'none' } }}
        >
          {(Object.keys(TOOL_INFO) as CompareTool[]).map((t) => (
            <ToggleButton key={t} value={t} title={TOOL_INFO[t].hint} data-testid={`compare-tool-${t}`}>
              {TOOL_INFO[t].label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
        <Typography variant="body2" color="text.secondary">
          {TOOL_INFO[tool].hint}
        </Typography>
      </Box>

      {tool !== 'cohort' && (
        <>
          <CompareForm
            sources={sources}
            loading={loading}
            onSubmit={(next, r, a) => void runCompare(next, r, a)}
            prefill={formPrefill}
            maxSeries={MAX_ITEMS[tool]}
          />
          {error && <ErrorAlert error={error} />}
        </>
      )}

      {tool === 'overlay' && (
        <>
          {loading && (
            <Box sx={{ textAlign: 'center', py: 6 }}>
              <CircularProgress size={32} />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                Fetching comparison data...
              </Typography>
            </Box>
          )}

          {seriesList && !loading && (
            <>
              <Grid container spacing={3}>
                <Grid size={{ xs: 12, lg: analyses ? 8 : 12 }}>
                  <CompareChart
                    seriesList={seriesList}
                    analyses={analyses}
                    resample={resample}
                    smoothing={smoothing}
                    onSmoothingChange={setSmoothingChoice}
                    mode={scale}
                    onModeChange={setScale}
                    correlation={corr.status === 'done' && seriesList.length === 2 ? corr.result : null}
                  />
                </Grid>
                {analyses && (
                  <Grid size={{ xs: 12, lg: 4 }}>
                    {analyses.map((a, i) => (
                      <Box key={i} sx={{ mb: 2 }}>
                        <Typography variant="subtitle2" sx={{ mb: 1, color: SERIES_COLORS[i], fontWeight: 600 }}>
                          {getFriendlyLabel(seriesList[i])}
                        </Typography>
                        <AnalysisPanel analysis={a} compact />
                      </Box>
                    ))}
                  </Grid>
                )}
              </Grid>
              {items.length >= 2 && (
                <CompareInsightPanel
                  items={items}
                  resample={resample}
                  apply={apply}
                  seriesList={seriesList ?? undefined}
                  analyses={analyses ?? undefined}
                />
              )}
            </>
          )}

          {!seriesList && !loading && !error && (
            <Box sx={{ textAlign: 'center', py: 8 }}>
              <Typography variant="body1" color="text.secondary" gutterBottom>
                Pick 2-3 series to compare side by side
              </Typography>
              <Typography variant="body2" color="text.disabled">
                Or try "compare fastapi and django" in the search bar above
              </Typography>
            </Box>
          )}
        </>
      )}

      {tool === 'correlation' && (
        <Box sx={{ mt: 1 }}>
          {items.length > 2 && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Correlation uses the first two series: {labels[0]} and {labels[1]}.
            </Alert>
          )}
          {corr.status === 'loading' && (
            <Box sx={{ textAlign: 'center', py: 6 }}>
              <CircularProgress size={32} />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                Computing correlation...
              </Typography>
            </Box>
          )}
          {corr.status === 'error' && <ErrorAlert error={corr.error} />}
          {corr.status === 'done' && <CorrelationView result={corr.result} labelA={labels[0]} labelB={labels[1]} />}
          {corr.status === 'idle' && (
            <Box sx={{ textAlign: 'center', py: 8 }}>
              <Typography variant="body1" color="text.secondary" gutterBottom>
                Pick two series to see how closely they move together
              </Typography>
              <Typography variant="body2" color="text.disabled">
                Try "bitcoin" (crypto) with "web3" (PyPI)
              </Typography>
            </Box>
          )}
        </Box>
      )}

      {cohortMounted && (
        <Box hidden={tool !== 'cohort'}>
          <CohortMode
            sources={sources}
            prefill={cohortPrefill}
            onRun={(source, queries) => setCohortRun({ source, queries })}
          />
        </Box>
      )}
    </Box>
  )
}
