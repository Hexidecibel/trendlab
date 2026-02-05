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

export interface FormFieldOption {
  value: string
  label: string
}

export interface FormField {
  name: string
  label: string
  field_type: 'text' | 'select' | 'autocomplete'
  placeholder: string
  options: FormFieldOption[]
  depends_on: string | null
}

export interface DataSourceInfo {
  name: string
  description: string
  form_fields: FormField[]
}

export interface LookupItem {
  value: string
  label: string
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

export interface NaturalQueryResponse {
  source: string
  query: string
  horizon: number
  start: string | null
  end: string | null
  resample: string | null
  apply: string | null
  interpretation: string
}

export interface NaturalCompareItem {
  source: string
  query: string
  start: string | null
  end: string | null
}

export interface NaturalCompareResponse {
  items: NaturalCompareItem[]
  resample: string | null
  interpretation: string
}

export type NaturalQueryResult = NaturalQueryResponse | NaturalCompareResponse

export function isCompareResult(r: NaturalQueryResult): r is NaturalCompareResponse {
  return 'items' in r
}

export interface CompareItem {
  source: string
  query: string
  start?: string
  end?: string
}

export interface CompareResponse {
  series: TimeSeries[]
  analyses?: TrendAnalysis[]
  count: number
}

export interface NaturalQueryError {
  detail: {
    error: string
    suggestions: string[]
  }
}

// Rich data context for AI follow-up questions
export interface DataContext {
  data_points_count: number
  date_range: string
  min_value: number
  max_value: number
  mean_value: number
  recent_values: Array<{ date: string; value: number }>
  trend_direction: string
  trend_momentum: number
  anomaly_count: number
  anomalies: Array<{ date: string; value: number; score: number }>
  structural_breaks: Array<{ date: string; method: string }>
  seasonality_detected: boolean
  seasonality_period?: number
  forecast_horizon?: number
  forecast_values?: Array<{ date: string; value: number; lower_ci: number; upper_ci: number }>
}
