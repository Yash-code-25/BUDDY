import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { X } from 'lucide-react'
import { getInductionJoiners, getInductionPlan } from './api'
import type { InductionJoiner } from './api'
import { filterInductionJoiners, formatDate, useLoad } from './helpers'
import { InductionFilters, PercentBar, PlanView } from './InductionParts'
import { DataView, LoadState, Modal } from './ui'
import { rowAction, secondary } from '../styles'

const initials = (name: string) =>
  name.split(/[\s_]+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('')

/** One fact in the dialog's summary strip. */
function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 break-words text-sm font-medium text-ink">{children}</dd>
    </div>
  )
}

/** One joiner's whole plan and what they ticked, read only. */
function PlanDialog({ joiner, onClose }: { joiner: InductionJoiner; onClose: () => void }) {
  const { data, error } = useLoad(useCallback(() => getInductionPlan(joiner.id), [joiner.id]), 'Could not load this plan.')
  const induction = data?.induction
  let stage = '–'
  if (induction) {
    if (induction.total > 0 && induction.done === induction.total) stage = 'Completed'
    else if (induction.current_week) stage = `Week ${induction.current_week} of 4`
    else stage = 'Not started yet'
  }
  return (
    <Modal wide onClose={onClose}>
      <div className="flex items-start gap-4">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand text-base font-semibold text-white">
          {initials(joiner.name)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Induction plan</p>
          <h2 className="break-words text-xl font-semibold text-ink">{joiner.name}</h2>
          <p className="break-words text-sm text-slate-500">{joiner.candidate_id} · {joiner.department} · {joiner.location}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close"
          className="-mr-2 -mt-2 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600">
          <X size={20} aria-hidden />
        </button>
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-4 rounded-xl border border-slate-200 p-4 sm:grid-cols-3">
        <Fact label="Joining date">{formatDate(joiner.date_of_joining)}</Fact>
        <Fact label="Buddy">{joiner.buddy ?? <span className="text-slate-400">Not assigned</span>}</Fact>
        <Fact label="Stage">{stage}</Fact>
      </dl>

      <LoadState error={error} loading={!data} />
      {induction && (
        <>
          <div className="mt-4 rounded-xl bg-slate-50 p-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <div className="text-3xl font-bold text-ink">{induction.percent}%</div>
                <div className="text-sm text-slate-500">of the induction completed</div>
              </div>
              <div className="text-sm text-slate-600">
                <span className="font-semibold text-ink">{induction.done}</span> of {induction.total} activities done
              </div>
            </div>
            <div className="mt-3 h-2.5 rounded-full bg-slate-200" role="img" aria-label={`${induction.percent}% of the induction done`}>
              <div className="h-2.5 rounded-full bg-success transition-all" style={{ width: `${induction.percent}%` }} />
            </div>
          </div>
          <div className="mt-5">
            <PlanView induction={induction} />
          </div>
        </>
      )}
      <div className="mt-5 flex justify-end border-t border-slate-100 pt-4">
        <button className={secondary} onClick={onClose}>Close</button>
      </div>
    </Modal>
  )
}

/** Reports, Induction progress: every joiner with how much of their induction they have ticked. */
export default function JoinerReviewReport({ params, onChange }: {
  params: URLSearchParams
  onChange: (next: URLSearchParams) => void
}) {
  const [open, setOpen] = useState<InductionJoiner | null>(null)
  const { data: rows, error } = useLoad(getInductionJoiners, 'Could not load the joiners.')
  const shown = useMemo(() => (rows ? filterInductionJoiners(rows, params) : []), [rows, params])

  return (
    <div>
      <InductionFilters rows={rows ?? []} params={params} onChange={onChange} />
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
                    <div className="font-medium text-ink">{r.name}</div>
                    <div className="text-xs text-slate-500">{r.candidate_id} · {r.department} · {r.location}</div>
                  </div>
                ),
              },
              { header: 'Joining', cell: (r) => <span className="whitespace-nowrap">{formatDate(r.date_of_joining)}</span> },
              { header: 'Buddy', cell: (r) => r.buddy ?? <span className="text-slate-400">Not yet</span> },
              { header: 'Induction done', cell: (r) => <PercentBar percent={r.percent} done={r.done} total={r.total} /> },
              { header: '', cell: (r) => <button className={rowAction} onClick={() => setOpen(r)}>View</button> },
            ]}
            card={(r) => (
              <div>
                <div className="break-words font-semibold">{r.name}</div>
                <div className="break-words text-xs text-slate-500">{r.candidate_id} · {r.department} · {r.location}</div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                  <div><div className="text-xs text-slate-500">Joining</div>{formatDate(r.date_of_joining)}</div>
                  <div className="min-w-0"><div className="text-xs text-slate-500">Buddy</div><div className="break-words">{r.buddy ?? 'Not yet'}</div></div>
                </div>
                <div className="mt-3"><PercentBar percent={r.percent} done={r.done} total={r.total} /></div>
                <button className={`${secondary} mt-3 w-full`} onClick={() => setOpen(r)}>View plan</button>
              </div>
            )}
          />
          <p className="mt-2 text-xs text-slate-400">Showing {shown.length} of {rows.length}.</p>
        </>
      )}
      {open && <PlanDialog joiner={open} onClose={() => setOpen(null)} />}
    </div>
  )
}
