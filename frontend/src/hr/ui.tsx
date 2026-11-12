import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { AlertCircle, CheckCircle2, Search, SlidersHorizontal, Upload } from 'lucide-react'
import type { ImportResult } from './api'
import { useSubmit } from '../useSubmit'
import { card, inputCls, linkButton, secondary } from '../styles'

/** A dialog on desktop, and a sheet that slides up from the bottom on a phone. */
export function Modal({ children, onClose, wide }: { children: ReactNode; onClose: () => void; wide?: boolean }) {
  // Esc closes it, like clicking outside.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-ink/40 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        className={`max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl sm:rounded-lg sm:p-6 ${
          wide ? 'sm:max-w-2xl' : 'sm:max-w-lg'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  )
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 block font-medium text-slate-700">{label}</span>
      {children}
    </label>
  )
}

/** A drop-down of the fixed values (departments, locations from Settings), so nobody types a
 * spelling the match would not recognise. */
export function ChoiceSelect({ value, choices, onChange }: { value: string; choices: string[]; onChange: (v: string) => void }) {
  const all = value && !choices.includes(value) ? [value, ...choices] : choices
  return (
    <select className={inputCls} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Choose…</option>
      {all.map((c) => <option key={c} value={c}>{c}</option>)}
    </select>
  )
}

/** A buddy's or joiner's five answers as small tiles; the caller lays them out in a grid. */
export function AnswerTiles({ answers }: { answers: { number: number; dimension: string; label: string }[] }) {
  return answers.map((a) => (
    <div key={a.number} className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{a.dimension}</div>
      <div className="mt-0.5 font-medium leading-snug text-ink">{a.label}</div>
    </div>
  ))
}

/** The error, or "Loading…" while there is nothing to show yet. */
export function LoadState({ error, loading }: { error: string | null; loading: boolean }) {
  if (error) return <Notice>{error}</Notice>
  return loading ? <p className="text-slate-500">Loading…</p> : null
}

export function Notice({ kind = 'error', children }: { kind?: 'error' | 'ok'; children: ReactNode }) {
  const Icon = kind === 'error' ? AlertCircle : CheckCircle2
  const style = kind === 'error'
    ? 'border-rose-200 border-l-rose-600 bg-rose-50 text-rose-800'
    : 'border-emerald-200 border-l-success bg-success-soft text-emerald-900'
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className={`mb-4 flex items-start gap-2 rounded-md border border-l-4 px-4 py-3 text-sm ${style}`}>
      <Icon size={18} className="mt-px shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  )
}

