import { useCallback, useEffect, useRef, useState } from 'react'
import { errorMessage } from '../api'
import { getFilterOptions } from './api'
import type { BuddyDetail, FilterOptions } from './api'

export const optionList = (values: string[]) => values.map((v) => ({ value: v, label: v }))

export const STATUS_TONE: Record<string, 'slate' | 'green' | 'blue' | 'amber' | 'red'> = {
  AWAITING_ASSESSMENT: 'slate',
  AWAITING_PAIRING: 'amber',
  PAIRED: 'green',
  MANUAL: 'red',
  ON_HOLD: 'slate',
  CLOSED: 'slate',
}

export const POOL_TONE: Record<string, 'green' | 'amber' | 'red'> = {
  ACTIVE: 'green',
  PAUSED: 'amber',
  ON_LEAVE: 'amber',
  REMOVED: 'red',
}

export const BAND_TONE: Record<string, 'green' | 'blue' | 'amber' | 'slate'> = {
  Strong: 'green',
  Good: 'blue',
  Weaker: 'amber',
  'Not suggested': 'slate',
}

type Pairing = BuddyDetail['history'][number]

export const PAIRING_OUTCOME: Record<Pairing['status'], string> = {
  ACTIVE: 'In induction',
  CLOSED: 'Finished',
  CANCELLED: 'Changed to another buddy',
}

/** "30 Nov 2026" from "2026-11-30" (or a full timestamp). */
export const formatDate = (iso: string) =>
  new Date(`${iso.slice(0, 10)}T00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

export const pairingDates = (p: Pairing) => `${formatDate(p.start_date)} to ${formatDate(p.end_date)}`

export function daysLabel(days: number) {
  if (days === 0) return 'today'
  if (days === 1) return 'tomorrow'
  if (days > 0) return `in ${days} days`
  return `${-days} days ago`
}

export function useFilterOptions() {
  const [options, setOptions] = useState<FilterOptions>({ department: [], location: [], brand: [] })
  useEffect(() => {
    getFilterOptions().then(setOptions).catch(() => undefined)
  }, [])
  return options
}

/** Runs an action on a page and says how it went: `message` once it worked, `error` if not. */
export function useActions() {
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const act = useCallback(async (work: () => Promise<unknown>, done: string) => {
    setError(null)
    setMessage(null)
    try {
      await work()
      setMessage(done)
    } catch (e) {
      setError(errorMessage(e))
    }
  }, [])
  return { error, setError, message, act }
}

/** Loads a page's data and reloads it whenever `fetch` changes (wrap it in useCallback). A failed load
 * keeps what was shown before and says why; a slow, older reply never overwrites a newer one. */
export function useLoad<T>(fetch: () => Promise<T>, failText: string) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const latest = useLatest()
  const reload = useCallback(() => {
    const current = latest()
    fetch()
      .then((value) => {
        if (current()) {
          setData(value)
          setError(null)
        }
      })
      .catch((e) => current() && setError(errorMessage(e, failText)))
  }, [fetch, failText, latest])
  useEffect(reload, [reload])
  return { data, error, setError, reload }
}

/** Call at the start of each load; the returned check is false once a newer load has started,
 * so a slow, older reply cannot overwrite a newer one. */
export function useLatest() {
  const seq = useRef(0)
  return useCallback(() => {
    const n = ++seq.current
    return () => n === seq.current
  }, [])
}
