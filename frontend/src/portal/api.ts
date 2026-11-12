import { post, request } from '../api'
import type { AssessmentStatus } from '../api'
import type { InductionProgress } from '../hr/api'

type Person = { name: string; role: string; department: string; location: string; date_of_joining: string }

export type Induction = InductionProgress

type Common = { name: string; first_name: string; username: string }

export type JoinerMe = Common & {
  kind: 'joiner'
  date_of_joining: string
  stage: string
  quiz: { status: AssessmentStatus; open: boolean; link: string; due: string | null }
  buddy: {
    name: string
    role: string
    department: string
    location: string
    intro: string
    start_date: string
    end_date: string
  } | null
  induction: Induction | null // once a buddy is assigned
  review: {
    opens_on: string
    open: boolean // after the 4 weeks
    submitted: boolean
    title: string
    questions: string[]
    scale: string[]
  } | null
  interests: Interests // what they enjoy outside work
  clubs: Club[] // their interests at their location, with the buddies there
  day_one: DayOne
}

export type Interests = { choices: string[]; selected: string[]; other: string }
export type Club = { interest: string; location: string; buddies: { name: string; department: string }[] }

/** "Yes, I'll be there", shown from 3 days before joining. Blank details are left out. */
export type DayOne = {
  show: boolean
  confirmed: boolean
  reporting_time: string
  office_address: string
  map_link: string
  contact_person: string
}

export type BuddyMe = Common & {
  kind: 'buddy'
  pool_status_label: string
  profile: { status: AssessmentStatus; link: string }
  joiners: (Person & { end_date: string; induction: Induction })[]
  total_joiners: number
  interests: Interests
  clubs: BuddyClub[] // their interests at their location, with the new joiners who share them
}

export type BuddyClub = {
  interest: string
  location: string
  joiners: { name: string; department: string; date_of_joining: string }[]
}

export type Me = JoinerMe | BuddyMe

export const getMe = () => request<Me>('/portal/me/')
export const signOut = () => post<{ ok: boolean }>('/portal/logout/')
export const tickInduction = (itemId: number, done: boolean) => post<Induction>(`/portal/induction/${itemId}/`, { done })
export const sendReview = (scores: number[], comment: string) => post<{ ok: boolean }>('/portal/review/', { scores, comment })
/** Saves what they enjoy outside work. A joiner also gets their clubs back. */
export const saveInterests = (selected: string[], other: string) =>
  post<{ interests: Interests; clubs?: Club[] }>('/portal/interests/', { selected, other })
export const confirmAttendance = () => post<DayOne>('/portal/attendance/')
/** A buddy reopens their finished profile to update it; returns where to answer. */
export const retakeProfile = () => post<{ link: string }>('/portal/retake/')
