import type { Recruiter } from '../api/types'

interface RecruiterSelectProps {
  recruiters: readonly Recruiter[]
  selectedId: string
  onChange: (recruiterId: string) => void
}

export function RecruiterSelect({ recruiters, selectedId, onChange }: RecruiterSelectProps) {
  return (
    <label className="field">
      <span className="field-label">Recruiter</span>
      <select value={selectedId} onChange={(event) => onChange(event.target.value)}>
        {recruiters.map((recruiter) => (
          <option key={recruiter.id} value={recruiter.id}>
            {recruiter.name} {recruiter.isAdmin ? '(admin)' : ''}
          </option>
        ))}
      </select>
    </label>
  )
}
