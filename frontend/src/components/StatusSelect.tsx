import { CANDIDATE_STATUSES, type CandidateStatus } from '../api/types'

interface StatusSelectProps {
  value: CandidateStatus | ''
  onChange: (status: CandidateStatus | '') => void
}

export function StatusSelect({ value, onChange }: StatusSelectProps) {
  return (
    <label className="field">
      <span className="field-label">Status</span>
      <select value={value} onChange={(event) => onChange(event.target.value as CandidateStatus | '')}>
        <option value="">All</option>
        {CANDIDATE_STATUSES.map((status) => (
          <option key={status} value={status}>
            {status}
          </option>
        ))}
      </select>
    </label>
  )
}
