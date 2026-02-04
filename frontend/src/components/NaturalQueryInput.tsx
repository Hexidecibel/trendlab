import { useState } from 'react'
import { parseNaturalQuery } from '../api/client'

interface Props {
  loading: boolean
  onResult: (
    source: string,
    query: string,
    horizon: number,
    start?: string,
    end?: string,
  ) => void
}

export function NaturalQueryInput({ loading, onResult }: Props) {
  const [text, setText] = useState('')
  const [parsing, setParsing] = useState(false)
  const [interpretation, setInterpretation] = useState('')
  const [error, setError] = useState('')
  const [suggestions, setSuggestions] = useState<string[]>([])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!text.trim() || text.trim().length < 3) return

    setParsing(true)
    setError('')
    setSuggestions([])
    setInterpretation('')

    try {
      const result = await parseNaturalQuery(text.trim())
      setInterpretation(result.interpretation)
      onResult(
        result.source,
        result.query,
        result.horizon,
        result.start ?? undefined,
        result.end ?? undefined,
      )
    } catch (err: unknown) {
      const detail = (err as { detail?: { error?: string; suggestions?: string[] } })?.detail
      if (detail?.error) {
        setError(detail.error)
        setSuggestions(detail.suggestions ?? [])
      } else {
        setError('Failed to parse query. Try rephrasing.')
      }
    } finally {
      setParsing(false)
    }
  }

  const handleSuggestionClick = (suggestion: string) => {
    const cleaned = suggestion.replace(/^Try ['"]?|['"]?$/g, '')
    setText(cleaned)
  }

  const isDisabled = loading || parsing || text.trim().length < 3

  return (
    <div className="mb-6">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask anything... e.g., 'Show me Bitcoin price trend' or 'Seattle Sounders xG at home'"
          className="flex-1 border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          disabled={parsing}
        />
        <button
          type="submit"
          disabled={isDisabled}
          className="bg-blue-600 text-white px-6 py-3 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {parsing ? (
            <>
              <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              Parsing...
            </>
          ) : (
            'Ask'
          )}
        </button>
      </form>

      {interpretation && (
        <p className="mt-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded px-3 py-2">
          {interpretation}
        </p>
      )}

      {error && (
        <div className="mt-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
          <p>{error}</p>
          {suggestions.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-2">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => handleSuggestionClick(s)}
                  className="text-xs text-blue-600 hover:text-blue-800 underline"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
