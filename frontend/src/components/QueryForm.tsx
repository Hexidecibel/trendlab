import { useState, useEffect, useCallback, useRef } from 'react'
import Autocomplete from '@mui/material/Autocomplete'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import FormControl from '@mui/material/FormControl'
import InputLabel from '@mui/material/InputLabel'
import Link from '@mui/material/Link'
import MenuItem from '@mui/material/MenuItem'
import Select from '@mui/material/Select'
import TextField from '@mui/material/TextField'
import type { DataSourceInfo, FormField, LookupItem } from '../api/types'
import { fetchLookup } from '../api/client'

export interface QueryPrefill {
  source: string
  query: string
  horizon: number
  start?: string
  end?: string
}

interface Props {
  sources: DataSourceInfo[]
  loading: boolean
  onSubmit: (source: string, query: string, horizon: number, start?: string, end?: string) => void
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
      const cacheKey = `${source}:${field.name}:${depValue}`

      if (lookupCache[cacheKey] || lookupLoading[cacheKey]) return
      if (field.depends_on && !depValue) return

      setLookupLoading((prev) => ({ ...prev, [cacheKey]: true }))
      try {
        const items = await fetchLookup(
          source,
          field.name === 'entity' ? 'teams' : field.name,
          depValue || undefined,
        )
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const query = buildQuery()
    if (source && query) {
      onSubmit(source, query, horizon, startDate || undefined, endDate || undefined)
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

  const getLookupItems = (field: FormField): LookupItem[] => {
    const depValue = field.depends_on ? fieldValues[field.depends_on] : ''
    const cacheKey = `${source}:${field.name}:${depValue}`
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
              <TextField
                size="small"
                label="Horizon"
                type="number"
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
                slotProps={{ htmlInput: { min: 1, max: 365 } }}
                sx={{ width: 100 }}
              />
            )}

            {source && (
              <Link
                component="button"
                type="button"
                variant="body2"
                onClick={() => setShowDateRange(!showDateRange)}
                sx={{ alignSelf: 'center', pb: 0.5 }}
              >
                {showDateRange ? 'Hide dates' : 'Date range'}
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
          </Box>

          {showDateRange && source && (
            <Box sx={{ display: 'flex', gap: 1.5, mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
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
              {(startDate || endDate) && (
                <Link
                  component="button"
                  type="button"
                  variant="body2"
                  onClick={() => { setStartDate(''); setEndDate('') }}
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
