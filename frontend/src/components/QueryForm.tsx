import { useState, useEffect, useCallback } from 'react'
import Autocomplete from '@mui/material/Autocomplete'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Collapse from '@mui/material/Collapse'
import FormControl from '@mui/material/FormControl'
import InputLabel from '@mui/material/InputLabel'
import IconButton from '@mui/material/IconButton'
import Link from '@mui/material/Link'
import MenuItem from '@mui/material/MenuItem'
import Select from '@mui/material/Select'
import Slider from '@mui/material/Slider'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import RefreshIcon from '@mui/icons-material/Refresh'
import type { DataSourceInfo, FormField, LookupItem } from '../api/types'
import { fetchLookup } from '../api/client'
import { CSVUpload } from './CSVUpload'

export interface QueryPrefill {
  source: string
  query: string
  horizon: number
  start?: string
  end?: string
  resample?: string
}

interface Props {
  sources: DataSourceInfo[]
  loading: boolean
  onSubmit: (source: string, query: string, horizon: number, start?: string, end?: string, resample?: string, apply?: string, refresh?: boolean) => void
  prefill?: QueryPrefill | null
  onSourceChange?: (source: string) => void
}

/**
 * Fields shown up front, per source. Everything else from the backend's
 * form_fields metadata goes into "Advanced" with a default filled in.
 * Sources not listed here show all their fields up front.
 */
const PRIMARY_FIELDS: Record<string, string[]> = {
  wikipedia: ['project', 'article'],
  weather: ['location', 'metric'],
  stocks: ['symbol', 'metric'],
  asa: ['league', 'team', 'metric'],
  google_trends: ['keyword', 'timeframe'],
}

/** Explicit defaults for select fields; other selects default to their first option. */
const FIELD_DEFAULTS: Record<string, Record<string, string>> = {
  wikipedia: { project: 'en.wikipedia', access: 'all-access', agent: 'user', granularity: 'daily' },
  weather: { temp_unit: 'celsius', wind_unit: 'kmh', precip_unit: 'mm' },
  stocks: { interval: '1d', range: '1y' },
  asa: { home_away: 'all', stage: 'all' },
}

/** Fields allowed to be blank when submitting. */
const OPTIONAL_FIELDS: Record<string, string[]> = {
  google_trends: ['geo'],
}

const EMPTY_FIELDS: FormField[] = []

function isPrimary(source: string, field: FormField): boolean {
  const allow = PRIMARY_FIELDS[source]
  return !allow || allow.includes(field.name)
}

function defaultValues(source: string, fields: FormField[]): Record<string, string> {
  const explicit = FIELD_DEFAULTS[source] || {}
  const values: Record<string, string> = {}
  for (const f of fields) {
    if (f.field_type !== 'select' || f.depends_on || f.options.length === 0) continue
    const wanted = explicit[f.name]
    values[f.name] = wanted && f.options.some((o) => o.value === wanted) ? wanted : f.options[0].value
  }
  return values
}

function decomposeQuery(query: string, formFields: FormField[]): Record<string, string> {
  if (formFields.length === 0) return {}
  if (formFields.length === 1 && formFields[0].name === 'query') {
    return { query }
  }
  const parts = query.split(':')
  const values: Record<string, string> = {}
  formFields.forEach((f, i) => {
    if (parts[i]) values[f.name] = parts[i]
  })
  return values
}

