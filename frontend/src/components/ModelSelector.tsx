import type { ForecastComparison } from '../api/types'

interface Props {
  forecast: ForecastComparison
  selected: string
  onChange: (model: string) => void
}

export function ModelSelector({ forecast, selected, onChange }: Props) {
  const evalMap = new Map(
    forecast.evaluations.map((e) => [e.model_name, e]),
  )

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-sm font-medium text-gray-700">Model:</span>
      {forecast.forecasts.map((f) => {
        const isRecommended = f.model_name === forecast.recommended_model
        const isSelected = f.model_name === selected
        const ev = evalMap.get(f.model_name)
        return (
          <button
            key={f.model_name}
            onClick={() => onChange(f.model_name)}
            className={`text-xs px-3 py-1 rounded-full border transition-colors ${
              isSelected
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400'
            }`}
          >
            {f.model_name}
            {isRecommended && ' *'}
            {ev && ` (MAE: ${ev.mae.toFixed(2)})`}
          </button>
        )
      })}
    </div>
  )
}
