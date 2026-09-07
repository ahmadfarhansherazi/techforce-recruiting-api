import { useEffect, useMemo, useState } from 'react'
import { ApiClient } from './api/ApiClient'
import { ApiError } from './api/ApiError'
import { RECRUITERS } from './api/recruiters'
import type { Candidate, CandidateStatus } from './api/types'
import { CandidateTable } from './components/CandidateTable'
import { Pagination } from './components/Pagination'
import { RecruiterSelect } from './components/RecruiterSelect'
import { SearchInput } from './components/SearchInput'
import { StatusSelect } from './components/StatusSelect'
import './index.css'

const PAGE_SIZE = 10

class InitialRecruiter {
  // Lets a link like ?recruiter=R-102 preselect a recruiter, otherwise the
  // first recruiter in the list is used.
  static resolve(): string {
    const requested = new URLSearchParams(window.location.search).get('recruiter')
    const match = RECRUITERS.find((recruiter) => recruiter.id === requested)
    return match ? match.id : RECRUITERS[0].id
  }
}

export function App() {
  const initialRecruiterId = useMemo(() => InitialRecruiter.resolve(), [])
  const apiClient = useMemo(() => new ApiClient('', initialRecruiterId), [initialRecruiterId])

  const [recruiterId, setRecruiterId] = useState(initialRecruiterId)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<CandidateStatus | ''>('')
  const [offset, setOffset] = useState(0)

  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Any filter change re-pages from the start.
  useEffect(() => {
    setOffset(0)
  }, [recruiterId, search, status])

  useEffect(() => {
    let cancelled = false
    apiClient.setRecruiterId(recruiterId)
    setLoading(true)
    setError(null)

    apiClient
      .listCandidates({ search, status, limit: PAGE_SIZE, offset })
      .then((response) => {
        if (cancelled) return
        setCandidates(response.items)
        setTotal(response.total)
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        setCandidates([])
        setTotal(0)
        if (cause instanceof ApiError && cause.status === 403) {
          setError(`"${recruiterId}" is not a recognized recruiter (403).`)
        } else if (cause instanceof Error) {
          setError(cause.message)
        } else {
          setError('Something went wrong loading candidates.')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [apiClient, recruiterId, search, status, offset])

  return (
    <main className="app">
      <h1>Candidates</h1>

      <div className="filters">
        <RecruiterSelect recruiters={RECRUITERS} selectedId={recruiterId} onChange={setRecruiterId} />
        <SearchInput onDebouncedChange={setSearch} />
        <StatusSelect value={status} onChange={setStatus} />
      </div>

      {error ? (
        <p className="status-message error">{error}</p>
      ) : (
        <>
          <CandidateTable candidates={candidates} loading={loading} />
          {!loading && <Pagination total={total} limit={PAGE_SIZE} offset={offset} onOffsetChange={setOffset} />}
        </>
      )}
    </main>
  )
}
