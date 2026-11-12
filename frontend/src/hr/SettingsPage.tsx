import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { getSettings, saveSettings } from './api'
import type { EmailSettings, SettingsData } from './api'
import { useSubmit } from '../useSubmit'
import { Field, Notice, PageTitle } from './ui'
import { inputCls, panel, primary } from '../styles'

type NumberKey = { [K in keyof SettingsData]: SettingsData[K] extends number ? K : never }[keyof SettingsData]
type EmailTextKey = Exclude<keyof EmailSettings, 'office_details'>

type NumberSetting = { key: NumberKey; label: string; hint: string }

// The few settings the Program admin is likely to change.
const BASIC: NumberSetting[] = [
  { key: 'candidates_per_tier', label: 'Buddies shown per tier', hint: 'The rest sit under "Show more".' },
  { key: 'manual_cutoff_day', label: 'Questions due (days before joining)', hint: 'Asked in the login email. Not answered by then means manual pairing. Joiners added 10 days or less before joining get 2 days.' },
]

// When emails 3 and 4 go out (notifications/prejoining.py).
const COMPANY_DAYS = 14
const DAY_ONE_DAYS = 3

/** One of the joiner's 5 emails, numbered in the order they arrive, with the settings it uses. */
function EmailCard({ number, title, when, children }: { number: number; title: string; when: string; children: ReactNode }) {
  return (
    <li className="rounded-lg border border-slate-200 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-soft text-sm font-semibold text-brand">
          {number}
        </span>
        <span className="font-medium text-ink">{title}</span>
        <span className="ml-auto rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{when}</span>
      </div>
      {children}
    </li>
  )
}

// The matching rules themselves. Change these only after a pilot has shown they need it.
const ADVANCED: NumberSetting[] = [
  { key: 'close_gap', label: 'Close answer gap', hint: 'A gap this size or less counts as close.' },
  { key: 'strong_threshold', label: 'Strong needs', hint: 'Close answers out of 5.' },
  { key: 'good_threshold', label: 'Good needs', hint: 'Close answers out of 5.' },
  { key: 'weaker_threshold', label: 'Weaker needs', hint: 'Shown only if nothing better exists.' },
  { key: 'amber_gap', label: 'Amber flag at a gap of', hint: 'A style difference worth noting.' },
  { key: 'red_gap', label: 'Red flag at a gap of', hint: 'Opposite styles.' },
  { key: 'old_answers_months', label: 'Old answers after (months)', hint: 'Adds an "Old answers" note.' },
]

