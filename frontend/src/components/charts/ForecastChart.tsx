import { Line } from 'react-chartjs-2'
import type { TimeSeries, ForecastComparison } from '../../api/types'

interface Props {
  series: TimeSeries
  forecast: ForecastComparison
  selectedModel: string
}

export function ForecastChart({ series, forecast, selectedModel }: Props) {
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
    },
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Time Series & Forecast
      </h3>
      <div className="h-80">
        <Line data={data} options={options} />
      </div>
    </div>
  )
}
