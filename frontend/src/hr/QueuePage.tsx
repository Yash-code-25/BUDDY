import { useCallback, useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { createJoiner, getQueue, importJoiners } from './api'
import type { QueueRow } from './api'
import { BAND_TONE, STATUS_TONE, daysLabel, formatDate, optionList, useFilterOptions, useLoad } from './helpers'
import { PersonDialog } from './PersonDialog'
import type { FieldSpec } from './PersonDialog'
import { Badge, DataView, FilterBar, ImportDialog, LoadState, PageTitle } from './ui'
import { primary, secondary } from '../styles'

const STATUSES = [
  ['AWAITING_ASSESSMENT', 'Awaiting assessment'], ['AWAITING_PAIRING', 'Awaiting pairing'],
  ['PAIRED', 'Paired'], ['MANUAL', 'Manual'],
  ['ON_HOLD', 'On hold'], ['CLOSED', 'Closed'],
]

const MAIN: FieldSpec[] = [
  ['name', 'Name'], ['candidate_id', 'Candidate id'], ['personal_email', 'Personal email', 'email'],
  ['date_of_joining', 'Date of joining', 'date'], ['department', 'Department'], ['location', 'Location'],
]
const MORE: FieldSpec[] = [
  ['brand', 'Brand'], ['designation', 'Designation'], ['reporting_manager_id', 'Reporting manager id'],
  // Day 1, for the pre-joining emails. The office address and map come from Settings, by location.
  ['manager_name', 'Manager name'], ['reporting_time', 'Reporting time (e.g. 9:30 am)'],
  ['contact_person', 'Ask for (at reception)'], ['directions', 'Getting there'],
]

function Match({ row }: { row: QueueRow }) {
  if (!row.tier_reached) return <span className="text-slate-400">Not matched yet</span>
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      {row.best_band ? <Badge tone={BAND_TONE[row.best_band] ?? 'slate'}>{row.best_band}</Badge> : <Badge tone="red">Manual</Badge>}
      <span className="text-xs text-slate-500">
        {row.tier_reached === 'MANUAL' ? '' : `tier ${row.tier_reached.toLowerCase()}`}
        {row.flags_count > 0 ? ` · ${row.flags_count} flag${row.flags_count > 1 ? 's' : ''}` : ''}
      </span>
    </span>
  )
}

export default function QueuePage() {
  const [params, setParams] = useSearchParams()
  const [adding, setAdding] = useState(false)
  const [importing, setImporting] = useState(false)
  const options = useFilterOptions()
  const query = params.toString()

  const { data: rows, error, reload: load } = useLoad(useCallback(() => getQueue(query), [query]), 'Could not load the joiners.')

  return (
    <div>
      <PageTitle title="Joiners">
        <button className={secondary} onClick={() => setImporting(true)}>Import CSV</button>
        <button className={primary} onClick={() => setAdding(true)}>Add joiner</button>
      </PageTitle>

      <FilterBar
        params={params}
        onChange={(next) => setParams(next, { replace: true })}
        fields={[
          { key: 'q', label: 'Search by name', type: 'text' },
          { key: 'status', label: 'Status', type: 'select', options: STATUSES.map(([value, label]) => ({ value, label })) },
          { key: 'department', label: 'Department', type: 'select', options: optionList(options.department) },
          { key: 'location', label: 'Location', type: 'select', options: optionList(options.location) },
          { key: 'band', label: 'Match band', type: 'select', options: optionList(['Strong', 'Good', 'Weaker', 'Manual']) },
          { key: 'doj_from', label: 'Joining from', type: 'date' },
          { key: 'doj_to', label: 'Joining to', type: 'date' },
        ]}
      />

      <LoadState error={error} loading={!rows} />
      {rows && (
        <DataView
          rows={rows}
          rowKey={(r) => r.id}
          empty="No joiners match these filters."
          columns={[
            {
              header: 'Joiner',
              cell: (r) => (
                <div>
                  <Link className="font-medium text-ink hover:text-brand hover:underline" to={`/hr/joiners/${r.id}`}>{r.name}</Link>
                  <div className="text-xs text-slate-500">{r.department} · {r.location}</div>
                </div>
              ),
            },
            {
              header: 'Joining',
              cell: (r) => (
                <div>
                  <div className="whitespace-nowrap">{formatDate(r.date_of_joining)}</div>
                  <div className={`text-xs ${r.status === 'AWAITING_PAIRING' && r.days_to_joining <= 3 ? 'font-semibold text-red-600' : 'text-slate-500'}`}>
                    {daysLabel(r.days_to_joining)}
                  </div>
                </div>
              ),
            },
            { header: 'Match', cell: (r) => <Match row={r} /> },
            { header: 'Status', cell: (r) => <Badge tone={STATUS_TONE[r.status] ?? 'slate'}>{r.status_label}</Badge> },
            {
              header: '',
              cell: (r) => <Link className="inline-flex items-center gap-1 whitespace-nowrap text-sm font-semibold text-brand hover:text-brand-dark" to={`/hr/joiners/${r.id}`}>Open <ChevronRight size={16} aria-hidden /></Link>,
            },
          ]}
          card={(r) => (
            <div>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-semibold">{r.name}</div>
                  <div className="text-xs text-slate-500">{r.department} · {r.location}</div>
                </div>
                <Badge tone={STATUS_TONE[r.status] ?? 'slate'}>{r.status_label}</Badge>
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className={r.status === 'AWAITING_PAIRING' && r.days_to_joining <= 3 ? 'font-semibold text-red-600' : 'text-slate-600'}>
                  Joins {daysLabel(r.days_to_joining)}
                </span>
                <Match row={r} />
              </div>
              <Link className={`${secondary} mt-3 w-full`} to={`/hr/joiners/${r.id}`}>Review</Link>
            </div>
          )}
        />
      )}

      {adding && (
        <PersonDialog
          title="Add a joiner"
          submitLabel="Add joiner"
          main={MAIN}
          more={MORE}
          onSubmit={createJoiner}
          onClose={() => setAdding(false)}
          onDone={load}
        />
      )}
      {importing && (
        <ImportDialog
          title="Import joiners"
          template={'candidate_id,name,personal_email,department,location,brand,designation,reporting_manager_id,date_of_joining,manager_name,reporting_time,contact_person,directions\n'}
          onImport={importJoiners}
          onClose={() => setImporting(false)}
          onDone={load}
        />
      )}
    </div>
  )
}
