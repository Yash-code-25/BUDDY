import { useState } from 'react'
import type { FormEvent } from 'react'
import { useSubmit } from '../useSubmit'
import { inputCls, primary, secondary } from '../styles'
import { useFilterOptions } from './helpers'
import type { FilterOptions } from './api'
import { ChoiceSelect, Field, Modal, Notice } from './ui'

/** [key, label, input type]. Department and location are always drop-downs of the Settings lists. */
export type FieldSpec = [key: string, label: string, type?: string]

type Form = Record<string, string>

/** One field of a joiner or buddy form. */
export function FormField({ spec: [key, label, type], form, setForm, options }: {
  spec: FieldSpec
  form: Form
  setForm: (form: Form) => void
  options: FilterOptions
}) {
  const set = (value: string) => setForm({ ...form, [key]: value })
  return (
    <Field label={label}>
      {key === 'department' || key === 'location' ? (
        <ChoiceSelect value={form[key] ?? ''} choices={options[key]} onChange={set} />
      ) : (
        <input className={inputCls} type={type} value={form[key] ?? ''} onChange={(e) => set(e.target.value)} />
      )}
    </Field>
  )
}

/** The "Add a joiner" and "Add a buddy" dialogs: the main fields, then optional ones under "More details". */
export function PersonDialog({ title, subtitle, submitLabel, main, more, intro, onSubmit, onClose, onDone }: {
  title: string
  subtitle?: string
  submitLabel: string
  main: FieldSpec[]
  more: FieldSpec[]
  intro?: string // label of an optional free-text introduction
  onSubmit: (form: Form) => Promise<unknown>
  onClose: () => void
  onDone: () => void
}) {
  const [form, setForm] = useState<Form>({})
  const { busy, error, run } = useSubmit()
  const options = useFilterOptions()
  const fields = (specs: FieldSpec[]) =>
    specs.map((spec) => <FormField key={spec[0]} spec={spec} form={form} setForm={setForm} options={options} />)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (await run(() => onSubmit(form))) {
      onDone()
      onClose()
    }
  }

  return (
    <Modal onClose={onClose} wide>
      <form onSubmit={submit}>
        <h3 className={`${subtitle ? 'mb-1' : 'mb-4'} text-lg font-semibold text-ink`}>{title}</h3>
        {subtitle && <p className="mb-4 text-sm text-slate-500">{subtitle}</p>}
        {error && <Notice>{error}</Notice>}
        <div className="grid gap-3 sm:grid-cols-2">{fields(main)}</div>
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-medium text-brand">More details (optional)</summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">{fields(more)}</div>
          {intro && (
            <div className="mt-3">
              <Field label={intro}>
                <textarea className={inputCls} rows={3} value={form.intro ?? ''} onChange={(e) => setForm({ ...form, intro: e.target.value })} />
              </Field>
            </div>
          )}
        </details>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className={secondary} onClick={onClose}>Cancel</button>
          <button type="submit" className={primary} disabled={busy}>{busy ? 'Saving…' : submitLabel}</button>
        </div>
      </form>
    </Modal>
  )
}
