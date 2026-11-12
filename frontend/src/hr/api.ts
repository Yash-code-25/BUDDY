import { ApiError, request } from '../api'
import type { Question } from '../api'

export type Flag = {
  level: 'Red' | 'Amber' | 'Info'
  code: string
  text: string
  question: number | null
}

export type Candidate = {
  buddy_id: string
  name: string
  department: string
  location: string
  tier: number
  answers: number[]
  gaps: number[]
  close_count: number
  total_gap: number
  largest_gap: number
  band: 'Strong' | 'Good' | 'Weaker' | 'Not suggested'
  total_joiners: number
  active_joiners: number
  flags: Flag[]
}

type MatchRunData = {
  id: number
  run_time: string
  tier_reached: string
  shown: Candidate[]
  more: Candidate[]
  tiers: Record<string, Candidate[]>
  weaker: Candidate[]
  scored: Candidate[]
}

type JoinerInfo = {
  id: number
  candidate_id: string
  name: string
  personal_email: string
  department: string
  location: string
  brand: string
  function: string
  designation: string
  designation_track: string
  reporting_manager_id: string
  date_of_joining: string
  days_to_joining: number
  status: string
  status_label: string
  notes: JoinerNote[] // newest first
  attendance_confirmed_at: string | null // "Yes, I'll be there"
} & DayOne

/** A joiner's Day 1 details, for the pre-joining emails. A blank one leaves its line out. */
export type DayOne = {
  manager_name: string
  reporting_time: string
  contact_person: string
  directions: string
}

export type JoinerNote = { date: string; time: string; text: string }

export type QueueRow = JoinerInfo & {
  tier_reached: string
  best_band: string
  flags_count: number
}

type AnswerRow = { number: number; dimension: string; text: string; value: number; label: string }
type PairingInfo = {
  id: number
  buddy_pk: number
  buddy_id: string
  buddy_name: string
  status: 'ACTIVE' | 'CLOSED'
  source: string
  band: string
  override_reason: string
  assigned_at: string
  start_date: string
  end_date: string
  can_change: boolean // within 2 days of assigning
  review_opens_on: string
  reviewed: boolean
}

export type InductionItem = { id: number; week: number; day: string; activity: string; owner: string }
export type InductionProgress = {
  start_date: string
  current_week: number | null // null before day 1
  done: number
  total: number
  weeks: { week: number; items: (Omit<InductionItem, 'week'> & { done: boolean })[] }[]
}

export type JoinerDetail = {
  joiner: JoinerInfo
  questions: Question[]
  answers: AnswerRow[]
  run: MatchRunData | null
  pairing: PairingInfo | null
  induction: InductionProgress | null
  reasons: string[]
  settings: { candidates_per_tier: number; close_gap: number }
}

export type StaffUser = { username: string; name: string }

export type Tile = { key: string; label: string; count: number; link: string; urgent?: number; detail?: string }

export type BuddyRow = {
  id: number
  employee_id: string
  name: string
  email: string
  department: string
  location: string
  brand: string
  designation: string
  intro: string
  pool_status: string
  pool_status_label: string
  cmpbd_status: 'not_started' | 'in_progress' | 'completed'
  total_joiners: number
  active_joiners: number
  date_added: string
}

type GroupJoiner = { joiner_id: number; name: string; date_of_joining: string; end_date: string }
export type BuddyGroup = {
  department: string
  location: string
  buddies: (BuddyRow & { joiners: GroupJoiner[] })[]
  active_joiners: number
}

export type BuddyDetail = BuddyRow & {
  answers: { number: number; dimension: string; value: number; label: string }[]
  version: number | null
  submitted_at: string | null
  history: {
    joiner: string
    joiner_id: number
    status: 'ACTIVE' | 'CLOSED' | 'CANCELLED'
    band: string
    source: string
    assigned_at: string
    start_date: string
    end_date: string
  }[]
}

export type SettingsData = {
  close_gap: number
  strong_threshold: number
  good_threshold: number
  weaker_threshold: number
  amber_gap: number
  red_gap: number
  candidates_per_tier: number
  manual_cutoff_day: number
  old_answers_months: number
  joiner_intro: string
  buddy_intro: string
  departments: string[]
  locations: string[]
} & EmailSettings

/** What the pre-joining emails show. A blank one leaves its line out of the email. */
export type EmailSettings = {
  story_video_link: string
  handbook_link: string
  linkedin_link: string
  instagram_link: string
  dress_code: string
  contact_phone: string
  office_details: Record<string, Office> // by location
}

/** Where a location's joiners go on Day 1. */
export type Office = { address?: string; map_link?: string }

/** One audit entry in plain words: `sentence` has {who} and {target} to fill in, in bold. */
export type AuditRow = {
  id: number
  when: string
  user: string
  action: string
  sentence: string
  who: string
  who_link: string | null
  target: string | null
  target_link: string | null
  changes: AuditChange[]
}
/** One changed field. `before` is null for a new value, `after` is null for a removed one. */
export type AuditChange = { label: string; before: string | null; after: string | null }

