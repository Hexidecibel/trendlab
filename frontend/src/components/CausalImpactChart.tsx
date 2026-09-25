import { Line } from 'react-chartjs-2'
import type { CausalImpactResponse } from '../api/types'
import { compactTick, formatPrecise, formatShortDate } from '../utils/format'

interface Props {
  result: CausalImpactResponse
  height?: number
  /** Hide the legend and axis titles (compact popover use). */
  compact?: boolean
}

/** Actual vs the counterfactual ("expected without the change") with its 95% band. */
export function CausalImpactChart({ result, height = 280, compact = false }: Props) {
  const data = {
    datasets: [
      {
        label: 'Actual',
        data: result.pointwise.map((p) => ({ x: p.date, y: p.actual })),
        borderColor: '#3b82f6',
        backgroundColor: '#3b82f6',
        pointRadius: 0,
        borderWidth: 2,
      },
      {
        label: 'Expected',
        data: result.pointwise.map((p) => ({ x: p.date, y: p.predicted })),
        borderColor: '#f97316',
        backgroundColor: '#f97316',
        borderDash: [5, 5],
        pointRadius: 0,
        borderWidth: 2,
      },
      {
        label: '95% CI Upper',
        data: result.pointwise.map((p) => ({ x: p.date, y: p.upper_ci })),
        borderColor: 'transparent',
        backgroundColor: 'transparent',
        pointRadius: 0,
        borderWidth: 0,
      },
      {
        label: '95% CI Lower',
        data: result.pointwise.map((p) => ({ x: p.date, y: p.lower_ci })),
        borderColor: 'transparent',
        backgroundColor: 'rgba(249, 115, 22, 0.12)',
        pointRadius: 0,
        borderWidth: 0,
        fill: '-1',
      },
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false as const,
    interaction: { mode: 'index' as const, intersect: false },
    scales: {
      x: {
        type: 'time' as const,
        time: { tooltipFormat: 'MMM d, yyyy' },
        title: { display: !compact, text: 'Date' },
        ticks: { maxTicksLimit: compact ? 4 : 8, font: { size: compact ? 10 : 12 } },
      },
      y: {
        title: { display: !compact, text: 'Value' },
        ticks: { callback: compactTick, maxTicksLimit: compact ? 4 : 8, font: { size: compact ? 10 : 12 } },
      },
    },
    plugins: {
      legend: {
        display: true,
        labels: {
          boxWidth: compact ? 10 : 40,
          font: { size: compact ? 10 : 12 },
          filter: (item: { text: string }) => !item.text.startsWith('95% CI'),
        },
      },
      tooltip: {
        filter: (item: { dataset: { label?: string } }) => !item.dataset.label?.startsWith('95% CI'),
        callbacks: {
          label: (ctx: { dataset: { label?: string }; parsed: { y: number | null } }) =>
            `${ctx.dataset.label}: ${formatPrecise(ctx.parsed.y)}`,
        },
      },
      annotation: {
        annotations: {
          eventLine: {
            type: 'line' as const,
            xMin: result.event_date,
            xMax: result.event_date,
            borderColor: 'rgba(239, 68, 68, 0.8)',
            borderWidth: 2,
            borderDash: [6, 4],
            label: {
              display: !compact,
              content: formatShortDate(result.event_date),
              position: 'start' as const,
              backgroundColor: 'rgba(239, 68, 68, 0.8)',
              color: '#fff',
              font: { size: 10 },
            },
          },
        },
      },
    },
  }

  return (
    <div style={{ height }}>
      <Line data={data} options={options} />
    </div>
  )
}
