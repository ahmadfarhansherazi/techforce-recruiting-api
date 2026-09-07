import { useEffect, useRef, useState } from 'react'
import { Debouncer } from '../util/Debouncer'

interface SearchInputProps {
  onDebouncedChange: (value: string) => void
  delayMs?: number
}

export function SearchInput({ onDebouncedChange, delayMs = 300 }: SearchInputProps) {
  const [value, setValue] = useState('')
  const debouncerRef = useRef<Debouncer>(new Debouncer(delayMs))

  useEffect(() => {
    const debouncer = debouncerRef.current
    return () => debouncer.cancel()
  }, [])

  const handleChange = (next: string) => {
    setValue(next)
    debouncerRef.current.run(() => onDebouncedChange(next))
  }

  return (
    <label className="field">
      <span className="field-label">Search</span>
      <input
        type="text"
        value={value}
        placeholder="Name or email"
        onChange={(event) => handleChange(event.target.value)}
      />
    </label>
  )
}