export default function SettingsPage() {
  const [form, setForm] = useState<SettingsData | null>(null)
  const [saved, setSaved] = useState(false)
  const [officeAt, setOfficeAt] = useState('') // the location whose office is being edited
  const { busy, error, setError, run } = useSubmit()

  useEffect(() => {
    getSettings().then(setForm).catch(() => setError('Could not load the settings.'))
  }, [setError])

  if (!form) return error ? <Notice>{error}</Notice> : <p className="text-slate-500">Loading…</p>

  async function save() {
    if (!form) return
    setSaved(false)
    await run(async () => {
      setForm(await saveSettings(form))
      setSaved(true)
    })
  }

  const update = (patch: Partial<SettingsData>) => {
    setSaved(false)
    setForm({ ...form, ...patch })
  }
  const numberField = (n: NumberSetting) => (
    <Field key={n.key} label={n.label}>
      <input
        className={inputCls}
        type="number"
        inputMode="numeric"
        value={form[n.key]}
        onChange={(e) => update({ [n.key]: Number(e.target.value) })}
      />
      <span className="mt-1 block text-xs text-slate-400">{n.hint}</span>
    </Field>
  )

  const textField = (key: EmailTextKey, label: string, hint?: string) => (
    <Field key={key} label={label}>
      <input className={inputCls} value={form[key]} onChange={(e) => update({ [key]: e.target.value })} />
      {hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </Field>
  )

  // Office address and map link, one per location: pick the location, then edit its office.
  const locations = form.locations.map((l) => l.trim()).filter(Boolean)
  const location = locations.includes(officeAt) ? officeAt : locations[0] ?? ''
  const office = form.office_details[location] ?? {}
  const setOffice = (patch: { address?: string; map_link?: string }) =>
    update({ office_details: { ...form.office_details, [location]: { ...office, ...patch } } })

  return (
    <div className="max-w-3xl pb-20">
      <PageTitle title="Settings" description="How matching works, when emails go out, and the words joiners and buddies see." />
      <p className="mb-4 text-sm text-slate-500">
        Changes are logged and apply to new matches only. Earlier matches keep the rules they were made with.
      </p>
      {error && <Notice>{error}</Notice>}
      {saved && <Notice kind="ok">Saved.</Notice>}

      <section className={`mb-4 ${panel}`}>
        <h2 className="mb-3 font-semibold text-slate-700">Pairing</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {BASIC.map(numberField)}
        </div>
      </section>

      <section className={`mb-4 ${panel}`}>
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-semibold text-slate-700">Pre-joining emails</h2>
          <span className="text-xs text-slate-500">Blank fields are left out of the emails.</span>
        </div>

        <ol className="space-y-3">
          <EmailCard number={1} title="Welcome to United Group" when="When added">
            <p className="text-sm text-slate-500">Sent as it is. Nothing to set.</p>
          </EmailCard>

          <EmailCard number={2} title="Your COMPASS login details" when="When added">
            <p className="text-sm text-slate-500">
              Username, password, and the 5 questions to answer by {form.manual_cutoff_day} days before joining (set under Pairing).
            </p>
          </EmailCard>

          <EmailCard number={3} title="Get to know United Group" when={`${COMPANY_DAYS} days before`}>
            <div className="grid gap-4 sm:grid-cols-2">
              {textField('story_video_link', 'Our story video link', 'The Watch our story button.')}
              {textField('handbook_link', 'Pre-joining handbook link', 'A link to the handbook PDF, e.g. on SharePoint.')}
              {textField('linkedin_link', 'LinkedIn page')}
              {textField('instagram_link', 'Instagram page')}
            </div>
          </EmailCard>

          <EmailCard number={4} title="Everything you need for Day 1" when={`${DAY_ONE_DAYS} days before`}>
            <div className="mb-4 rounded-md border border-slate-200 bg-slate-50 p-3 sm:p-4">
              <div className="mb-3 text-sm font-medium text-slate-700">Office by location</div>
              <div className="grid gap-4 sm:grid-cols-[11rem_1fr]">
                <Field label="Location">
                  <select className={inputCls} value={location} onChange={(e) => setOfficeAt(e.target.value)}>
                    {locations.map((l) => (
                      <option key={l} value={l}>{l}{form.office_details[l]?.address ? '' : ' (not set)'}</option>
                    ))}
                  </select>
                </Field>
                <div className="grid gap-4">
                  <Field label={`Office address, ${location}`}>
                    <input className={inputCls} value={office.address ?? ''} onChange={(e) => setOffice({ address: e.target.value })} />
                  </Field>
                  <Field label={`Map link, ${location}`}>
                    <input className={inputCls} value={office.map_link ?? ''} onChange={(e) => setOffice({ map_link: e.target.value })} />
                  </Field>
                </div>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {textField('contact_phone', 'Phone for Day 1 changes', '"If anything changes, call us on…"')}
              {textField('dress_code', 'What to wear')}
            </div>
            <p className="mt-3 text-xs text-slate-500">Each joiner's manager and reporting time are on their own page.</p>
          </EmailCard>

          <EmailCard number={5} title="See you tomorrow" when="1 day before">
            <p className="text-sm text-slate-500">Uses the office address above and each joiner's manager and reporting time.</p>
          </EmailCard>
        </ol>
      </section>

      <section className={`mb-4 ${panel}`}>
        <h2 className="mb-1 font-semibold text-slate-700">Departments and locations</h2>
        <p className="mb-3 text-sm text-slate-500">
          Joiners and buddies are given one of each from these lists, so the match always compares the same
          spelling. One per line. One that people still have cannot be removed.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Departments">
            <textarea className={inputCls} rows={8} value={form.departments.join('\n')} onChange={(e) => update({ departments: e.target.value.split('\n') })} />
          </Field>
          <Field label="Locations">
            <textarea className={inputCls} rows={8} value={form.locations.join('\n')} onChange={(e) => update({ locations: e.target.value.split('\n') })} />
          </Field>
        </div>
      </section>

      <section className={`mb-4 ${panel}`}>
        <h2 className="mb-3 font-semibold text-slate-700">Welcome texts</h2>
        <div className="grid gap-4">
          <Field label="Joiner">
            <textarea className={inputCls} rows={3} value={form.joiner_intro} onChange={(e) => update({ joiner_intro: e.target.value })} />
          </Field>
          <Field label="Buddy">
            <textarea className={inputCls} rows={3} value={form.buddy_intro} onChange={(e) => update({ buddy_intro: e.target.value })} />
          </Field>
        </div>
      </section>

      <details className={`mb-4 ${panel}`}>
        <summary className="cursor-pointer font-semibold text-slate-700">Advanced matching rules</summary>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">{ADVANCED.map(numberField)}</div>
      </details>

      {/* Always in reach: pinned to the bottom of the screen, on phones and laptops. */}
      <div className="fixed inset-x-0 bottom-0 z-10 border-t border-slate-200 bg-white/95 p-3 backdrop-blur sm:sticky sm:bottom-4 sm:flex sm:items-center sm:justify-between sm:gap-4 sm:rounded-lg sm:border sm:px-4 sm:shadow-[0_4px_12px_rgba(15,27,45,0.08)]">
        <span className="hidden text-sm text-slate-500 sm:block">{saved ? 'All changes saved.' : 'Changes apply once you save.'}</span>
        <button className={`${primary} w-full sm:w-auto`} disabled={busy} onClick={save}>
          {busy ? 'Saving…' : 'Save settings'}
        </button>
      </div>
      <p className="mt-6 text-xs text-slate-400">
        Question wording is versioned in the Django admin under Question sets. An answered set is locked.
      </p>
    </div>
  )
}
