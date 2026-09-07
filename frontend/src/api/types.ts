// Plain typed interfaces mirroring the backend's Pydantic response models.
// No logic here, that lives on ApiClient.

export type CandidateStatus = 'active' | 'screening' | 'interviewing' | 'withdrawn'

export type Region = 'US-MW' | 'US-NE' | 'US-SE' | 'US-W' | 'PH-MNL' | 'CO-BOG'

export const CANDIDATE_STATUSES: readonly CandidateStatus[] = [
  'active',
  'screening',
  'interviewing',
  'withdrawn',
]

// Mirrors app.api.candidates.CandidateOut
export interface Candidate {
  id: number
  name: string
  email: string
  region: Region
  role: string | null
  status: CandidateStatus
  applied_date: string | null
}

// Mirrors app.api.candidates.CandidateListResponse
export interface CandidateListResponse {
  items: Candidate[]
  total: number
  limit: number
  offset: number
}

export interface ListCandidatesParams {
  search?: string
  status?: CandidateStatus | ''
  limit: number
  offset: number
}

export interface Recruiter {
  id: string
  name: string
  isAdmin: boolean
}
