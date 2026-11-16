import { useMemo, useState } from 'react'
import { Search, X } from 'lucide-react'
import type { HaEntity } from '../types'

function normalize(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}

export function EntityPicker({
  entities,
  value,
  onChange,
  emptyLabel,
  placeholder = 'Buscar por nombre o entity_id…',
  hint,
  disabled = false,
}: {
  entities: HaEntity[]
  value: string
  onChange: (value: string) => void
  emptyLabel: string
  placeholder?: string
  hint?: string
  disabled?: boolean
}) {
  const [query, setQuery] = useState('')
  const normalizedQuery = normalize(query.trim())

  const selectedEntity = entities.find((entity) => entity.entity_id === value)
  const filtered = useMemo(() => {
    if (!normalizedQuery) return entities
    return entities.filter((entity) => {
      const haystack = normalize(
        `${entity.name} ${entity.entity_id} ${entity.domain} ${entity.state}`,
      )
      return haystack.includes(normalizedQuery)
    })
  }, [entities, normalizedQuery])

  const options = useMemo(() => {
    let result = filtered
    if (selectedEntity && !result.some((entity) => entity.entity_id === selectedEntity.entity_id)) {
      result = [selectedEntity, ...result]
    }
    if (value && !entities.some((entity) => entity.entity_id === value)) {
      result = [
        {
          entity_id: value,
          name: value,
          domain: value.split('.', 1)[0],
          state: '',
          unit: null,
          device_class: null,
          state_class: null,
        },
        ...result,
      ]
    }
    return result
  }, [entities, filtered, selectedEntity, value])

  return (
    <div className="entity-picker">
      <div className="entity-search">
        <Search size={14} className="entity-search-icon" />
        <input
          className="input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={placeholder}
          aria-label={placeholder}
          disabled={disabled}
        />
        {query ? (
          <button
            type="button"
            className="entity-search-clear"
            onClick={() => setQuery('')}
            aria-label="Limpiar búsqueda de entidades"
          >
            <X size={13} />
          </button>
        ) : null}
      </div>
      <select
        className="select"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      >
        <option value="">{emptyLabel}</option>
        {options.map((entity) => (
          <option value={entity.entity_id} key={entity.entity_id}>
            {entity.name} · {entity.entity_id}
          </option>
        ))}
      </select>
      <div className="entity-picker-meta">
        <span>
          {options.length} {options.length === 1 ? 'entidad' : 'entidades'}
          {query ? ` de ${entities.length}` : ''}
        </span>
        {hint ? <span>{hint}</span> : null}
      </div>
    </div>
  )
}
