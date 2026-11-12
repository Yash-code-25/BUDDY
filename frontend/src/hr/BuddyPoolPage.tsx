import { useCallback, useEffect, useState } from 'react'
import { useOutletContext, useSearchParams } from 'react-router-dom'
import { buddyAction, createBuddy, getBuddies, getBuddyGroups, importBuddies } from './api'
import type { BuddyGroup, BuddyRow } from './api'
import { errorMessage } from '../api'
import { POOL_TONE, optionList, useActions, useFilterOptions, useLatest } from './helpers'
import { BuddyGroupsView } from './BuddyGroups'
import type { LayoutContext } from './HrLayout'
import { useOpenBuddy } from './useOpenBuddy'
import { PersonDialog } from './PersonDialog'
import type { FieldSpec } from './PersonDialog'
import { Badge, DataView, FilterBar, ImportDialog, Notice, PageTitle, Segmented } from './ui'
import { primary, rowAction, secondary } from '../styles'

const POOL_STATUS = [
  ['ACTIVE', 'Active'], ['PAUSED', 'Paused'], ['ON_LEAVE', 'On leave'], ['REMOVED', 'Removed'],
]
const CMPBD = [
  ['not_started', 'Not started'], ['in_progress', 'In progress'],
  ['not_started,in_progress', 'Not completed'], ['completed', 'Completed'],
]

const MAIN: FieldSpec[] = [
  ['name', 'Name'], ['employee_id', 'Employee id'], ['email', 'Email'], ['department', 'Department'], ['location', 'Location'],
]
const MORE: FieldSpec[] = [['brand', 'Brand'], ['designation', 'Designation']]