export function QueryForm({ sources, loading, onSubmit, prefill, onSourceChange }: Props) {
  const [source, setSource] = useState('')
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
  const [horizon, setHorizon] = useState(14)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [resample, setResample] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [lookupCache, setLookupCache] = useState<Record<string, LookupItem[]>>({})
  const [lookupLoading, setLookupLoading] = useState<Record<string, boolean>>({})
  const [lastPrefill, setLastPrefill] = useState<QueryPrefill | null>(null)
  const [csvRefreshKey, setCsvRefreshKey] = useState(0)

  const selectedSource = sources.find((s) => s.name === source)
  const formFields = selectedSource?.form_fields ?? EMPTY_FIELDS
  const primaryFields = formFields.filter((f) => isPrimary(source, f))
  const advancedFields = formFields.filter((f) => !isPrimary(source, f))

  // Apply a new prefill (NL result, saved view, recent query) during render.
  if (prefill && prefill !== lastPrefill) {
    setLastPrefill(prefill)
    setSource(prefill.source)
    setHorizon(prefill.horizon)
    setResample(prefill.resample === 'season' ? 'year' : prefill.resample || '')
    setStartDate(prefill.start || '')
    setEndDate(prefill.end || '')
    const targetSource = sources.find((s) => s.name === prefill.source)
    if (targetSource) {
      setFieldValues({
        ...defaultValues(prefill.source, targetSource.form_fields),
        ...decomposeQuery(prefill.query, targetSource.form_fields),
      })
    } else {
      setFieldValues({})
    }
  }

  const handleSourceChange = (next: string) => {
    setSource(next)
    const target = sources.find((s) => s.name === next)
    setFieldValues(target ? defaultValues(next, target.form_fields) : {})
    onSourceChange?.(next)
  }

  const lookupKey = useCallback(
    (field: FormField) => {
      const depValue = field.depends_on ? fieldValues[field.depends_on] : ''
      return `${source}:${field.name}:${depValue}:${csvRefreshKey}`
    },
    [source, fieldValues, csvRefreshKey],
  )

  const loadLookup = useCallback(
    async (field: FormField) => {
      if (field.field_type !== 'autocomplete') return
      const depValue = field.depends_on ? fieldValues[field.depends_on] : ''
      const cacheKey = lookupKey(field)
      if (lookupCache[cacheKey] || lookupLoading[cacheKey]) return
      if (field.depends_on && !depValue) return

      setLookupLoading((prev) => ({ ...prev, [cacheKey]: true }))
      try {
        const depends: Record<string, string> = {}
        if (field.depends_on && depValue) {
          depends[field.depends_on] = depValue
        }
        const items = await fetchLookup(source, field.name, depends)
        setLookupCache((prev) => ({ ...prev, [cacheKey]: items }))
      } catch {
        // Silently fail
      } finally {
        setLookupLoading((prev) => ({ ...prev, [cacheKey]: false }))
      }
    },
    [source, fieldValues, lookupCache, lookupLoading, lookupKey],
  )

  useEffect(() => {
    for (const field of formFields) {
      if (field.field_type === 'autocomplete') {
        loadLookup(field)
      }
    }
  }, [formFields, loadLookup])

  const buildQuery = (): string => {
    if (formFields.length === 0) return ''
    if (formFields.length === 1 && formFields[0].name === 'query') {
      return fieldValues['query'] || ''
    }
    return formFields.map((f) => fieldValues[f.name] || '').join(':')
  }

  const handleSubmit = (e: React.FormEvent, refresh?: boolean) => {
    e.preventDefault()
    const query = buildQuery()
    if (source && query) {
      onSubmit(source, query, horizon, startDate || undefined, endDate || undefined, resample || undefined, undefined, refresh)
    }
  }

  const setField = (name: string, value: string) => {
    setFieldValues((prev) => {
      const next = { ...prev, [name]: value }
      for (const f of formFields) {
        if (f.depends_on === name) {
          next[f.name] = ''
        }
      }
      return next
    })
  }

  const handleCsvUploadComplete = (uploadId: string) => {
    setCsvRefreshKey((k) => k + 1)
    setFieldValues({ query: uploadId })
  }

  const optional = OPTIONAL_FIELDS[source] || []
  const isComplete =
    !!source &&
    formFields.every(
      (f) => optional.includes(f.name) || (fieldValues[f.name] && fieldValues[f.name].trim() !== ''),
    )

  const itemSx = { flex: '1 1 180px', minWidth: 0 }

  const renderField = (field: FormField) => {
    if (field.field_type === 'text') {
      return (
        <TextField
          key={`${source}-${field.name}`}
          size="small"
          label={field.label}
          value={fieldValues[field.name] || ''}
          onChange={(e) => setField(field.name, e.target.value)}
          placeholder={field.placeholder}
          sx={itemSx}
        />
      )
    }

    if (field.field_type === 'select') {
      const disabled = field.depends_on ? !fieldValues[field.depends_on] : false
      return (
        <FormControl key={`${source}-${field.name}`} size="small" sx={itemSx} disabled={disabled}>
          <InputLabel>{field.label}</InputLabel>
          <Select
            value={fieldValues[field.name] || ''}
            label={field.label}
            onChange={(e) => setField(field.name, e.target.value)}
          >
            {field.options.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )
    }

    if (field.field_type === 'autocomplete') {
      const items = lookupCache[lookupKey(field)] || []
      const disabled = field.depends_on ? !fieldValues[field.depends_on] : false
      const selectedItem = items.find((item) => item.value === fieldValues[field.name]) || null

      return (
        <Autocomplete
          key={`${source}-${field.name}`}
          size="small"
          sx={{ flex: '1 1 220px', minWidth: 0 }}
          options={items}
          getOptionLabel={(opt) => opt.label}
          value={selectedItem}
          onChange={(_e, newValue) => {
            setField(field.name, newValue?.value || '')
          }}
          loading={items.length === 0 && !disabled}
          disabled={disabled}
          renderInput={(params) => (
            <TextField
              {...params}
              label={field.label}
              placeholder={disabled ? 'Select above first...' : field.placeholder}
            />
          )}
        />
      )
    }

    return null
  }

  return (
    <form onSubmit={handleSubmit}>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, alignItems: 'center' }}>
        <FormControl size="small" sx={{ flex: '1 1 200px', minWidth: 0 }}>
          <InputLabel>Source</InputLabel>
          <Select
            value={source}
            label="Source"
            onChange={(e) => handleSourceChange(e.target.value)}
            renderValue={(v) => v}
          >
            {sources.map((s) => (
              <MenuItem key={s.name} value={s.name}>
                {s.name} &mdash; {s.description}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {primaryFields.map(renderField)}

        {source && (
          <FormControl size="small" sx={{ flex: '0 1 130px', minWidth: 110 }}>
            <InputLabel>Resample</InputLabel>
            <Select value={resample} label="Resample" onChange={(e) => setResample(e.target.value)}>
              <MenuItem value="">None</MenuItem>
              <MenuItem value="week">Weekly</MenuItem>
              <MenuItem value="month">Monthly</MenuItem>
              <MenuItem value="quarter">Quarterly</MenuItem>
              <MenuItem value="year">Yearly</MenuItem>
              {selectedSource?.resample_periods?.map((period) => (
                <MenuItem key={period.value} value={period.value}>
                  {period.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}

        {source && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Button type="submit" variant="contained" disabled={loading || !isComplete}>
              {loading ? 'Loading...' : 'Analyze'}
            </Button>
            {isComplete && !loading && (
              <Tooltip title="Refresh (bypass cache)">
                <IconButton size="small" onClick={(e) => handleSubmit(e as unknown as React.FormEvent, true)}>
                  <RefreshIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        )}
      </Box>

      {source === 'csv' && (
        <Box sx={{ mt: 1.5 }}>
          <CSVUpload onUploadComplete={handleCsvUploadComplete} />
        </Box>
      )}

      {source && (
        <Box sx={{ mt: 1.5 }}>
          <Link
            component="button"
            type="button"
            variant="body2"
            underline="hover"
            onClick={() => setShowAdvanced(!showAdvanced)}
            sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.25 }}
          >
            Advanced
            <ExpandMoreIcon
              fontSize="small"
              sx={{ transition: 'transform 0.2s', transform: showAdvanced ? 'rotate(180deg)' : 'none' }}
            />
            {(startDate || endDate) && !showAdvanced && (
              <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                (date range set)
              </Typography>
            )}
          </Link>
          <Collapse in={showAdvanced}>
            <Box
              sx={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 1.5,
                mt: 1.5,
                pt: 1.5,
                borderTop: '1px solid',
                borderColor: 'divider',
                alignItems: 'center',
              }}
            >
              {advancedFields.map(renderField)}
              <TextField
                size="small"
                label="Start date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                sx={{ flex: '1 1 150px' }}
              />
              <TextField
                size="small"
                label="End date"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                sx={{ flex: '1 1 150px' }}
              />
              <Box sx={{ flex: '1 1 180px', px: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Forecast horizon: {horizon} periods
                </Typography>
                <Slider
                  size="small"
                  value={horizon}
                  onChange={(_, v) => setHorizon(v as number)}
                  min={7}
                  max={90}
                  step={7}
                  valueLabelDisplay="auto"
                />
              </Box>
              {(startDate || endDate) && (
                <Link
                  component="button"
                  type="button"
                  variant="body2"
                  onClick={() => {
                    setStartDate('')
                    setEndDate('')
                  }}
                >
                  Clear dates
                </Link>
              )}
            </Box>
          </Collapse>
        </Box>
      )}
    </form>
  )
}
