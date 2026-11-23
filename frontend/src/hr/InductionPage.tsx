import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { errorMessage } from '../api'
import { addInductionItem, getInduction, getInductionJoiners, removeInductionItem } from './api'
import type { InductionItem, InductionJoiner } from './api'
import { filterInductionJoiners, formatDate, useLoad } from './helpers'
import { AddRow, EditRow, InductionFilters, PercentBar } from './InductionParts'
import { DataView, LoadState, PageTitle } from './ui'
import { rowAction, secondary } from '../styles'

/** The Day 1 rows every joiner gets. */
function CommonDayOne() {
  const [editing, setEditing] = useState<number | null>(null)
  const [open, setOpen] = useState(false) // folded by default, so the joiner list is in view
  const { data: items, error, setError, reload } = useLoad(getInduction, 'Could not load the Day 1 plan.')

  async function remove(item: InductionItem) {
    if (!window.confirm(`Remove "${item.activity}" from Day 1 for every joiner? Joiners who ticked it lose that tick.`)) return
    try {
      await removeInductionItem(item.id)
      reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  return (
    <section className="mb-8 overflow-hidden rounded-lg border border-slate-200 bg-white">
      <h2>
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
          className="flex w-full flex-wrap items-center justify-between gap-2 bg-slate-50 px-4 py-3 text-left font-semibold text-brand hover:bg-slate-100"
        >
          <span className="flex items-center gap-2">
            <ChevronDown size={18} aria-hidden className={`transition-transform ${open ? '' : '-rotate-90'}`} />
            Day 1 (common for all joiners)
          </span>
          <span className="text-sm font-normal text-slate-500">
            {items && `${items.length} ${items.length === 1 ? 'item' : 'items'} · `}{open ? 'Hide' : 'Show'}
          </span>
        </button>
      </h2>
      {open && (<>
      <p className="px-4 pt-3 text-sm text-slate-500">
        Every joiner gets these rows on Day 1. Their plan from Day 2 to the end of week 4 is written on their own page below.
      </p>
      <LoadState error={error} loading={!items} />
      {items && items.length > 0 && (
        <div className="mt-2 divide-y divide-slate-100">
          <div className="hidden px-4 py-2 text-xs font-medium text-slate-500 sm:grid sm:grid-cols-[8rem_1fr_10rem_9rem] sm:gap-3">
            <span>Day</span><span>Activity</span><span>With</span><span />
          </div>
          {items.map((item) =>
            editing === item.id ? (
              <EditRow key={item.id} item={item} canMove={false} onCancel={() => setEditing(null)}
                onSaved={() => { setEditing(null); reload() }} />
            ) : (
              <div key={item.id} className="grid gap-1 px-4 py-3 text-sm sm:grid-cols-[8rem_1fr_10rem_9rem] sm:items-center sm:gap-3">
                <span className="break-words text-slate-500">{item.day}</span>
                <span className="break-words font-medium text-slate-800">{item.activity}</span>
                <span className="break-words text-slate-600">{item.owner && <span className="sm:hidden">With </span>}{item.owner}</span>
                <span className="flex gap-3 sm:justify-end">
                  <button className={rowAction} onClick={() => setEditing(item.id)}>Edit</button>
                  <button className="min-h-10 font-medium text-red-700 hover:text-red-800 hover:underline" onClick={() => remove(item)}>Remove</button>
                </span>
              </div>
            ),
          )}
        </div>
      )}
      <AddRow week={1} dayHint="Day / topic" onAdd={async (d) => { await addInductionItem(d); reload() }} />
      </>)}
    </section>
  )
}

const planLink = (r: InductionJoiner) => `/hr/induction/${r.id}`

export default function InductionPage() {
  const [params, setParams] = useSearchParams()
  const { data: rows, error } = useLoad(getInductionJoiners, 'Could not load the joiners.')
  const shown = useMemo(() => (rows ? filterInductionJoiners(rows, params) : []), [rows, params])

  return (
    <div>
      <PageTitle title="Induction" description="Day 1 is the same for everyone; open a joiner to write their own 4-week plan." />
      <CommonDayOne />

      <h2 className="mb-3 text-lg font-semibold text-ink">Joiners</h2>
      <InductionFilters rows={rows ?? []} params={params} onChange={(next) => setParams(next, { replace: true })} />
      <LoadState error={error} loading={!rows} />
      {rows && (
        <>
          <DataView
            rows={shown}
            rowKey={(r) => r.id}
            empty={rows.length === 0 ? 'No joiners yet.' : 'No joiners match these filters.'}
            columns={[
              {
                header: 'Joiner',
                cell: (r) => (
                  <div>
                    <Link className="font-medium text-ink hover:text-brand hover:underline" to={planLink(r)}>{r.name}</Link>
                    <div className="text-xs text-slate-500">{r.candidate_id} · {r.department} · {r.location}</div>
                  </div>
                ),
              },
              { header: 'Joining', cell: (r) => <span className="whitespace-nowrap">{formatDate(r.date_of_joining)}</span> },
              { header: 'Buddy', cell: (r) => r.buddy ?? <span className="text-slate-400">Not yet</span> },
              {
                header: 'Own plan',
                cell: (r) => r.own_items
                  ? `${r.own_items} ${r.own_items === 1 ? 'row' : 'rows'}`
                  : <span className="whitespace-nowrap text-amber-700">None yet</span>,
              },
              { header: 'Done', cell: (r) => <PercentBar percent={r.percent} done={r.done} total={r.total} /> },
              {
                header: '',
                cell: (r) => (
                  <Link className="inline-flex items-center gap-1 whitespace-nowrap text-sm font-semibold text-brand hover:text-brand-dark" to={planLink(r)}>
                    Open plan <ChevronRight size={16} aria-hidden />
                  </Link>
                ),
              },
            ]}
            card={(r) => (
              <div>
                <div className="min-w-0">
                  <div className="break-words font-semibold">{r.name}</div>
                  <div className="break-words text-xs text-slate-500">{r.candidate_id} · {r.department} · {r.location}</div>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                  <div><div className="text-xs text-slate-500">Joining</div>{formatDate(r.date_of_joining)}</div>
                  <div className="min-w-0"><div className="text-xs text-slate-500">Buddy</div><div className="break-words">{r.buddy ?? 'Not yet'}</div></div>
                  <div><div className="text-xs text-slate-500">Own plan</div>
                    {r.own_items ? `${r.own_items} ${r.own_items === 1 ? 'row' : 'rows'}` : <span className="whitespace-nowrap text-amber-700">None yet</span>}
                  </div>
                  <PercentBar percent={r.percent} done={r.done} total={r.total} />
                </div>
                <Link className={`${secondary} mt-3 w-full`} to={planLink(r)}>Open plan</Link>
              </div>
            )}
          />
          <p className="mt-2 text-xs text-slate-400">Showing {shown.length} of {rows.length}.</p>
        </>
      )}
    </div>
  )
}
