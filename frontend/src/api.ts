export type Kind = 'buddy' | 'joiner'

type Option = { value: number; label: string }
export type Question = { number: number; dimension: string; text: string; options: Option[] }
export type AssessmentStatus = 'not_started' | 'in_progress' | 'submitted'
export type Assessment = {
  first_name: string
  status: AssessmentStatus
  answers?: Record<string, number>
  questions?: Question[]
  intro?: string
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function errorMessage(e: unknown, fallback = 'Something went wrong.') {
  return e instanceof ApiError ? e.message : fallback
}

function csrfToken() {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const write = (init.method ?? 'GET') !== 'GET'
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(write ? { 'X-CSRFToken': csrfToken() } : {}), ...init.headers },
  })
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const message = Array.isArray(body) ? String(body[0]) : body?.detail ?? 'Something went wrong.'
    throw new ApiError(res.status, message)
  }
  return body as T
}

export const post = <T,>(path: string, body: unknown = {}) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) })

/** The one sign-in for everyone: Program admins (username and password), joiners and buddies (candidate or employee id and login code). */
export const signIn = (username: string, password: string) =>
  post<{ to: string }>('/auth/login/', { username, password })

/** Development only: every joiner and buddy, signed in with one click. The server answers 404 when off. */
export type DemoPerson = { kind: 'joiner' | 'buddy'; username: string; name: string; detail: string }
export const getDemoPeople = () => request<{ people: DemoPerson[] }>('/auth/demo/')
export const demoSignIn = (username: string, kind: DemoPerson['kind']) =>
  post<{ to: string }>('/auth/demo/', { username, kind })

export const getAssessment = (kind: Kind, token: string) =>
  request<Assessment>(`/assessment/${kind}/${token}/`)

export const saveAnswer = (kind: Kind, token: string, question: number, value: number) =>
  post<{ saved: boolean }>(`/assessment/${kind}/${token}/answer/`, { question, value })

export const submitAssessment = (kind: Kind, token: string) =>
  post<{ submitted: boolean }>(`/assessment/${kind}/${token}/submit/`)