export type ReportName = 'buddies' | 'reviews'
export type ReportTable = {
  name: ReportName
  title: string
  columns: string[]
  rows: (string | number)[][]
  buddy_column: number | null // this column names a buddy: clicking it opens the buddy panel
  buddy_ids: (number | null)[] // the buddy for each row
  attention: boolean[] // rows that need someone to act
}
export type ReportSummary = {
  total_buddies: number // in the pool, removed ones left out
  active_buddies: number
  total_joiners: number
  total_assigned: number // joiners given a buddy, now or in the past
  in_induction: number
  average_review: number | null
  reviews: number
}
export type ImportResult = { created: number; updated: number; errors: { row: number; error: string }[] }
export type FilterOptions = { department: string[]; location: string[]; brand: string[] }

// The session has run out (or the user signed out in another tab): go back to the sign-in page.
const SIGNED_OUT = 'Authentication credentials were not provided.'

async function call<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  try {
    return await request<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch (e) {
    if (e instanceof ApiError && e.status === 403 && e.message === SIGNED_OUT) {
      window.location.assign('/login')
    }
    throw e
  }
}

const withQuery = (path: string, query: string) => (query ? `${path}?${query.replace(/^\?/, '')}` : path)

// signed-in admin (signing in itself is signIn in ../api, shared with joiners and buddies)
export const logout = () => call('/hr/auth/logout/', 'POST')
export const me = () => call<StaffUser>('/hr/auth/me/')

// home
export const getHome = () => call<{ tiles: Tile[] }>('/hr/home/')
export const getFilterOptions = () => call<FilterOptions>('/hr/filters/')

// joiners
export const getQueue = (query = '') => call<QueueRow[]>(withQuery('/hr/joiners/', query))
export const createJoiner = (body: Record<string, string>) => call<{ id: number }>('/hr/joiners/', 'POST', body)
export const importJoiners = (csv: string) => call<ImportResult>('/hr/joiners/import/', 'POST', { csv })
export const getJoinerDetail = (id: number) => call<JoinerDetail>(`/hr/joiners/${id}/`)
export const saveDayOne = (id: number, details: DayOne) =>
  call<JoinerInfo>(`/hr/joiners/${id}/day-one/`, 'PUT', details)
export const joinerAction = (id: number, action: string, note = '') =>
  call<{ status: string }>(`/hr/joiners/${id}/action/`, 'POST', { action, note })
/** Assign a buddy, or change them within 2 days of assigning. */
export const assignBuddy = (
  id: number,
  body: { buddy_id: string; reason?: string; note?: string },
) => call<{ pairing_id: number; source: string }>(`/hr/joiners/${id}/assign/`, 'POST', body)

// buddy pool
export const getBuddies = (query = '') => call<BuddyRow[]>(withQuery('/hr/buddies/', query))
export const getBuddyGroups = (query = '') => call<BuddyGroup[]>(withQuery('/hr/buddies/groups/', query))
export const createBuddy = (body: Record<string, string>) => call<{ id: number }>('/hr/buddies/', 'POST', body)
export const importBuddies = (csv: string) => call<ImportResult>('/hr/buddies/import/', 'POST', { csv })
export const getBuddy = (id: number) => call<BuddyDetail>(`/hr/buddies/${id}/`)
export const patchBuddy = (id: number, body: Record<string, string>) =>
  call<{ ok: boolean }>(`/hr/buddies/${id}/`, 'PATCH', body)
export const buddyAction = (id: number, action: string) =>
  call<{ pool_status: string }>(`/hr/buddies/${id}/action/`, 'POST', { action })

// the 4-week induction programme
export const getInduction = () => call<InductionItem[]>('/hr/induction/')
export const addInductionItem = (body: Omit<InductionItem, 'id'>) => call<InductionItem>('/hr/induction/', 'POST', body)
export const saveInductionItem = (id: number, body: Omit<InductionItem, 'id'>) =>
  call<InductionItem>(`/hr/induction/${id}/`, 'PATCH', body)
export const removeInductionItem = (id: number) => call(`/hr/induction/${id}/`, 'DELETE')

// reports, settings, audit
export const getReportSummary = () => call<ReportSummary>('/hr/reports/summary/')
export const getReportTable = (name: ReportName) => call<ReportTable>(`/hr/reports/${name}/`)
export const reportDownloadUrl = (name: ReportName, kind: 'csv' | 'xlsx') => `/api/hr/reports/${name}/?export=${kind}`

/** A club: one interest at one location, and everyone there who picked it. */
export type ClubData = {
  interest: string
  location: string
  buddies: { id: number; name: string; department: string; designation: string }[]
  joiners: { id: number; name: string; department: string; date_of_joining: string; status: string }[]
}
export type ClubsData = { clubs: ClubData[]; interests: string[]; locations: string[] }
export const getClubs = (query: string) => call<ClubsData>(`/hr/clubs/${query ? `?${query}` : ''}`)
export const getSettings = () => call<SettingsData>('/hr/settings/')
export const saveSettings = (body: SettingsData) => call<SettingsData>('/hr/settings/', 'PUT', body)
export const getAudit = (query = '') => call<AuditRow[]>(withQuery('/hr/audit/', query))
