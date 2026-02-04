export interface DataPoint {
  date: string
  value: number
}

export interface TimeSeries {
  source: string
  query: string
  points: DataPoint[]
  metadata: Record<string, unknown>
}

export interface DataSourceInfo {
  name: string
  description: string
}

export interface MovingAverage {
  window: number
  values: DataPoint[]
}

export interface TrendSignal {
  direction: string
  momentum: number
  acceleration: number
  moving_averages: MovingAverage[]
  momentum_series: DataPoint[]
}

export interface SeasonalityResult {
  detected: boolean
  period_days: number | null
  strength: number | null
  autocorrelation: number[]
}

export interface AnomalyPoint {
  date: string
  value: number
  score: number
  method: string
}

export interface AnomalyReport {
  method: string
  threshold: number
  anomalies: AnomalyPoint[]
  total_points: number
  anomaly_count: number
}

export interface StructuralBreak {
  date: string
  index: number
  method: string
  confidence: number
}

export interface TrendAnalysis {
  source: string
  query: string
  series_length: number
  trend: TrendSignal
  seasonality: SeasonalityResult
  anomalies: AnomalyReport
  structural_breaks: StructuralBreak[]
}

export interface ForecastPoint {
  date: string
  value: number
  lower_ci: number
  upper_ci: number
}

export interface ModelForecast {
  model_name: string
  points: ForecastPoint[]
}

export interface ModelEvaluation {
  model_name: string
  mae: number
  rmse: number
  mape: number
  train_size: number
  test_size: number
}

export interface ForecastComparison {
  source: string
  query: string
  series_length: number
  horizon: number
  forecasts: ModelForecast[]
  evaluations: ModelEvaluation[]
  recommended_model: string
}
