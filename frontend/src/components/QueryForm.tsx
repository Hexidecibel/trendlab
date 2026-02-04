import { useState } from 'react'
import type { DataSourceInfo } from '../api/types'

const PLACEHOLDERS: Record<string, string> = {
  pypi: 'fastapi',
  github_stars: 'owner/repo',
  crypto: 'bitcoin',
  football: 'PL/Arsenal FC',
}

interface Props {
  sources: DataSourceInfo[]
  loading: boolean
  onSubmit: (source: string, query: string, horizon: number) => void
}

export function QueryForm({ sources, loading, onSubmit }: Props) {
  const [source, setSource] = useState('')
  const [query, setQuery] = useState('')
  const [horizon, setHorizon] = useState(14)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (source && query) {
      onSubmit(source, query, horizon)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap gap-3 items-end"
    >
      <div className="flex-1 min-w-[150px]">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Source
        </label>
        <select
          value={source}
          onChange={(e) => setSource(e.target.value)}
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
        >
          <option value="">Select a source...</option>
          {sources.map((s) => (
            <option key={s.name} value={s.name}>
              {s.name} &mdash; {s.description}
            </option>
          ))}
        </select>
      </div>

      <div className="flex-1 min-w-[200px]">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Query
        </label>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={PLACEHOLDERS[source] || 'Enter query...'}
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
        />
      </div>

      <div className="w-24">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Horizon
        </label>
        <input
          type="number"
          value={horizon}
          onChange={(e) => setHorizon(Number(e.target.value))}
          min={1}
          max={365}
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
        />
      </div>

      <button
        type="submit"
        disabled={loading || !source || !query}
        className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Loading...' : 'Analyze'}
      </button>
    </form>
  )
}
