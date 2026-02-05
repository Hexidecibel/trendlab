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

export interface ResamplePeriod {
  value: string
  label: string
  description: string
}

export interface DataSourceInfo {
  name: string
  description: string
  form_fields: FormField[]
  resample_periods: ResamplePeriod[]
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

// Correlation types
export interface CorrelationCoefficient {
  r: number
  p_value: number
}

export interface LagCorrelation {
  lag: number
  correlation: number
}

export interface ScatterPoint {
  x: number
  y: number
}

export interface CorrelateItem {
  source: string
  query: string
  start?: string
  end?: string
}

export interface CorrelateRequest {
  series_a: CorrelateItem
  series_b: CorrelateItem
  start?: string
  end?: string
  resample?: string
  refresh?: boolean
}

// Saved Views types
export interface SaveViewRequest {
  name: string
  source: string
  query: string
  horizon?: number
  start?: string
  end?: string
  resample?: string
  apply?: string
  anomaly_method?: string
}

export interface SavedViewResponse {
  hash_id: string
  name: string
  source: string
  query: string
  horizon: number
  start: string | null
  end: string | null
  resample: string | null
  apply: string | null
  anomaly_method: string
  created_at: string
}

export interface CorrelateResponse {
  series_a_label: string
  series_b_label: string
  aligned_points: number
  pearson: CorrelationCoefficient
  spearman: CorrelationCoefficient
  lag_analysis: LagCorrelation[]
  scatter: ScatterPoint[]
}

// Watchlist types
export interface WatchlistAddRequest {
  name: string
  source: string
  query: string
  resample?: string
  threshold_direction?: 'above' | 'below'
  threshold_value?: number
}

export interface WatchlistItem {
  id: number
  name: string
  source: string
  query: string
  resample?: string
  threshold_direction?: 'above' | 'below'
  threshold_value?: number
  last_value?: number
  last_checked_at?: string
  created_at: string
  triggered: boolean
  trend_direction?: 'rising' | 'falling' | 'stable'
}

export interface WatchlistCheckResponse {
  items: WatchlistItem[]
  checked_at: string
  alerts: WatchlistItem[]
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
