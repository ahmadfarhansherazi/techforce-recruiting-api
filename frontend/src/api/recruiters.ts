import type { Recruiter } from './types'

// The five recruiters from recruiters.csv. Hardcoded rather than read from
// Data/, which is gitignored source data and must not be a build dependency.
export const RECRUITERS: readonly Recruiter[] = [
  { id: 'R-101', name: 'Dana Whitmore', isAdmin: true },
  { id: 'R-102', name: 'Caleb Nguyen', isAdmin: false },
  { id: 'R-103', name: 'Marisol Vega', isAdmin: false },
  { id: 'R-104', name: 'Jordan Blake', isAdmin: false },
  { id: 'R-105', name: 'Tessa Iqbal', isAdmin: false },
]
