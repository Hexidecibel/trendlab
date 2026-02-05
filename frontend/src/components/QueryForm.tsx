import { useState, useEffect, useCallback, useRef } from 'react'
import Autocomplete from '@mui/material/Autocomplete'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
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
import RefreshIcon from '@mui/icons-material/Refresh'
import type { DataSourceInfo, FormField, LookupItem } from '../api/types'
import { fetchLookup } from '../api/client'

export interface QueryPrefill {
  source: string
  query: string
  horizon: number
  start?: string
  end?: string
  resample?: string
  apply?: string
}

interface Props {
  sources: DataSourceInfo[]
  loading: boolean
  onSubmit: (source: string, query: string, horizon: number, start?: string, end?: string, resample?: string, apply?: string, refresh?: boolean) => void
  prefill?: QueryPrefill | null
}

function decomposeQuery(query: string, formFields: FormField[]): Record<string, string> {
  if (formFields.length === 0) return {}
  if (formFields.length === 1 && formFields[0].name === 'query') {
    return { query }
  }
  const parts = query.split(':')
  const values: Record<string, string> = {}
  formFields.forEach((f, i) => {
    values[f.name] = parts[i] || ''
  })
  return values
}

export function QueryForm({ sources, loading, onSubmit, prefill }: Props) {
  const [source, setSource] = useState('')
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
  const [horizon, setHorizon] = useState(14)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [resample, setResample] = useState('')
  const [apply, setApply] = useState('')
  const [showDateRange, setShowDateRange] = useState(false)
  const [lookupCache, setLookupCache] = useState<Record<string, LookupItem[]>>({})
  const [lookupLoading, setLookupLoading] = useState<Record<string, boolean>>({})
  const [lastPrefill, setLastPrefill] = useState<QueryPrefill | null>(null)
  const prefillRef = useRef(false)

  const selectedSource = sources.find((s) => s.name === source)
  const formFields = selectedSource?.form_fields || []

  // Apply prefill when it changes
  useEffect(() => {
    if (!prefill || prefill === lastPrefill) return
    setLastPrefill(prefill)
    prefillRef.current = true
    setSource(prefill.source)
    setHorizon(prefill.horizon)
    setResample(prefill.resample || '')
    setApply(prefill.apply || '')
    if (prefill.start || prefill.end) {
      setStartDate(prefill.start || '')
      setEndDate(prefill.end || '')
      setShowDateRange(true)
    }
    // Decompose query into field values using the target source's form fields
    const targetSource = sources.find((s) => s.name === prefill.source)
    if (targetSource) {
      setFieldValues(decomposeQuery(prefill.query, targetSource.form_fields))
    }
  }, [prefill, lastPrefill, sources])

  useEffect(() => {
    if (prefillRef.current) {
      prefillRef.current = false
      return
    }
    setFieldValues({})
  }, [source])

  const loadLookup = useCallback(
    async (field: FormField) => {
      if (field.field_type !== 'autocomplete') return

      const depValue = field.depends_on ? fieldValues[field.depends_on] : ''
      // For entity field, also factor in entity_type to cache key
      const entityType = fieldValues['entity_type'] || ''
      const cacheKey = field.name === 'entity'
        ? `${source}:${field.name}:${depValue}:${entityType}`
        : `${source}:${field.name}:${depValue}`

      if (lookupCache[cacheKey] || lookupLoading[cacheKey]) return
      if (field.depends_on && !depValue) return

      setLookupLoading((prev) => ({ ...prev, [cacheKey]: true }))
      try {
        // Use entity_type value (teams/players) for lookup type
        const lookupType = field.name === 'entity'
          ? (fieldValues['entity_type'] || 'teams')
          : field.name
        // Build depends object with actual field name as key
        const depends: Record<string, string> = {}
        if (field.depends_on && depValue) {
          depends[field.depends_on] = depValue
        }
        const items = await fetchLookup(source, lookupType, depends)
        setLookupCache((prev) => ({ ...prev, [cacheKey]: items }))
      } catch {
        // Silently fail
      } finally {
        setLookupLoading((prev) => ({ ...prev, [cacheKey]: false }))
      }
    },
    [source, fieldValues, lookupCache, lookupLoading],
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
    const parts: string[] = []
    for (const field of formFields) {
      parts.push(fieldValues[field.name] || '')
    }
    return parts.join(':')
  }

  const handleSubmit = (e: React.FormEvent, refresh?: boolean) => {
    e.preventDefault()
    const query = buildQuery()
    if (source && query) {
      onSubmit(source, query, horizon, startDate || undefined, endDate || undefined, resample || undefined, apply || undefined, refresh)
    }
  }

  const setField = (name: string, value: string) => {
    setFieldValues((prev) => {
      const next = { ...prev, [name]: value }
      // Clear dependent fields
      for (const f of formFields) {
        if (f.depends_on === name) {
          next[f.name] = ''
        }
      }
      // Also clear entity when entity_type changes
      if (name === 'entity_type') {
        next['entity'] = ''
      }
      return next
    })
  }

  const getLookupItems = (field: FormField): LookupItem[] => {
    const depValue = field.depends_on ? fieldValues[field.depends_on] : ''
    const entityType = fieldValues['entity_type'] || ''
    const cacheKey = field.name === 'entity'
      ? `${source}:${field.name}:${depValue}:${entityType}`
      : `${source}:${field.name}:${depValue}`
    return lookupCache[cacheKey] || []
  }

  const isComplete =
    source &&
    formFields.every(
      (f) => fieldValues[f.name] && fieldValues[f.name].trim() !== '',
    )

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
          sx={{ minWidth: 200, flex: 1 }}
        />
      )
    }

    if (field.field_type === 'select') {
      const disabled = field.depends_on ? !fieldValues[field.depends_on] : false
      return (
        <FormControl
          key={`${source}-${field.name}`}
          size="small"
          sx={{ minWidth: 150 }}
          disabled={disabled}
        >
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
      const items = getLookupItems(field)
      const disabled = field.depends_on ? !fieldValues[field.depends_on] : false
      const selectedItem = items.find((item) => item.value === fieldValues[field.name]) || null

      return (
        <Autocomplete
          key={`${source}-${field.name}`}
          size="small"
          sx={{ minWidth: 220 }}
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
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <form onSubmit={handleSubmit}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, alignItems: 'flex-end' }}>
            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel>Source</InputLabel>
              <Select
                value={source}
                label="Source"
                onChange={(e) => setSource(e.target.value)}
              >
                {sources.map((s) => (
                  <MenuItem key={s.name} value={s.name}>
                    {s.name} &mdash; {s.description}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {formFields.map(renderField)}

            {source && (
              <Box sx={{ width: 180, px: 1 }}>
                <Typography variant="caption" color="text.secondary" gutterBottom>
                  Forecast: {horizon} days
                </Typography>
                <Slider
                  size="small"
                  value={horizon}
                  onChange={(_, v) => setHorizon(v as number)}
                  min={7}
                  max={90}
                  step={7}
                  marks={[
                    { value: 7, label: '7' },
                    { value: 30, label: '30' },
                    { value: 60, label: '60' },
                    { value: 90, label: '90' },
                  ]}
                  valueLabelDisplay="auto"
                />
              </Box>
            )}

            {source && (
              <FormControl size="small" sx={{ minWidth: 130 }}>
                <InputLabel>Resample</InputLabel>
                <Select
                  value={resample}
                  label="Resample"
                  onChange={(e) => setResample(e.target.value)}
                >
                  <MenuItem value="">None</MenuItem>
                  <MenuItem value="week">Weekly</MenuItem>
                  <MenuItem value="month">Monthly</MenuItem>
                  <MenuItem value="quarter">Quarterly</MenuItem>
                  <MenuItem value="season">Seasonal</MenuItem>
                  <MenuItem value="year">Yearly</MenuItem>
                </Select>
              </FormControl>
            )}

            {source && (
              <Link
                component="button"
                type="button"
                variant="body2"
                onClick={() => setShowDateRange(!showDateRange)}
                sx={{ alignSelf: 'center', pb: 0.5 }}
              >
                {showDateRange ? 'Hide options' : 'More options'}
              </Link>
            )}

            {source && (
              <Button
                type="submit"
                variant="contained"
                disabled={loading || !isComplete}
              >
                {loading ? 'Loading...' : 'Analyze'}
              </Button>
            )}

            {source && isComplete && !loading && (
              <Tooltip title="Refresh (bypass cache)">
                <IconButton
                  size="small"
                  onClick={(e) => handleSubmit(e as unknown as React.FormEvent, true)}
                >
                  <RefreshIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Box>

          {showDateRange && source && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider', alignItems: 'flex-end' }}>
              <TextField
                size="small"
                label="Start Date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                sx={{ width: 170 }}
              />
              <TextField
                size="small"
                label="End Date"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                sx={{ width: 170 }}
              />
              <TextField
                size="small"
                label="Transforms"
                value={apply}
                onChange={(e) => setApply(e.target.value)}
                placeholder="e.g. normalize|rolling_avg_7d"
                sx={{ minWidth: 220, flex: 1 }}
              />
              {(startDate || endDate || apply) && (
                <Link
                  component="button"
                  type="button"
                  variant="body2"
                  onClick={() => { setStartDate(''); setEndDate(''); setApply('') }}
                  sx={{ alignSelf: 'flex-end', pb: 0.5 }}
                >
                  Clear
                </Link>
              )}
            </Box>
          )}
        </form>
      </CardContent>
    </Card>
  )
}
