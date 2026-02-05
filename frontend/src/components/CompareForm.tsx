import { useState, useEffect, useCallback } from 'react'
import Autocomplete from '@mui/material/Autocomplete'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import FormControl from '@mui/material/FormControl'
import IconButton from '@mui/material/IconButton'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import Select from '@mui/material/Select'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import AddIcon from '@mui/icons-material/Add'
import CloseIcon from '@mui/icons-material/Close'
import type { CompareItem, DataSourceInfo, FormField, LookupItem } from '../api/types'
import { fetchLookup } from '../api/client'

interface Props {
  sources: DataSourceInfo[]
  loading: boolean
  onSubmit: (items: CompareItem[]) => void
}

interface Slot {
  source: string
  fieldValues: Record<string, string>
}

function emptySlot(): Slot {
  return { source: '', fieldValues: {} }
}

export function CompareForm({ sources, loading, onSubmit }: Props) {
  const [slots, setSlots] = useState<Slot[]>([emptySlot(), emptySlot()])
  const [lookupCache, setLookupCache] = useState<Record<string, LookupItem[]>>({})
  const [lookupLoading, setLookupLoading] = useState<Record<string, boolean>>({})

  const updateSlot = (index: number, update: Partial<Slot>) => {
    setSlots((prev) => prev.map((s, i) => (i === index ? { ...s, ...update } : s)))
  }

  const setSlotField = (index: number, name: string, value: string, formFields: FormField[]) => {
    setSlots((prev) =>
      prev.map((s, i) => {
        if (i !== index) return s
        const next = { ...s.fieldValues, [name]: value }
        for (const f of formFields) {
          if (f.depends_on === name) next[f.name] = ''
        }
        return { ...s, fieldValues: next }
      }),
    )
  }

  const addSlot = () => {
    if (slots.length < 3) setSlots((prev) => [...prev, emptySlot()])
  }

  const removeSlot = (index: number) => {
    if (slots.length > 2) setSlots((prev) => prev.filter((_, i) => i !== index))
  }

  const loadLookup = useCallback(
    async (source: string, field: FormField, fieldValues: Record<string, string>) => {
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
    [lookupCache, lookupLoading],
  )

  // Load lookups when slot fields change
  useEffect(() => {
    for (const slot of slots) {
      if (!slot.source) continue
      const src = sources.find((s) => s.name === slot.source)
      if (!src) continue
      for (const field of src.form_fields) {
        if (field.field_type === 'autocomplete') {
          loadLookup(slot.source, field, slot.fieldValues)
        }
      }
    }
  }, [slots, sources, loadLookup])

  const getLookupItems = (source: string, field: FormField, fieldValues: Record<string, string>): LookupItem[] => {
    const depValue = field.depends_on ? fieldValues[field.depends_on] : ''
    const cacheKey = `${source}:${field.name}:${depValue}`
    return lookupCache[cacheKey] || []
  }

  const buildQuery = (slot: Slot): string => {
    const src = sources.find((s) => s.name === slot.source)
    if (!src) return ''
    const fields = src.form_fields
    if (fields.length === 0) return ''
    if (fields.length === 1 && fields[0].name === 'query') {
      return slot.fieldValues['query'] || ''
    }
    return fields.map((f) => slot.fieldValues[f.name] || '').join(':')
  }

  const isSlotComplete = (slot: Slot): boolean => {
    if (!slot.source) return false
    const src = sources.find((s) => s.name === slot.source)
    if (!src) return false
    return src.form_fields.every((f) => slot.fieldValues[f.name]?.trim())
  }

  const canSubmit = slots.filter(isSlotComplete).length >= 2

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const items: CompareItem[] = slots
      .filter(isSlotComplete)
      .map((slot) => ({ source: slot.source, query: buildQuery(slot) }))
    if (items.length >= 2) onSubmit(items)
  }

  const renderField = (slotIndex: number, slot: Slot, field: FormField) => {
    const formFields = sources.find((s) => s.name === slot.source)?.form_fields || []

    if (field.field_type === 'text') {
      return (
        <TextField
          key={`${slotIndex}-${field.name}`}
          size="small"
          label={field.label}
          value={slot.fieldValues[field.name] || ''}
          onChange={(e) => setSlotField(slotIndex, field.name, e.target.value, formFields)}
          placeholder={field.placeholder}
          sx={{ minWidth: 150, flex: 1 }}
        />
      )
    }

    if (field.field_type === 'select') {
      const disabled = field.depends_on ? !slot.fieldValues[field.depends_on] : false
      return (
        <FormControl key={`${slotIndex}-${field.name}`} size="small" sx={{ minWidth: 130 }} disabled={disabled}>
          <InputLabel>{field.label}</InputLabel>
          <Select
            value={slot.fieldValues[field.name] || ''}
            label={field.label}
            onChange={(e) => setSlotField(slotIndex, field.name, e.target.value, formFields)}
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
      const items = getLookupItems(slot.source, field, slot.fieldValues)
      const disabled = field.depends_on ? !slot.fieldValues[field.depends_on] : false
      const selectedItem = items.find((item) => item.value === slot.fieldValues[field.name]) || null
      return (
        <Autocomplete
          key={`${slotIndex}-${field.name}`}
          size="small"
          sx={{ minWidth: 180 }}
          options={items}
          getOptionLabel={(opt) => opt.label}
          value={selectedItem}
          onChange={(_e, newValue) => {
            setSlotField(slotIndex, field.name, newValue?.value || '', formFields)
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
          {slots.map((slot, index) => {
            const src = sources.find((s) => s.name === slot.source)
            const formFields = src?.form_fields || []
            return (
              <Box
                key={index}
                sx={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 1.5,
                  alignItems: 'flex-end',
                  mb: index < slots.length - 1 ? 2 : 0,
                  pb: index < slots.length - 1 ? 2 : 0,
                  borderBottom: index < slots.length - 1 ? '1px solid' : 'none',
                  borderColor: 'divider',
                }}
              >
                <Typography variant="caption" color="text.secondary" sx={{ width: 24, pb: 1, fontWeight: 600 }}>
                  {index + 1}.
                </Typography>
                <FormControl size="small" sx={{ minWidth: 160 }}>
                  <InputLabel>Source</InputLabel>
                  <Select
                    value={slot.source}
                    label="Source"
                    onChange={(e) => updateSlot(index, { source: e.target.value, fieldValues: {} })}
                  >
                    {sources.map((s) => (
                      <MenuItem key={s.name} value={s.name}>
                        {s.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                {formFields.map((f) => renderField(index, slot, f))}

                {slots.length > 2 && (
                  <IconButton size="small" onClick={() => removeSlot(index)} sx={{ mb: 0.5 }}>
                    <CloseIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
            )
          })}

          <Box sx={{ display: 'flex', gap: 1.5, mt: 2, alignItems: 'center' }}>
            {slots.length < 3 && (
              <Button size="small" startIcon={<AddIcon />} onClick={addSlot}>
                Add series
              </Button>
            )}
            <Box sx={{ flex: 1 }} />
            <Button type="submit" variant="contained" disabled={loading || !canSubmit}>
              {loading ? 'Loading...' : 'Compare'}
            </Button>
          </Box>
        </form>
      </CardContent>
    </Card>
  )
}