export function Badge({ children, tone = 'slate' }: { children: ReactNode; tone?: 'slate' | 'green' | 'blue' | 'amber' | 'red' }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-700 ring-slate-300/60',
    green: 'bg-success-soft text-success ring-success/25',
    blue: 'bg-brand-soft text-brand ring-brand/25',
    amber: 'bg-amber-50 text-amber-800 ring-amber-300/60',
    red: 'bg-rose-50 text-rose-700 ring-rose-300/60',
  }
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${tones[tone]}`}>
      {children}
    </span>
  )
}

/** The top of every admin page: title, an optional one-line description, and the page's main actions. */
export function PageTitle({ title, description, children }: { title: string; description?: string; children?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-slate-200 pb-5">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-slate-500">{description}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  )
}

/** A small set of buttons to switch between views, e.g. Groups and List. */
export function Segmented<T extends string>(props: {
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}) {
  const { label, value, options, onChange } = props
  return (
    <div className="inline-flex rounded-md border border-slate-200 bg-white p-1 shadow-sm" role="tablist" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={o.value === value}
          onClick={() => onChange(o.value)}
          className={`min-h-8 rounded px-4 text-sm font-medium transition ${
            o.value === value ? 'bg-brand text-white shadow-sm' : 'text-slate-600 hover:bg-slate-50 hover:text-ink'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/** Shown when a list or table has nothing in it. */
export function Empty({ children }: { children: ReactNode }) {
  return <div className={`${card} px-4 py-10 text-center text-sm text-slate-500`}>{children}</div>
}

/** A plain table that scrolls sideways when it is wider than the screen (used by the reports). */
export function Table({ columns, children, className = '', bodyClassName }: {
  columns: string[]
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <div className={`${card} overflow-x-auto ${className}`}>
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>{columns.map((c) => <th key={c} className="px-4 py-3 align-bottom font-semibold">{c}</th>)}</tr>
        </thead>
        <tbody className={bodyClassName}>{children}</tbody>
      </table>
    </div>
  )
}

export type Column<T> = { header: string; cell: (row: T) => ReactNode }

/** A table on a wide screen and a stack of cards on a phone, from the same rows. */
export function DataView<T>(props: {
  rows: T[]
  columns: Column<T>[]
  card: (row: T) => ReactNode
  rowKey: (row: T) => string | number
  empty: string
}) {
  const { rows, columns, card: cardContent, rowKey, empty } = props
  if (rows.length === 0) return <Empty>{empty}</Empty>
  return (
    <>
      <Table className="hidden md:block" bodyClassName="divide-y divide-slate-100" columns={columns.map((c) => c.header)}>
        {rows.map((r) => (
          <tr key={rowKey(r)} className="align-top transition hover:bg-slate-50">
            {columns.map((c) => <td key={c.header} className="px-4 py-3">{c.cell(r)}</td>)}
          </tr>
        ))}
      </Table>
      <div className="space-y-3 md:hidden">
        {rows.map((r) => (
          <div key={rowKey(r)} className={`${card} p-4`}>{cardContent(r)}</div>
        ))}
      </div>
    </>
  )
}

// ---------- filters ----------

export type FilterField =
  | { key: string; label: string; type: 'select'; options: { value: string; label: string }[] }
  | { key: string; label: string; type: 'text' | 'date' }

/** The first field (usually a search box) is always visible. The rest fold into a "Filters" panel. */
export function FilterBar(props: {
  fields: FilterField[]
  params: URLSearchParams
  onChange: (next: URLSearchParams) => void
}) {
  const { fields, params, onChange } = props
  const [open, setOpen] = useState(false)
  const [first, ...rest] = fields
  const active = rest.filter((f) => params.get(f.key)).length

  function set(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    onChange(next)
  }

  function control(f: FilterField, extra = '') {
    return f.type === 'select' ? (
      <select className={`${inputCls} ${extra}`} value={params.get(f.key) ?? ''} onChange={(e) => set(f.key, e.target.value)}>
        <option value="">All</option>
        {f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    ) : (
      <input
        className={`${inputCls} ${extra}`}
        type={f.type}
        placeholder={f.type === 'text' ? f.label : undefined}
        aria-label={f.label}
        value={params.get(f.key) ?? ''}
        onChange={(e) => set(f.key, e.target.value)}
      />
    )
  }

  if (!first) return null
  return (
    <div className={`${card} mb-4 p-3`}>
      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          {first.type === 'text' && (
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden />
          )}
          {control(first, first.type === 'text' ? 'pl-9' : '')}
        </div>
        {rest.length > 0 && (
          <button className={secondary} aria-expanded={open} onClick={() => setOpen(!open)}>
            <SlidersHorizontal size={16} aria-hidden />
            <span className="hidden sm:inline">Filters</span>
            {active > 0 && <span className="rounded-full bg-brand px-1.5 text-xs text-white">{active}</span>}
          </button>
        )}
        {fields.some((f) => params.get(f.key)) && (
          <button
            type="button"
            className={`${linkButton} px-1`}
            onClick={() => {
              // Clear only the filters: other settings in the address (List view, an open panel) stay.
              const next = new URLSearchParams(params)
              fields.forEach((f) => next.delete(f.key))
              onChange(next)
            }}
          >
            Clear
          </button>
        )}
      </div>

      {open && (
        <div className="mt-3 border-t border-slate-100 pt-3">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {rest.map((f) => (
              <div key={f.key}>
                <div className="mb-1 text-xs font-medium text-slate-500">{f.label}</div>
                {control(f)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------- CSV import ----------

export function ImportDialog(props: {
  title: string
  template: string
  onImport: (csv: string) => Promise<ImportResult>
  onClose: () => void
  onDone: () => void
}) {
  const { title, template, onImport, onClose, onDone } = props
  const { busy, error, run } = useSubmit()
  const [result, setResult] = useState<ImportResult | null>(null)

  function downloadTemplate() {
    const url = URL.createObjectURL(new Blob([template], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  async function upload(file: File | undefined) {
    if (!file) return
    await run(async () => {
      setResult(await onImport(await file.text()))
      onDone()
    }, 'Could not import that file.')
  }

  return (
    <Modal onClose={onClose} wide>
      <h3 className="mb-2 text-lg font-semibold text-ink">{title}</h3>
      <p className="mb-4 text-sm text-slate-600">
        Upload a CSV file. Records with the same id are updated, so it is safe to run again.{' '}
        <button className="font-medium text-brand hover:underline" onClick={downloadTemplate}>Download the template</button>
      </p>
      {error && <Notice>{error}</Notice>}
      <label className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-600 transition hover:border-brand hover:bg-brand-soft/40">
        <Upload size={22} className="text-brand" aria-hidden />
        <span><span className="font-semibold text-brand">Choose a CSV file</span> to upload</span>
        <input type="file" accept=".csv,text/csv" disabled={busy} onChange={(e) => upload(e.target.files?.[0])} className="sr-only" />
      </label>
      {busy && <p className="mt-3 text-sm text-slate-500">Importing…</p>}
      {result && (
        <div className="mt-4 text-sm">
          <Notice kind="ok">{result.created} added, {result.updated} updated, {result.errors.length} skipped.</Notice>
          {result.errors.length > 0 && (
            <ul className="list-disc pl-5 text-rose-700">
              {result.errors.map((e) => <li key={e.row}>Row {e.row}: {e.error}</li>)}
            </ul>
          )}
        </div>
      )}
      <div className="mt-5 text-right"><button className={secondary} onClick={onClose}>Close</button></div>
    </Modal>
  )
}
