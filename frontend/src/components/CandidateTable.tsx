import type { Candidate } from '../api/types'

interface CandidateTableProps {
  candidates: readonly Candidate[]
  loading: boolean
}

export function CandidateTable({ candidates, loading }: CandidateTableProps) {
  if (loading) {
    return <p className="status-message">Loading candidates…</p>
  }

  if (candidates.length === 0) {
    return <p className="status-message">No candidates match this recruiter's regions and filters.</p>
  }

  return (
    <table className="candidate-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Email</th>
          <th>Region</th>
          <th>Role</th>
          <th>Status</th>
          <th>Applied</th>
        </tr>
      </thead>
      <tbody>
        {candidates.map((candidate) => (
          <tr key={candidate.id}>
            <td>{candidate.name}</td>
            <td>{candidate.email}</td>
            <td>{candidate.region}</td>
            <td>{candidate.role ?? '—'}</td>
            <td>
              <span className={`status-pill status-${candidate.status}`}>{candidate.status}</span>
            </td>
            <td>{candidate.applied_date ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
