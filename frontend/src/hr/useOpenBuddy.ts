import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

/** Open the buddy panel from any admin page: it adds ?buddy=<id> to the address, and the layout shows
 * the panel. Back (or Esc) closes it again. */
export function useOpenBuddy() {
  const [, setParams] = useSearchParams()
  return useCallback((id: number) => {
    setParams((prev) => {
      const p = new URLSearchParams(prev)
      p.set('buddy', String(id))
      return p
    })
  }, [setParams])
}
