import { useCallback, useState } from 'react'
import { errorMessage } from './api'

/** A save or send: `busy` while it runs, and what went wrong if it fails. `run` returns whether it worked. */
export function useSubmit() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const run = useCallback(async (work: () => Promise<unknown>, failText?: string) => {
    setBusy(true)
    setError(null)
    try {
      await work()
      return true
    } catch (e) {
      setError(errorMessage(e, failText))
      return false
    } finally {
      setBusy(false)
    }
  }, [])
  return { busy, error, setError, run }
}
