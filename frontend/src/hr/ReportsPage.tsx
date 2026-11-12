import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getReportSummary, getReportTable, reportDownloadUrl } from './api'
import type { ReportName, ReportSummary } from './api'
import { useLoad } from './helpers'
import { Empty, LoadState, PageTitle, Segmented, Table } from './ui'
import { useOpenBuddy } from './useOpenBuddy'
import { card, inputCls, secondary } from '../styles'

const TABS: { name: ReportName; label: string; attention?: string }[] = [
  { name: 'buddies', label: 'Buddies', attention: 'Only buddies with no profile yet' },
  { name: 'reviews', label: 'Buddy reviews' },
]

function NumberTile(props: { value: string | number; label: string; hint: string; alert?: boolean; onClick: () => void }) {
  const { value, label, hint, alert, onClick } = props
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg border bg-white p-4 text-left transition hover:border-brand ${alert ? 'border-amber-300' : 'border-slate-200'}`}
    >
      <div className={`text-3xl font-semibold ${alert ? 'text-amber-600' : 'text-ink'}`}>{value}</div>
      <div className="mt-1 text-sm font-medium text-slate-700">{label}</div>
      <div className="text-xs text-slate-400">{hint}</div>
    </button>
  )
}

export default function ReportsPage() {
  const [params, setParams] = useSearchParams()
  const tab = TABS.find((t) => t.name === params.get('tab')) ?? TABS[0]
  const [summary, setSummary] = useState<ReportSummary | null>(null)
  const [search, setSearch] = useState('')
  const [onlyAttention, setOnlyAttention] = useState(false)
  const openBuddy = useOpenBuddy()
  const navigate = useNavigate()

  useEffect(() => {
    getReportSummary().then(setSummary).catch(() => setSummary(null))
  }, [])

  const { data: table, error } = useLoad(useCallback(() => getReportTable(tab.name), [tab.name]), 'Could not load this report.')

  function show(name: ReportName) {
    setParams((prev) => {
      const p = new URLSearchParams(prev)
      p.set('tab', name)
      return p
    }, { replace: true })
    setSearch('')
    setOnlyAttention(false)
  }

  /** A cell's content: a buddy's name opens the buddy panel; an empty cell shows a dash. */
  function cellContent(i: number, j: number, cell: string | number) {
    const buddyId = table && j === table.buddy_column ? table.buddy_ids[i] : null
    if (buddyId) {
      return (
        <button type="button" className="font-medium text-brand hover:underline" onClick={() => openBuddy(buddyId)}>
          {cell}
        </button>
      )
    }
    return cell === '' ? '—' : cell
  }

  // Row numbers stay tied to the original rows, so the buddy ids still line up after filtering.
  const shown = useMemo(() => {
    if (!table || table.name !== tab.name) return []
    const needle = search.trim().toLowerCase()
    return table.rows
      .map((row, i) => ({ row, i }))
      .filter(({ row, i }) => (!onlyAttention || table.attention[i]) &&
        (!needle || row.some((cell) => String(cell).toLowerCase().includes(needle))))
  }, [table, tab.name, search, onlyAttention])

  return (
    <div>
      <PageTitle title="Reports" />

      {summary && (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <NumberTile value={summary.total_buddies} label="Total buddies" hint={`${summary.active_buddies} active in the pool`}
            onClick={() => navigate('/hr/buddies?view=list')} />
          <NumberTile value={summary.total_joiners} label="Total joiners" hint="Everyone added to COMPASS"
            onClick={() => navigate('/hr/joiners')} />
          <NumberTile value={summary.total_assigned} label="Total assigned" hint={`Given a buddy · ${summary.in_induction} in induction now`}
            onClick={() => navigate('/hr/joiners?status=PAIRED')} />
          <NumberTile value={summary.average_review ?? '–'} label="Average buddy review"
            hint={`Out of 5, from ${summary.reviews} ${summary.reviews === 1 ? 'review' : 'reviews'}`} onClick={() => show('reviews')} />
        </div>
      )}

      <div className="mb-4">
        <Segmented label="Report" value={tab.name} options={TABS.map((t) => ({ value: t.name, label: t.label }))}
          onChange={(name) => show(name)} />
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <input
          className={`${inputCls} max-w-xs`}
          placeholder="Search this table"
          aria-label="Search this table"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {tab.attention && (
          <label className="flex min-h-10 items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" className="h-4 w-4" checked={onlyAttention} onChange={(e) => setOnlyAttention(e.target.checked)} />
            {tab.attention}
          </label>
        )}
        <div className="ml-auto flex gap-2">
          <a className={secondary} href={reportDownloadUrl(tab.name, 'xlsx')}>Excel</a>
          <a className={secondary} href={reportDownloadUrl(tab.name, 'csv')}>CSV</a>
        </div>
      </div>

      <LoadState error={error} loading={!table || table.name !== tab.name} />

      {table && table.name === tab.name && (
        <>
          {shown.length === 0 && <Empty>{table.rows.length === 0 ? 'Nothing here yet.' : 'No rows match.'}</Empty>}

          {/* laptop: the full table */}
          {shown.length > 0 && (
            <Table className="hidden md:block" columns={table.columns}>
              {shown.map(({ row, i }) => (
                <tr key={i} className={`border-t border-slate-100 ${table.attention[i] ? 'bg-amber-50/70' : 'hover:bg-slate-50'}`}>
                  {row.map((cell, j) => (
                    <td
                      key={j}
                      className={`px-4 py-3 ${table.columns[j] === 'Comment' ? 'min-w-64' : 'whitespace-nowrap'} ${
                        j === 0 ? 'font-medium text-ink' : 'text-slate-600'
                      }`}
                    >
                      {cellContent(i, j, cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </Table>
          )}

          {/* phone: one card per row, the first column as its title */}
          <div className="space-y-3 md:hidden">
            {shown.map(({ row, i }) => (
              <div key={i} className={`${card} p-4 ${table.attention[i] ? 'border-l-4 border-l-amber-400' : ''}`}>
                <div className="font-semibold text-ink">{row[0]}</div>
                <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  {row.slice(1).map((cell, k) => (
                    <div key={k} className={table.columns[k + 1] === 'Comment' ? 'col-span-2' : ''}>
                      <dt className="text-xs text-slate-500">{table.columns[k + 1]}</dt>
                      <dd className="text-slate-700">{cellContent(i, k + 1, cell)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-400">
            Showing {shown.length} of {table.rows.length}.
            {tab.attention && ' Highlighted rows need someone to act.'}
            {table.buddy_column !== null && ' Click a buddy to see their joiners.'}
          </p>
        </>
      )}
    </div>
  )
}