export default function BuddyPoolPage() {
  const [params, setParams] = useSearchParams()
  const [rows, setRows] = useState<BuddyRow[] | null>(null)
  const { error, setError, message, act: run } = useActions()
  const [adding, setAdding] = useState(false)
  const [importing, setImporting] = useState(false)
  const [groups, setGroups] = useState<BuddyGroup[] | null>(null)
  const options = useFilterOptions()
  const query = (() => {
    const p = new URLSearchParams(params)
    p.delete('buddy')
    return p.toString()
  })()
  const view = params.get('view') === 'list' ? 'list' : 'groups'
  const openBuddy = useOpenBuddy()
  const { buddyChanged } = useOutletContext<LayoutContext>()

  const latest = useLatest()
  const load = useCallback(() => {
    const current = latest()
    const failed = (e: unknown) => current() && setError(errorMessage(e, 'Could not load the buddy pool.'))
    const loaded = <T,>(set: (value: T) => void) => (value: T) => {
      if (current()) {
        set(value)
        setError(null)
      }
    }
    if (view === 'list') getBuddies(query).then(loaded(setRows)).catch(failed)
    else getBuddyGroups(query).then(loaded(setGroups)).catch(failed)
  }, [query, view, latest, setError])

  function setView(next: 'groups' | 'list') {
    const p = new URLSearchParams(params)
    if (next === 'list') p.set('view', 'list')
    else {
      p.delete('view')
      // Groups has no Pool status or Profile filter, so a choice made in List must not stay hidden in effect.
      p.delete('status')
      p.delete('cmpbd')
    }
    setParams(p)
  }

  useEffect(() => {
    load()
  }, [load, buddyChanged]) // buddyChanged: the buddy panel paused or resumed someone, so reload

  const act = (row: BuddyRow, action: string, done: string) =>
    run(async () => {
      await buddyAction(row.id, action)
      load()
    }, `${row.name}: ${done}`)

  // One quick action per buddy: pause an active one, resume a paused one, or chase an unfinished profile.
  function quick(r: BuddyRow) {
    if (r.pool_status === 'REMOVED') return null
    const [action, done, label] =
      r.pool_status === 'ACTIVE' ? ['pause', 'paused', 'Pause']
        : r.cmpbd_status === 'completed' ? ['resume', 'resumed', 'Resume']
          : ['remind', 'reminder sent', 'Remind']
    return <button className={rowAction} onClick={() => act(r, action, done)}>{label}</button>
  }

  const status = (r: BuddyRow) => (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <Badge tone={POOL_TONE[r.pool_status] ?? 'slate'}>{r.pool_status_label}</Badge>
      {r.cmpbd_status !== 'completed' && <Badge tone="amber">Profile pending</Badge>}
    </span>
  )
  const load_ = (r: BuddyRow) => `${r.active_joiners} active · ${r.total_joiners} total`

  return (
    <div>
      <PageTitle title="Buddies">
        <button className={secondary} onClick={() => setImporting(true)}>Upload CSV</button>
        <button className={primary} onClick={() => setAdding(true)}>Add buddy</button>
      </PageTitle>

      <div className="mb-4">
        <Segmented
          label="Buddies view"
          value={view}
          options={[{ value: 'groups', label: 'Groups' }, { value: 'list', label: 'List' }]}
          onChange={setView}
        />
      </div>

      <FilterBar
        params={params}
        onChange={(next) => setParams(next, { replace: true })}
        fields={[
          { key: 'q', label: 'Search by name', type: 'text' },
          // Pool status and Profile are List-only: the Groups view leaves them out.
          ...(view === 'list' ? [
            { key: 'status', label: 'Pool status', type: 'select' as const, options: POOL_STATUS.map(([value, label]) => ({ value, label })) },
            { key: 'cmpbd', label: 'Profile', type: 'select' as const, options: CMPBD.map(([value, label]) => ({ value, label })) },
          ] : []),
          { key: 'department', label: 'Department', type: 'select', options: optionList(options.department) },
          { key: 'location', label: 'Location', type: 'select', options: optionList(options.location) },
        ]}
      />

      {error && <Notice>{error}</Notice>}
      {message && <Notice kind="ok">{message}</Notice>}
      {!error && ((view === 'list' && !rows) || (view === 'groups' && !groups)) && (
        <p className="text-slate-500">Loading…</p>
      )}

      {view === 'groups' && groups && <BuddyGroupsView groups={groups} onOpen={openBuddy} />}

      {view === 'list' && rows && (
        <DataView
          rows={rows}
          rowKey={(r) => r.id}
          empty="No buddies match these filters."
          columns={[
            {
              header: 'Buddy',
              cell: (r) => (
                <div>
                  <button type="button" className="font-medium text-left text-brand hover:underline" onClick={() => openBuddy(r.id)}>{r.name}</button>
                  <div className="text-xs text-slate-500">{r.department} · {r.location}</div>
                </div>
              ),
            },
            { header: 'Status', cell: status },
            { header: 'Joiners', cell: (r) => <span className="whitespace-nowrap text-slate-600">{load_(r)}</span> },
            { header: '', cell: quick },
          ]}
          card={(r) => (
            <div>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <button type="button" className="font-semibold text-left text-brand hover:underline" onClick={() => openBuddy(r.id)}>{r.name}</button>
                  <div className="text-xs text-slate-500">{r.department} · {r.location}</div>
                </div>
                {status(r)}
              </div>
              <div className="mt-2 flex items-center justify-between text-sm text-slate-600">
                <span>{load_(r)}</span>
                {quick(r)}
              </div>
            </div>
          )}
        />
      )}

      {adding && (
        <PersonDialog
          title="Add a buddy"
          subtitle="They are emailed a link to complete their buddy profile."
          submitLabel="Add buddy"
          main={MAIN}
          more={MORE}
          intro="Short introduction (shown to the joiner)"
          onSubmit={createBuddy}
          onClose={() => setAdding(false)}
          onDone={load}
        />
      )}
      {importing && (
        <ImportDialog
          title="Upload buddies"
          template={'employee_id,name,email,department,location,brand,designation,total_joiners_buddied,intro\n'}
          onImport={importBuddies}
          onClose={() => setImporting(false)}
          onDone={load}
        />
      )}
    </div>
  )
}
