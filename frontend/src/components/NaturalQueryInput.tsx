import { useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Collapse from '@mui/material/Collapse'
import Link from '@mui/material/Link'
import InputAdornment from '@mui/material/InputAdornment'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import SearchIcon from '@mui/icons-material/Search'
import { addToWatchlist, parseNaturalQuery } from '../api/client'
import { isAlertResult, isCompareResult } from '../api/types'
import type { NaturalAlertResponse, NaturalCompareItem } from '../api/types'
import { formatPrecise } from '../utils/format'

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
  const [alertResult, setAlertResult] = useState<NaturalAlertResponse | null>(null)
  const [alertAdding, setAlertAdding] = useState(false)
  const [alertSuccess, setAlertSuccess] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!text.trim() || text.trim().length < 3) return

    setParsing(true)
    setError('')
    setSuggestions([])
    setInterpretation('')
    setAlertResult(null)
    setAlertSuccess('')

    try {
      const result = await parseNaturalQuery(text.trim())
      setInterpretation(result.interpretation)
      if (isAlertResult(result)) {
        setAlertResult(result)
      } else if (isCompareResult(result)) {
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

  const handleAlertConfirm = async () => {
    if (!alertResult) return
    setAlertAdding(true)
    try {
      await addToWatchlist({
        name: alertResult.name,
        source: alertResult.source,
        query: alertResult.query,
        threshold_direction: alertResult.threshold_direction,
        threshold_value: alertResult.threshold_value,
      })
      setAlertSuccess(`Added "${alertResult.name}" to watchlist`)
      setAlertResult(null)
    } catch {
      setError('Failed to add alert to watchlist')
    } finally {
      setAlertAdding(false)
    }
  }

  const handleAlertCancel = () => {
    setAlertResult(null)
  }

  return (
    <Box sx={{ mb: 2 }}>
      <form onSubmit={handleSubmit}>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'stretch' }}>
          <TextField
            fullWidth
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Ask about any trend, e.g. fastapi downloads this year"
            disabled={parsing}
            autoFocus
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon color="action" />
                  </InputAdornment>
                ),
                sx: { fontSize: { xs: '1rem', sm: '1.1rem' }, bgcolor: 'background.paper', borderRadius: 2 },
              },
              htmlInput: { 'aria-label': 'Ask in plain English' },
            }}
          />
          <Button
            type="submit"
            variant="contained"
            disabled={isDisabled}
            sx={{ whiteSpace: 'nowrap', minWidth: { xs: 64, sm: 96 } }}
          >
            {parsing ? <CircularProgress size={20} color="inherit" /> : 'Ask'}
          </Button>
          <Tooltip title="Examples">
            <Button
              variant="outlined"
              onClick={() => setShowHelp(!showHelp)}
              sx={{ minWidth: 44, px: 1 }}
              aria-label="Show example questions"
            >
              <HelpOutlineIcon fontSize="small" />
            </Button>
          </Tooltip>
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
            Add "normalized" to put series on a common scale.
          </Typography>
        </Box>
      </Collapse>

      {interpretation && (
        <Alert severity="success" sx={{ mt: 1 }}>
          {interpretation}
        </Alert>
      )}

      {alertResult && (
        <Alert
          severity="info"
          sx={{ mt: 1 }}
          action={
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                size="small"
                variant="contained"
                onClick={handleAlertConfirm}
                disabled={alertAdding}
              >
                {alertAdding ? <CircularProgress size={16} color="inherit" /> : 'Add to Watchlist'}
              </Button>
              <Button size="small" onClick={handleAlertCancel}>
                Cancel
              </Button>
            </Box>
          }
        >
          <Typography variant="subtitle2" gutterBottom>
            Create alert: {alertResult.name}
          </Typography>
          <Typography variant="body2">
            Source: {alertResult.source} &middot; Query: {alertResult.query} &middot;{' '}
            Trigger: {alertResult.threshold_direction} {formatPrecise(alertResult.threshold_value)}
          </Typography>
        </Alert>
      )}

      {alertSuccess && (
        <Alert severity="success" sx={{ mt: 1 }} onClose={() => setAlertSuccess('')}>
          {alertSuccess}
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
