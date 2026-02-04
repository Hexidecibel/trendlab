import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { NaturalQueryInput } from './NaturalQueryInput'
import { QueryForm } from './QueryForm'
import { ForecastChart } from './charts/ForecastChart'
import { ModelSelector } from './ModelSelector'
import { AnalysisPanel } from './AnalysisPanel'
import { EvaluationTable } from './EvaluationTable'
import { InsightPanel } from './InsightPanel'

export function Dashboard() {
  const { sources, series, analysis, forecast, loading, error, loadData } =
    useApi()
  const [selectedModel, setSelectedModel] = useState('')
  const [lastQuery, setLastQuery] = useState({ source: '', query: '', horizon: 14 })

  const handleSubmit = (source: string, query: string, horizon: number, start?: string, end?: string) => {
    setLastQuery({ source, query, horizon })
    setSelectedModel('')
    loadData(source, query, horizon, start, end)
  }

  // Auto-select recommended model when forecast loads
  const effectiveModel =
    selectedModel || forecast?.recommended_model || ''

  const hasData = series && analysis && forecast

  return (
    <div>
      <NaturalQueryInput loading={loading} onResult={handleSubmit} />

      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-200" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="bg-white px-3 text-gray-400">or use the form</span>
        </div>
      </div>

      <QueryForm
        sources={sources}
        loading={loading}
        onSubmit={handleSubmit}
      />

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded px-4 py-3 mb-6">
          {error}
        </div>
      )}

      {loading && (
        <div className="text-center py-12 text-gray-500">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-3" />
          <p className="text-sm">Fetching data and running analysis...</p>
        </div>
      )}

      {hasData && (
        <>
          <div className="mb-4">
            <ModelSelector
              forecast={forecast}
              selected={effectiveModel}
              onChange={setSelectedModel}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <ForecastChart
                series={series}
                forecast={forecast}
                selectedModel={effectiveModel}
              />
              <EvaluationTable
                evaluations={forecast.evaluations}
                recommended={forecast.recommended_model}
              />
            </div>

            <div className="space-y-6">
              <AnalysisPanel analysis={analysis} />
              {lastQuery.source && lastQuery.query && (
                <InsightPanel
                  source={lastQuery.source}
                  query={lastQuery.query}
                  horizon={lastQuery.horizon}
                />
              )}
            </div>
          </div>
        </>
      )}

      {!hasData && !loading && !error && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg mb-1">Select a data source and enter a query to get started</p>
          <p className="text-sm">
            Try PyPI with "fastapi" or Crypto with "bitcoin"
          </p>
        </div>
      )}
    </div>
  )
}
