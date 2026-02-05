import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Typography from '@mui/material/Typography'
import { Line } from 'react-chartjs-2'
import type { TimeSeries, ForecastComparison, TrendAnalysis } from '../../api/types'

interface Props {
  series: TimeSeries
  forecast: ForecastComparison
  selectedModel: string
  analysis?: TrendAnalysis | null
  showBreaks?: boolean
  showAnomalies?: boolean
}

export function ForecastChart({
  series,
  forecast,
  selectedModel,
  analysis,
  showBreaks = true,
  showAnomalies = true,
}: Props) {
  const modelForecast = forecast.forecasts.find(
    (f) => f.model_name === selectedModel,
  )
  if (!modelForecast) return null

  const actualData = series.points.map((p) => ({ x: p.date, y: p.value }))
  const forecastData = modelForecast.points.map((p) => ({
    x: p.date,
    y: p.value,
  }))
  const upperCI = modelForecast.points.map((p) => ({
    x: p.date,
    y: p.upper_ci,
  }))
  const lowerCI = modelForecast.points.map((p) => ({
    x: p.date,
    y: p.lower_ci,
  }))

  const data = {
    datasets: [
      {
        label: 'Actual',
        data: actualData,
        borderColor: '#3b82f6',
        backgroundColor: '#3b82f6',
        pointRadius: 0,
        borderWidth: 2,
      },
      {
        label: `Forecast (${selectedModel})`,
        data: forecastData,
        borderColor: '#f97316',
        backgroundColor: '#f97316',
        borderDash: [5, 5],
        pointRadius: 0,
        borderWidth: 2,
      },
      {
        label: '95% CI Upper',
        data: upperCI,
        borderColor: 'transparent',
        backgroundColor: 'transparent',
        pointRadius: 0,
        borderWidth: 0,
      },
      {
        label: '95% CI Lower',
        data: lowerCI,
        borderColor: 'transparent',
        backgroundColor: 'rgba(249, 115, 22, 0.1)',
        pointRadius: 0,
        borderWidth: 0,
        fill: '-1',
      },
    ],
  }

  // Build annotation config from analysis data
  const annotations: Record<string, object> = {}

  if (analysis && showBreaks) {
    analysis.structural_breaks.forEach((brk, i) => {
      annotations[`break-${i}`] = {
        type: 'line',
        xMin: brk.date,
        xMax: brk.date,
        borderColor: 'rgba(239, 68, 68, 0.7)',
        borderWidth: 2,
        borderDash: [6, 4],
        label: {
          display: true,
          content: `Break (${brk.method})`,
          position: 'start',
          backgroundColor: 'rgba(239, 68, 68, 0.8)',
          color: '#fff',
          font: { size: 10 },
        },
      }
    })
  }

  if (analysis && showAnomalies) {
    analysis.anomalies.anomalies.forEach((a, i) => {
      annotations[`anomaly-${i}`] = {
        type: 'point',
        xValue: a.date,
        yValue: a.value,
        radius: 5,
        backgroundColor: 'rgba(239, 68, 68, 0.4)',
        borderColor: 'rgb(239, 68, 68)',
        borderWidth: 2,
      }
    })
  }

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
      legend: {
        labels: {
          filter: (item: { text: string }) =>
            !item.text.startsWith('95% CI'),
        },
      },
      zoom: {
        zoom: {
          drag: { enabled: true },
          mode: 'x' as const,
        },
      },
      annotation: {
        annotations,
      },
    },
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="subtitle2" gutterBottom>
          Time Series & Forecast
        </Typography>
        <Box sx={{ height: 320 }}>
          <Line data={data} options={options} />
        </Box>
      </CardContent>
    </Card>
  )
}
