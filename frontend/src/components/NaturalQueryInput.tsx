import { useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Link from '@mui/material/Link'
import TextField from '@mui/material/TextField'
import { parseNaturalQuery } from '../api/client'
import { isCompareResult } from '../api/types'
import type { NaturalCompareItem } from '../api/types'

interface Props {
  loading: boolean
  onResult: (
    source: string,
    query: string,
    horizon: number,
    start?: string,
    end?: string,
    resample?: string,
    apply?: string,
  ) => void
  onCompareResult?: (
    items: NaturalCompareItem[],
    interpretation: string,
    resample?: string,
  ) => void
}

export function NaturalQueryInput({ loading, onResult, onCompareResult }: Props) {
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
      if (isCompareResult(result)) {
        onCompareResult?.(
          result.items,
          result.interpretation,
          result.resample ?? undefined,
        )
      } else {
        onResult(
          result.source,
          result.query,
          result.horizon,
          result.start ?? undefined,
          result.end ?? undefined,
          result.resample ?? undefined,
          result.apply ?? undefined,
        )
      }
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
    <Box sx={{ mb: 3 }}>
      <form onSubmit={handleSubmit}>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            fullWidth
            size="small"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Ask anything... e.g., 'Compare Bitcoin and Ethereum' or 'Seattle Sounders xG at home'"
            disabled={parsing}
          />
          <Button
            type="submit"
            variant="contained"
            disabled={isDisabled}
            sx={{ whiteSpace: 'nowrap', minWidth: 80 }}
          >
            {parsing ? <CircularProgress size={20} color="inherit" /> : 'Ask'}
          </Button>
        </Box>
      </form>

      {interpretation && (
        <Alert severity="success" sx={{ mt: 1 }}>
          {interpretation}
        </Alert>
      )}

      {error && (
        <Alert severity="warning" sx={{ mt: 1 }}>
          {error}
          {suggestions.length > 0 && (
            <Box sx={{ mt: 0.5, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {suggestions.map((s, i) => (
                <Link
                  key={i}
                  component="button"
                  variant="body2"
                  onClick={() => handleSuggestionClick(s)}
                  sx={{ cursor: 'pointer' }}
                >
                  {s}
                </Link>
              ))}
            </Box>
          )}
        </Alert>
      )}
    </Box>
  )
}
