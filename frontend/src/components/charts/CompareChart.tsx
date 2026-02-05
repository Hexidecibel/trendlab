import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Typography from '@mui/material/Typography'
import { Line } from 'react-chartjs-2'
import type { TimeSeries } from '../../api/types'

const COLORS = ['#3b82f6', '#f97316', '#10b981']

interface Props {
  seriesList: TimeSeries[]
}

export function CompareChart({ seriesList }: Props) {
  if (seriesList.length === 0) return null

  const datasets = seriesList.map((s, i) => ({
    label: `${s.source}: ${s.query}`,
    data: s.points.map((p) => ({ x: p.date, y: p.value })),
    borderColor: COLORS[i % COLORS.length],
    backgroundColor: COLORS[i % COLORS.length],
    pointRadius: 0,
    borderWidth: 2,
  }))

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    scales: {
      x: {
        type: 'time' as const,
        time: { unit: 'day' as const },
        title: { display: true, text: 'Date' },
      },
      y: {
        title: { display: true, text: 'Value' },
      },
    },
    plugins: {
      zoom: {
        zoom: {
          drag: { enabled: true },
          mode: 'x' as const,
        },
      },
    },
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="subtitle2" gutterBottom>
          Series Comparison
        </Typography>
        <Box sx={{ height: 400 }}>
          <Line data={{ datasets }} options={options} />
        </Box>
      </CardContent>
    </Card>
  )
}
