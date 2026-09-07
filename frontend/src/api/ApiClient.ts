import { ApiError } from './ApiError'
import type { Candidate, CandidateListResponse, ListCandidatesParams } from './types'

const RECRUITER_HEADER = 'X-Recruiter-Id'

// Owns the base URL, the recruiter header, and every HTTP call the app
// makes. Components never call fetch() themselves.
export class ApiClient {
  private readonly baseUrl: string
  private recruiterId: string

  constructor(baseUrl: string, recruiterId: string) {
    this.baseUrl = baseUrl
    this.recruiterId = recruiterId
  }

  setRecruiterId(recruiterId: string): void {
    this.recruiterId = recruiterId
  }

  async listCandidates(params: ListCandidatesParams): Promise<CandidateListResponse> {
    const url = new URL(`${this.baseUrl}/api/v1/candidates`, window.location.origin)
    if (params.search) url.searchParams.set('search', params.search)
    if (params.status) url.searchParams.set('status', params.status)
    url.searchParams.set('limit', String(params.limit))
    url.searchParams.set('offset', String(params.offset))

    return this.request<CandidateListResponse>(url)
  }

  async getCandidate(id: number): Promise<Candidate> {
    const url = new URL(`${this.baseUrl}/api/v1/candidates/${id}`, window.location.origin)
    return this.request<Candidate>(url)
  }

  private async request<T>(url: URL): Promise<T> {
    const response = await fetch(url.toString(), {
      headers: { [RECRUITER_HEADER]: this.recruiterId },
    })

    if (!response.ok) {
      throw new ApiError(response.status, await this.describeError(response))
    }
    return (await response.json()) as T
  }

  private async describeError(response: Response): Promise<string> {
    try {
      const body: unknown = await response.json()
      if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
        return body.detail
      }
    } catch {
      // body was not JSON, fall through to the status text below
    }
    return response.statusText || `request failed with status ${response.status}`
  }
}
