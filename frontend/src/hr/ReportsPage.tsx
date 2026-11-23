import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Eye } from 'lucide-react'
import { getReportSummary, getReportTable, reportDownloadUrl } from './api'
import type { ReportName, ReportSummary, ReportTable, ReviewDetail } from './api'
import { formatDate, useLoad } from './helpers'
import JoinerReviewReport from './JoinerReviewReport'
import { Empty, LoadState, Modal, PageTitle, Segmented, Table } from './ui'
import { useOpenBuddy } from './useOpenBuddy'
import { card, inputCls, secondary } from '../styles'

// 'joiners' is Induction progress: each joiner's induction progress, built on its own page part.
type TabName = ReportName | 'joiners'
const TABS: { name: TabName; label: string; attention?: string }[] = [
  { name: 'buddies', label: 'Buddies', attention: 'Only buddies with no profile yet' },
  { name: 'reviews', label: 'Buddy reviews' },
  { name: 'joiners', label: 'Buddy progress' },
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

/** One joiner's review of their buddy: each question with the answer they chose, out of 5. */
function ReviewDialog({ joiner, buddy, date, detail, onClose }: {
  joiner: string; buddy: string; date: string; detail: ReviewDetail; onClose: () => void
}) {
  return (
    <Modal onClose={onClose}>
      <h3 className="text-lg font-semibold text-ink">{joiner}'s review of {buddy}</h3>
      <p className="mt-0.5 text-sm text-slate-500">Sent {formatDate(date)} · total {detail.total} / {detail.max}</p>
      <ul className="mt-4 space-y-3">
        {detail.questions.map((q) => (
          <li key={q.question} className="rounded-lg border border-slate-200 p-3">
            <div className="text-sm font-medium text-slate-800">{q.question}</div>
            <div className="mt-2 flex items-center gap-3">
              <div className="flex gap-1" aria-hidden>
                {[1, 2, 3, 4, 5].map((n) => (
                  <span key={n} className={`h-2 w-7 rounded-full ${n <= q.score ? 'bg-success' : 'bg-slate-200'}`} />
                ))}
              </div>
              <span className="text-sm font-semibold text-ink">{q.score} · {q.label}</span>
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-4">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Comment</div>
        <p className="mt-1 whitespace-pre-line text-sm text-slate-700">{detail.comment || 'No comment.'}</p>
      </div>
      <div className="mt-5 flex justify-end">
        <button className={secondary} onClick={onClose}>Close</button>
      </div>
    </Modal>
  )
}

export default function ReportsPage() {
  const [params, setParams] = useSearchParams()
  const tab = TABS.find((t) => t.name === params.get('tab')) ?? TABS[0]
  const [summary, setSummary] = useState<ReportSummary | null>(null)
  const [search, setSearch] = useState('')
  const [onlyAttention, setOnlyAttention] = useState(false)
  const [review, setReview] = useState<number | null>(null) // the review row whose answers are open
  const openBuddy = useOpenBuddy()
  const navigate = useNavigate()

  useEffect(() => {
    getReportSummary().then(setSummary).catch(() => setSummary(null))
  }, [])

  const { data: table, error } = useLoad(
    useCallback((): Promise<ReportTable | null> => (tab.name === 'joiners' ? Promise.resolve(null) : getReportTable(tab.name)), [tab.name]),
    'Could not load this report.',
  )

  function show(name: TabName) {
    // a new tab starts with no filters
    setParams(new URLSearchParams({ tab: name }), { replace: true })
    setSearch('')
    setOnlyAttention(false)
    setReview(null)
  }

  /** A cell's content: a buddy's name opens the buddy panel; an empty cell shows a dash. */
  function cellContent(i: number, j: number, cell: string | number) {
    if (table?.details && table.columns[j] === 'Details') {
      // a review: opens the joiner's answers in full
      return (
        <button type="button" className="inline-flex items-center gap-1.5 font-medium text-brand hover:underline" onClick={() => setReview(i)}>
          <Eye size={16} aria-hidden /> View details
        </button>
      )
    }
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
          <NumberTile value={summary.reviews} label="Total reviews" hint="Buddy reviews sent by joiners"
            onClick={() => show('reviews')} />
        </div>
      )}

      <div className="mb-4">
        <Segmented label="Report" value={tab.name} options={TABS.map((t) => ({ value: t.name, label: t.label }))}
          onChange={(name) => show(name)} />
      </div>

      {tab.name === 'joiners' ? (
        <JoinerReviewReport params={params} onChange={(next) => setParams(next, { replace: true })} />
      ) : (
      <>
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
          <a className={secondary} href={reportDownloadUrl(tab.name as ReportName, 'xlsx')}>Excel</a>
          <a className={secondary} href={reportDownloadUrl(tab.name as ReportName, 'csv')}>CSV</a>
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
                <div className="font-semibold text-ink">{cellContent(i, 0, row[0])}</div>
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
            {table.details && ' Q1 to Q3 are the review questions, each scored out of 5 (set in Settings); Total adds them up. View details shows the questions in full.'}
            {table.buddy_column !== null && ' Click a buddy to see their joiners.'}
          </p>
          {review !== null && table.details?.[review] && (
            <ReviewDialog joiner={String(table.rows[review][0])} buddy={String(table.rows[review][1])}
              date={String(table.rows[review][2])} detail={table.details[review]} onClose={() => setReview(null)} />
          )}
        </>
      )}
      </>
      )}
    </div>
  )
}
