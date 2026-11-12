import { useCallback } from 'react'
import type { ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getAudit } from './api'
import type { AuditChange, AuditRow } from './api'
import { useLoad } from './helpers'
import { FilterBar, LoadState, PageTitle } from './ui'
import { card } from '../styles'

// In the viewer's own time zone (the server sends UTC), e.g. "6 Nov 2026, 16:15".
const when = (r: AuditRow) =>
  new Date(r.when).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })

function Name({ text, link }: { text: string; link: string | null }) {
  return link
    ? <Link to={link} className="font-semibold text-ink hover:text-brand hover:underline">{text}</Link>
    : <strong className="font-semibold text-ink">{text}</strong>
}

/** "superuser resumed buddy Anita Desai": the sentence with the person and the record in bold. */
function Sentence({ row }: { row: AuditRow }) {
  const parts: ReactNode[] = []
  row.sentence.split(/(\{who\}|\{target\})/).forEach((piece, i) => {
    if (piece === '{who}') parts.push(<Name key={i} text={row.who} link={row.who_link} />)
    else if (piece === '{target}') parts.push(<Name key={i} text={row.target ?? ''} link={row.target_link} />)
    else if (piece) parts.push(piece)
  })
  return <p className="text-sm text-slate-700">{parts}</p>
}

/** "Pool status: Paused → Active", one per changed field. */
function Change({ c }: { c: AuditChange }) {
  return (
    <li className="inline-flex flex-wrap items-baseline gap-1 rounded-md bg-slate-50 px-2 py-1 text-xs ring-1 ring-inset ring-slate-200">
      <span className="text-slate-500">{c.label}:</span>
      {c.before !== null && <span className={c.after !== null ? 'text-slate-400 line-through' : 'text-slate-600'}>{c.before}</span>}
      {c.before !== null && c.after !== null && <span className="text-slate-400" aria-label="changed to">→</span>}
      {c.after !== null && <span className="font-medium text-ink">{c.after}</span>}
    </li>
  )
}

export default function AuditPage() {
  const [params, setParams] = useSearchParams()
  const query = params.toString()
  const { data: rows, error } = useLoad(useCallback(() => getAudit(query), [query]), 'Could not load the audit log.')

  return (
    <div>
      <PageTitle title="Audit log" description="Every change made in COMPASS, newest first." />
      <FilterBar
        params={params}
        onChange={(next) => setParams(next, { replace: true })}
        fields={[
          { key: 'user', label: 'Search by user', type: 'text' },
          { key: 'action', label: 'Action contains', type: 'text' },
          { key: 'date_from', label: 'From', type: 'date' },
          { key: 'date_to', label: 'To', type: 'date' },
        ]}
      />
      <LoadState error={error} loading={!rows} />
      {rows && rows.length === 0 && (
        <p className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          Nothing logged for these filters.
        </p>
      )}
      {rows && rows.length > 0 && (
        <ul className={`${card} divide-y divide-slate-100`}>
          {rows.map((r) => (
            <li key={r.id} className="flex flex-col gap-1.5 px-4 py-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
              <div className="min-w-0">
                <Sentence row={r} />
                {r.changes.length > 0 && (
                  <ul className="mt-1.5 flex flex-wrap gap-1.5">
                    {r.changes.map((c, i) => <Change key={i} c={c} />)}
                  </ul>
                )}
              </div>
              <time className="shrink-0 whitespace-nowrap text-xs text-slate-400 sm:pt-0.5" dateTime={r.when}>{when(r)}</time>
            </li>
          ))}
        </ul>
      )}
      {rows && rows.length === 500 && <p className="mt-2 text-xs text-slate-400">Showing the latest 500. Narrow the filters to see more.</p>}
    </div>
  )
}
