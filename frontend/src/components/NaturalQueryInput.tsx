import { useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Collapse from '@mui/material/Collapse'
import Link from '@mui/material/Link'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import { parseNaturalQuery } from '../api/client'
import { isCompareResult } from '../api/types'
import type { NaturalCompareItem } from '../api/types'

const EXAMPLE_QUERIES = [
  // Sports - MLS teams with season resampling
  { text: 'LA Galaxy goals by MLS season', category: 'Sports' },
  { text: 'Seattle Sounders vs Portland Timbers xG this season', category: 'Sports' },
  { text: 'Compare Inter Miami and LAFC expected goals by season', category: 'Sports' },
  { text: 'Austin FC xG at home this season, weekly', category: 'Sports' },
  // Stocks & Finance
  { text: 'Tesla stock price last 6 months, weekly', category: 'Finance' },
  { text: 'Compare Apple and Microsoft stock prices this year', category: 'Finance' },
  { text: 'Bitcoin vs Ethereum price last 3 months, normalized', category: 'Finance' },
  { text: 'NVIDIA trading volume last quarter', category: 'Finance' },
  // Tech & Open Source
  { text: 'FastAPI downloads this year with rolling average', category: 'Tech' },
  { text: 'Compare pandas, numpy, and polars downloads monthly', category: 'Tech' },
  { text: 'Correlate React and TypeScript npm downloads', category: 'Tech' },
  { text: 'Python requests vs httpx weekly downloads', category: 'Tech' },
  // Wikipedia & Culture
  { text: 'ChatGPT Wikipedia views last 90 days', category: 'Culture' },
  { text: 'Compare Python and JavaScript Wikipedia page views', category: 'Culture' },
  { text: 'Taylor Swift Wikipedia traffic with rolling average', category: 'Culture' },
  // Weather with meteorological seasons
  { text: 'Seattle temperature by meteorological season', category: 'Weather' },
  { text: 'Compare New York and Miami temperature monthly', category: 'Weather' },
  { text: 'Chicago precipitation last year by season', category: 'Weather' },
]

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
  const [showHelp, setShowHelp] = useState(false)

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

  const handleExampleClick = (query: string) => {
    setText(query)
    setShowHelp(false)
  }

  return (
    <Box sx={{ mb: 3 }}>
      <form onSubmit={handleSubmit}>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            fullWidth
            size="small"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Describe what you want to analyze in plain English..."
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
          <Button
            variant="outlined"
            size="small"
            onClick={() => setShowHelp(!showHelp)}
            sx={{ minWidth: 40, px: 1 }}
          >
            <HelpOutlineIcon fontSize="small" />
          </Button>
        </Box>
      </form>

      <Collapse in={showHelp}>
        <Box
          sx={{
            mt: 2,
            p: 2,
            borderRadius: 2,
            bgcolor: 'background.paper',
            border: 1,
            borderColor: 'divider',
          }}
        >
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Try these examples — click to use
          </Typography>
          {['Sports', 'Finance', 'Tech', 'Culture', 'Weather'].map((category) => (
            <Box key={category} sx={{ mb: 1.5 }}>
              <Typography
                variant="caption"
                sx={{
                  color: 'primary.main',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: 0.5,
                }}
              >
                {category}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 0.5 }}>
                {EXAMPLE_QUERIES.filter((q) => q.category === category).map((q, i) => (
                  <Chip
                    key={i}
                    label={q.text}
                    size="small"
                    variant="outlined"
                    onClick={() => handleExampleClick(q.text)}
                    sx={{
                      cursor: 'pointer',
                      '&:hover': {
                        bgcolor: 'action.hover',
                        borderColor: 'primary.main',
                      },
                    }}
                  />
                ))}
              </Box>
            </Box>
          ))}
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            Tip: Use "vs" or "compare" to overlay series. Say "correlate" to find relationships.
            Try "by MLS season" or "by meteorological season" for custom aggregation.
            Add "normalized" or "rolling average" for transforms.
          </Typography>
        </Box>
      </Collapse>

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
