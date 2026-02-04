import type { TrendAnalysis } from '../api/types'

interface Props {
  analysis: TrendAnalysis
}

const DIRECTION_COLORS: Record<string, string> = {
  rising: 'bg-green-100 text-green-800',
  falling: 'bg-red-100 text-red-800',
  stable: 'bg-gray-100 text-gray-800',
}

export function AnalysisPanel({ analysis }: Props) {
  const { trend, seasonality, anomalies, structural_breaks } = analysis
  const dirClass = DIRECTION_COLORS[trend.direction] || DIRECTION_COLORS.stable

  return (
    <div className="bg-white rounded-lg shadow p-4 space-y-4">
      <h3 className="text-sm font-semibold text-gray-700">Trend Analysis</h3>

      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded ${dirClass}`}>
            {trend.direction.toUpperCase()}
          </span>
        </div>
        <p className="text-xs text-gray-500">
          Momentum: {trend.momentum.toFixed(4)} | Acceleration:{' '}
          {trend.acceleration.toFixed(4)}
        </p>
      </div>

      <div>
        <h4 className="text-xs font-semibold text-gray-600 mb-1">
          Seasonality
        </h4>
        {seasonality.detected ? (
          <p className="text-xs text-gray-700">
            Detected: {seasonality.period_days}-day period (strength:{' '}
            {seasonality.strength?.toFixed(2)})
          </p>
        ) : (
          <p className="text-xs text-gray-500">No seasonality detected</p>
        )}
      </div>

      <div>
        <h4 className="text-xs font-semibold text-gray-600 mb-1">
          Anomalies
        </h4>
        <p className="text-xs text-gray-700">
          {anomalies.anomaly_count} of {anomalies.total_points} points flagged
          ({anomalies.method})
        </p>
        {anomalies.anomalies.slice(0, 5).map((a, i) => (
          <p key={i} className="text-xs text-gray-500 ml-2">
            {a.date}: {a.value.toFixed(1)} (score: {a.score.toFixed(2)})
          </p>
        ))}
      </div>

      <div>
        <h4 className="text-xs font-semibold text-gray-600 mb-1">
          Structural Breaks
        </h4>
        {structural_breaks.length === 0 ? (
          <p className="text-xs text-gray-500">None detected</p>
        ) : (
          structural_breaks.map((b, i) => (
            <p key={i} className="text-xs text-gray-700 ml-2">
              {b.date} ({b.method}, confidence: {b.confidence.toFixed(2)})
            </p>
          ))
        )}
      </div>
    </div>
  )
}
