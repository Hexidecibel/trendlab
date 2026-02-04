import { useState, useEffect, useCallback } from 'react'
import type { DataSourceInfo, FormField, LookupItem } from '../api/types'
import { fetchLookup } from '../api/client'

interface Props {
  sources: DataSourceInfo[]
  loading: boolean
  onSubmit: (source: string, query: string, horizon: number) => void
}

export function QueryForm({ sources, loading, onSubmit }: Props) {
  const [source, setSource] = useState('')
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
  const [horizon, setHorizon] = useState(14)
  const [lookupCache, setLookupCache] = useState<
    Record<string, LookupItem[]>
  >({})
  const [lookupLoading, setLookupLoading] = useState<Record<string, boolean>>(
    {},
  )
  const [autocompleteSearch, setAutocompleteSearch] = useState<
    Record<string, string>
  >({})

  const selectedSource = sources.find((s) => s.name === source)
  const formFields = selectedSource?.form_fields || []

  // Reset field values when source changes
  useEffect(() => {
    setFieldValues({})
    setAutocompleteSearch({})
  }, [source])

  // Load lookup data for autocomplete fields when dependencies change
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
        // Silently fail — autocomplete just won't have options
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
    // Simple adapters: just use "query" field
    if (
      formFields.length === 1 &&
      formFields[0].name === 'query'
    ) {
      return fieldValues['query'] || ''
    }
    // Complex adapters: build colon-separated query
    // e.g., "mls:teams:jYQJ19EqGR:xgoals_for"
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
      onSubmit(source, query, horizon)
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

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-lg shadow p-4 mb-6"
    >
      <div className="flex flex-wrap gap-3 items-end">
        {/* Source selector */}
        <div className="min-w-[180px]">
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

        {/* Dynamic fields */}
        {formFields.map((field) => (
          <DynamicField
            key={`${source}-${field.name}`}
            field={field}
            value={fieldValues[field.name] || ''}
            onChange={(v) => setField(field.name, v)}
            lookupItems={getLookupItems(field)}
            searchText={autocompleteSearch[field.name] || ''}
            onSearchChange={(t) =>
              setAutocompleteSearch((prev) => ({
                ...prev,
                [field.name]: t,
              }))
            }
            disabled={
              field.depends_on
                ? !fieldValues[field.depends_on]
                : false
            }
          />
        ))}

        {/* Horizon */}
        {source && (
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
        )}

        {/* Submit */}
        {source && (
          <button
            type="submit"
            disabled={loading || !isComplete}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Loading...' : 'Analyze'}
          </button>
        )}
      </div>
    </form>
  )
}

interface DynamicFieldProps {
  field: FormField
  value: string
  onChange: (value: string) => void
  lookupItems: LookupItem[]
  searchText: string
  onSearchChange: (text: string) => void
  disabled: boolean
}

function DynamicField({
  field,
  value,
  onChange,
  lookupItems,
  searchText,
  onSearchChange,
  disabled,
}: DynamicFieldProps) {
  const [showDropdown, setShowDropdown] = useState(false)

  if (field.field_type === 'text') {
    return (
      <div className="flex-1 min-w-[200px]">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {field.label}
        </label>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
        />
      </div>
    )
  }

  if (field.field_type === 'select') {
    return (
      <div className="min-w-[150px]">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {field.label}
        </label>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm disabled:opacity-50"
        >
          <option value="">Select...</option>
          {field.options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    )
  }

  if (field.field_type === 'autocomplete') {
    const selectedLabel =
      lookupItems.find((item) => item.value === value)?.label || ''
    const filtered = lookupItems.filter((item) =>
      item.label.toLowerCase().includes(searchText.toLowerCase()),
    )

    return (
      <div className="min-w-[220px] relative">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {field.label}
        </label>
        <input
          type="text"
          value={showDropdown ? searchText : selectedLabel}
          onChange={(e) => {
            onSearchChange(e.target.value)
            if (!showDropdown) setShowDropdown(true)
            // Clear selection when typing
            if (value) onChange('')
          }}
          onFocus={() => {
            setShowDropdown(true)
            onSearchChange('')
          }}
          onBlur={() => {
            // Delay to allow click on dropdown item
            setTimeout(() => setShowDropdown(false), 200)
          }}
          placeholder={
            disabled ? 'Select above first...' : field.placeholder
          }
          disabled={disabled}
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm disabled:opacity-50"
        />
        {showDropdown && !disabled && filtered.length > 0 && (
          <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded shadow-lg max-h-48 overflow-y-auto">
            {filtered.map((item) => (
              <button
                key={item.value}
                type="button"
                className="w-full text-left px-3 py-1.5 text-sm hover:bg-blue-50 focus:bg-blue-50"
                onMouseDown={(e) => {
                  e.preventDefault()
                  onChange(item.value)
                  onSearchChange(item.label)
                  setShowDropdown(false)
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        )}
        {showDropdown &&
          !disabled &&
          lookupItems.length === 0 && (
            <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded shadow-lg px-3 py-2">
              <span className="text-xs text-gray-400">Loading...</span>
            </div>
          )}
      </div>
    )
  }

  return null
}
