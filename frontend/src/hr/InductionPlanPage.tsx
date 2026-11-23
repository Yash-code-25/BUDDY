import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import { errorMessage } from '../api'
import { addJoinerInductionItem, getInductionPlan, removeInductionItem, restoreCommonDayOne } from './api'
import type { InductionProgress } from './api'
import { formatDate, useLoad } from './helpers'
import { AddRow, DoneMark, EditRow, PercentBar } from './InductionParts'
import { LoadState, PageTitle } from './ui'
import { linkButton, panel, rowAction } from '../styles'

type PlanItem = InductionProgress['weeks'][number]['items'][number]

/** One joiner's 4-week induction plan: the common Day 1, then their own rows, which are edited here. */
export default function InductionPlanPage() {
  const id = Number(useParams().id)
  const [editing, setEditing] = useState<number | null>(null)
  const { data, error, setError, reload } = useLoad(useCallback(() => getInductionPlan(id), [id]), 'Could not load this plan.')

  async function remove(item: PlanItem) {
    if (!window.confirm(`Remove "${item.activity}" from this joiner's plan?`)) return
    try {
      await removeInductionItem(item.id, id) // a common Day 1 row goes for this joiner only
      reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function restore() {
    if (!window.confirm('Drop the Day 1 changes made for this joiner and give them the common Day 1 again?')) return
    try {
      await restoreCommonDayOne(id)
      reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  const joiner = data?.joiner
  const induction = data?.induction

  return (
    <div>
      <Link to="/hr/induction" className={`${linkButton} mb-2 inline-flex items-center gap-1`}>
        <ChevronLeft size={16} aria-hidden /> All joiners
      </Link>
      <PageTitle title={joiner ? `${joiner.name}'s induction` : 'Induction plan'} />
      <LoadState error={error} loading={!data} />

      {joiner && induction && (
        <>
          <div className={`${panel} mb-4 grid gap-4 sm:grid-cols-[1fr_14rem] sm:items-center`}>
            <dl className="grid min-w-0 grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3 lg:grid-cols-5">
              {[
                ['Candidate ID', joiner.candidate_id],
                ['Department', joiner.department],
                ['Location', joiner.location],
                ['Date of joining', formatDate(joiner.date_of_joining)],
                ['Buddy', joiner.buddy ?? 'Not assigned yet'],
              ].map(([label, value]) => (
                <div key={label} className="min-w-0">
                  <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
                  <dd className={`mt-0.5 break-words font-medium ${label === 'Buddy' && !joiner.buddy ? 'text-slate-400' : 'text-ink'}`}>{value}</dd>
                </div>
              ))}
            </dl>
            <PercentBar percent={induction.percent} done={induction.done} total={induction.total} />
          </div>

          <div className="space-y-4">
            {induction.weeks.map(({ week, items: rows }) => {
              return (
                <section key={week} className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                  <h2 className="flex items-center justify-between bg-slate-50 px-4 py-3 font-semibold text-brand">
                    Week {week}
                    <span className="text-sm font-normal text-slate-500">{rows.length} {rows.length === 1 ? 'item' : 'items'}</span>
                  </h2>
                  {week === 1 && (
                    <p className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-2 text-xs text-slate-500">
                      {induction.own_day_one ? (
                        <>
                          <span>Day 1 has been changed for this joiner only.</span>
                          <button className="font-medium text-brand hover:underline" onClick={restore}>Use the common Day 1 again</button>
                        </>
                      ) : (
                        <span>Changing a Day 1 row here changes it for this joiner only; everyone else keeps the common Day 1.</span>
                      )}
                    </p>
                  )}
                  {rows.length > 0 && (
                    <div className="divide-y divide-slate-100">
                      <div className="hidden px-4 py-2 text-xs font-medium text-slate-500 sm:grid sm:grid-cols-[8rem_1fr_10rem_4.5rem_8rem] sm:gap-3">
                        <span>Day</span><span>Activity</span><span>With</span><span>Ticked</span><span />
                      </div>
                      {rows.map((item) =>
                        editing === item.id ? (
                          <EditRow key={item.id} item={{ ...item, week }} canMove={!item.day_one} joinerId={id} onCancel={() => setEditing(null)}
                            onSaved={() => { setEditing(null); reload() }} />
                        ) : (
                          <div key={item.id}
                            className={`grid gap-1 px-4 py-3 text-sm sm:grid-cols-[8rem_1fr_10rem_4.5rem_8rem] sm:items-center sm:gap-3 ${item.day_one ? 'bg-slate-50/60' : ''}`}>
                            <span className="break-words text-slate-500">{item.day}</span>
                            <span className="break-words font-medium text-slate-800">{item.activity}</span>
                            <span className="break-words text-slate-600">{item.owner && <span className="sm:hidden">With </span>}{item.owner}</span>
                            <DoneMark done={item.done} />
                            <span className="flex gap-3 sm:justify-end">
                              <button className={rowAction} onClick={() => setEditing(item.id)}>Edit</button>
                              <button className="min-h-10 font-medium text-red-700 hover:text-red-800 hover:underline" onClick={() => remove(item)}>Remove</button>
                            </span>
                          </div>
                        ),
                      )}
                    </div>
                  )}
                  <AddRow week={week} dayHint={week === 1 ? 'Day (e.g. Day 1 or Day 2)' : `Day (e.g. Day ${week * 5 - 3})`}
                    onAdd={async (d) => { await addJoinerInductionItem(id, d); reload() }} />
                </section>
              )
            })}
          </div>
          <p className="mt-3 text-xs text-slate-400">
            To change Day 1 for every joiner, use the <Link className="text-brand hover:underline" to="/hr/induction">Induction</Link> page.
            {induction.own_day_one && ' This joiner has their own Day 1, so those changes will not reach them.'}
          </p>
        </>
      )}
    </div>
  )
}
