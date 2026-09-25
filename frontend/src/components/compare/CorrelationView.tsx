import { useRef } from 'react'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Grid from '@mui/material/Grid'
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import DownloadIcon from '@mui/icons-material/Download'
import { Bar, Scatter } from 'react-chartjs-2'
import { BarElement, Chart as ChartJSClass } from 'chart.js'
import type { Chart as ChartJS } from 'chart.js'
import type { CorrelateResponse } from '../../api/types'
import { formatLagLong, formatLagShort, lagAxisTitle } from '../../utils/lag'
import { compactTick, formatPrecise } from '../../utils/format'

ChartJSClass.register(BarElement)

function strength(r: number): string {
  const a = Math.abs(r)
  if (a > 0.7) return 'Strong'
  if (a > 0.3) return 'Moderate'
  return 'Weak or no'
}

function pText(p: number): string {
  return p < 0.001 ? '<0.001' : p.toFixed(3)
}

function download(chart: ChartJS | null | undefined, name: string) {
  if (!chart) return
  const link = document.createElement('a')
  link.download = name
  link.href = chart.toBase64Image()
  link.click()
}

interface Props {
  result: CorrelateResponse
  /** Friendly names for the two series (else the backend labels). */
  labelA?: string
  labelB?: string
}

/** Correlation mode of Compare: stats, scatter plot and the lag chart. */
export function CorrelationView({ result, labelA, labelB }: Props) {
  const scatterRef = useRef<ChartJS<'scatter'>>(null)
  const lagRef = useRef<ChartJS<'bar'>>(null)
  const a = labelA || result.series_a_label
  const b = labelB || result.series_b_label
  const r = result.pearson.r
  const best = [...result.lag_analysis].sort((x, y) => Math.abs(y.correlation) - Math.abs(x.correlation))[0]
  const bestIsLagged = best && best.lag !== 0 && Math.abs(best.correlation) > Math.abs(r) + 0.02

  return (
    <Grid container spacing={3} data-testid="correlation-view">
      <Grid size={{ xs: 12, md: 4 }}>
        <Card sx={{ height: '100%' }}>
          <CardContent>
            <Typography variant="subtitle2" gutterBottom>
              How closely they move together
            </Typography>
            <Typography variant="h4" sx={{ color: Math.abs(r) > 0.5 ? 'success.main' : 'text.primary' }}>
              r = {r.toFixed(2)}
            </Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
              {strength(r)}
              {r < 0 && Math.abs(r) > 0.3 ? ' negative' : ''} correlation ·{' '}
              {result.pearson.p_value < 0.05 ? 'statistically significant' : 'not significant'}
            </Typography>
            {bestIsLagged && (
              <Typography variant="body2" sx={{ mb: 2 }}>
                Strongest when {best.lag > 0 ? a : b} leads by {formatLagLong(Math.abs(best.lag), result.lag_step)} (r ={' '}
                {best.correlation.toFixed(2)})
              </Typography>
            )}
            <Box sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
              <Typography variant="caption" component="div">
                Pearson r {r.toFixed(3)} (p {pText(result.pearson.p_value)})
              </Typography>
              <Typography variant="caption" component="div">
                Spearman ρ {result.spearman.r.toFixed(3)} (p {pText(result.spearman.p_value)})
              </Typography>
              <Typography variant="caption" component="div">
                {result.aligned_points} aligned points
              </Typography>
            </Box>
          </CardContent>
        </Card>
      </Grid>

      <Grid size={{ xs: 12, md: 8 }}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="subtitle2">Lag correlation</Typography>
              <Tooltip title="Download PNG">
                <IconButton size="small" onClick={() => download(lagRef.current, `lag-${a}-vs-${b}.png`)} aria-label="Download lag chart">
                  <DownloadIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
              Correlation when one series is shifted in time (positive lag = {a} moves first)
            </Typography>
            <Box sx={{ height: { xs: 220, sm: 260 } }}>
              <Bar
                ref={lagRef}
                data={{
                  labels: result.lag_analysis.map((l) => formatLagShort(l.lag, result.lag_step)),
                  datasets: [
                    {
                      label: 'Correlation',
                      data: result.lag_analysis.map((l) => l.correlation),
                      backgroundColor: result.lag_analysis.map((l) =>
                        l.correlation >= 0 ? 'rgba(16, 185, 129, 0.7)' : 'rgba(239, 68, 68, 0.7)',
                      ),
                      borderColor: result.lag_analysis.map((l) => (l.correlation >= 0 ? '#10b981' : '#ef4444')),
                      borderWidth: 1,
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  scales: {
                    y: { min: -1, max: 1, title: { display: true, text: 'Correlation' } },
                    x: { title: { display: true, text: lagAxisTitle(result.lag_step) } },
                  },
                  plugins: { legend: { display: false } },
                }}
              />
            </Box>
          </CardContent>
        </Card>
      </Grid>

      <Grid size={{ xs: 12 }}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="subtitle2">Scatter plot</Typography>
              <Tooltip title="Download PNG">
                <IconButton size="small" onClick={() => download(scatterRef.current, `scatter-${a}-vs-${b}.png`)} aria-label="Download scatter plot">
                  <DownloadIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
            <Box sx={{ height: { xs: 240, sm: 300 } }}>
              <Scatter
                ref={scatterRef}
                data={{
                  datasets: [
                    {
                      label: `${a} vs ${b}`,
                      data: result.scatter,
                      backgroundColor: 'rgba(59, 130, 246, 0.5)',
                      borderColor: '#3b82f6',
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  scales: {
                    x: { title: { display: true, text: a }, ticks: { callback: compactTick } },
                    y: { title: { display: true, text: b }, ticks: { callback: compactTick } },
                  },
                  plugins: {
                    legend: { display: false },
                    tooltip: {
                      callbacks: {
                        label: (ctx) => `${formatPrecise(ctx.parsed.x)}, ${formatPrecise(ctx.parsed.y)}`,
                      },
                    },
                  },
                }}
              />
            </Box>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  )
}
