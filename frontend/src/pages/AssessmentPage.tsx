import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Shell from '../EmployeeShell'
import { ApiError, errorMessage, getAssessment, saveAnswer, submitAssessment } from '../api'
import type { Assessment, Kind } from '../api'
import { primary, secondary } from '../styles'

type Step = 'welcome' | 'review' | 'done' | number

const VALUES = [
  'Staff Development', 'Building Trust', 'Passion for Excellence',
  'Commitment', 'One for All, All for Winning',
]

const COPY = {
  joiner: {
    title: (name: string) => `Welcome to United Group, ${name}.`,
    intro:
      'Every new joiner gets a buddy. These five questions help us find someone who works the way you do.',
    privacy: 'Your answers are used only to match you with a buddy and are seen only by the COMPASS team.',
    start: "Let's start",
    thanks: (name: string) =>
      `Thanks, ${name}. Your buddy will appear in your portal as soon as they are assigned.`,
  },
  buddy: {
    title: (name: string) => `Hi ${name}, thanks for being a COMPASS buddy.`,
    intro:
      'These five questions help us pair you with new joiners who work in a similar way to you.',
    privacy: 'Your answers are used only to match you with new joiners and are seen only by the COMPASS team.',
    start: 'Start',
    thanks: () => "You're all set. New joiners assigned to you will appear in your portal.",
  },
}

export default function AssessmentPage() {
  const params = useParams()
  const kind: Kind | null =
    params.kind === 'buddy' || params.kind === 'joiner' ? params.kind : null
  const token = params.token ?? ''

  const [data, setData] = useState<Assessment | null>(null)
  const [error, setError] = useState<string | null>(null)
  // What the server has stored, and the latest save per question that may still be on its way.
  const saved = useRef<Record<number, number>>({})
  const saving = useRef(new Map<number, Promise<boolean>>())
  const [answers, setAnswers] = useState<Record<number, number>>({})
  const [step, setStep] = useState<Step>('welcome')
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    if (!kind) return
    let cancelled = false
    getAssessment(kind, token)
      .then((d) => {
        if (cancelled) return
        setData(d)
        const loaded = Object.fromEntries(
          Object.entries(d.answers ?? {}).map(([k, v]) => [Number(k), v]),
        ) as Record<number, number>
        saved.current = { ...loaded }
        setAnswers(loaded)
        if (d.status === 'submitted') setStep('done')
      })
      .catch((e) => {
        if (cancelled) return
        setError(
          e instanceof ApiError && e.status === 404
            ? 'This link is not valid. Please check your email or contact HR.'
            : e instanceof ApiError
              ? e.message
              : 'Could not load the assessment. Please try again.',
        )
      })
    return () => {
      cancelled = true
    }
  }, [kind, token])

  if (!kind) {
    return <Shell><p className="text-slate-600">This link is not valid.</p></Shell>
  }
  if (error) {
    return <Shell><p className="text-slate-700">{error}</p></Shell>
  }
  if (!data) {
    return <Shell><p className="text-slate-500">Loading…</p></Shell>
  }

  const copy = COPY[kind]
  const questions = data.questions ?? []
  const answeredCount = Object.keys(answers).length

  function start() {
    const next = questions.find((q) => answers[q.number] === undefined)
    setStep(next ? next.number : 'review')
  }

  function choose(question: number, value: number) {
    setAnswers((prev) => ({ ...prev, [question]: value }))
    const save: Promise<boolean> = saveAnswer(kind!, token, question, value)
      .then(() => {
        saved.current[question] = value
        setNotice(null)
        return true
      })
      .catch(() => {
        // Only undo if no newer answer to this question has been picked since.
        if (saving.current.get(question) === save) {
          setAnswers((prev) => {
            const next = { ...prev }
            if (saved.current[question] === undefined) delete next[question]
            else next[question] = saved.current[question]
            return next
          })
        }
        setNotice('We could not save that answer. Please check your connection and choose it again.')
        return false
      })
    saving.current.set(question, save)
  }

  function next() {
    if (editing) {
      setEditing(false)
      setStep('review')
    } else if (typeof step === 'number' && step < 5) {
      setStep(step + 1)
    } else {
      setStep('review')
    }
  }

  function back() {
    if (editing) {
      setEditing(false)
      setStep('review')
    } else if (step === 1) {
      setStep('welcome')
    } else if (typeof step === 'number') {
      setStep(step - 1)
    }
  }

  function change(question: number) {
    setEditing(true)
    setStep(question)
  }

  async function submit() {
    setBusy(true)
    try {
      const results = await Promise.all(saving.current.values())
      if (results.includes(false)) return // the notice already says which answer to pick again
      await submitAssessment(kind!, token)
      setNotice(null)
      setStep('done')
    } catch (e) {
      setNotice(errorMessage(e, 'Could not submit. Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  const banner = notice && (
    <div className="mb-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">{notice}</div>
  )

  if (step === 'welcome') {
    return (
      <Shell>
        <h1 className="text-xl font-semibold text-ink">{copy.title(data.first_name)}</h1>
        <p className="mt-3 text-slate-600">{data.intro || copy.intro}</p>
        {kind === 'joiner' && (
          <div className="mt-5 flex flex-wrap gap-2">
            {VALUES.map((v) => (
              <span key={v} className="rounded-full bg-success-soft px-3 py-1 text-xs font-medium text-success">
                {v}
              </span>
            ))}
          </div>
        )}
        <ul className="mt-6 list-disc space-y-2 pl-5 text-sm text-slate-600">
          <li>It takes about 2 minutes.</li>
          <li>
            There are no right or wrong answers. Pick what is true for you on a normal workday, not
            what sounds best.
          </li>
          <li>{copy.privacy}</li>
        </ul>
        <button className={`${primary} mt-8 w-full`} onClick={start}>
          {answeredCount > 0 ? 'Continue' : copy.start}
        </button>
      </Shell>
    )
  }

  if (typeof step === 'number') {
    const q = questions.find((x) => x.number === step)
    if (!q) return <Shell><p className="text-slate-600">Question not found.</p></Shell>
    return (
      <Shell>
        {banner}
        <div className="mb-1 text-sm text-slate-500">Question {step} of 5</div>
        <div className="mb-6 flex gap-1.5">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className={`h-1.5 flex-1 rounded-full ${i <= step ? 'bg-brand' : 'bg-slate-200'}`} />
          ))}
        </div>
        <h2 className="mb-5 text-xl font-semibold leading-snug">{q.text}</h2>
        <div className="space-y-3">
          {q.options.map((o) => {
            const selected = answers[q.number] === o.value
            return (
              <button
                key={o.value}
                type="button"
                aria-pressed={selected}
                onClick={() => choose(q.number, o.value)}
                className={`w-full rounded-lg border-2 px-4 py-3.5 text-left transition ${
                  selected
                    ? 'border-brand bg-brand text-white'
                    : 'border-slate-200 bg-white hover:border-brand/50'
                }`}
              >
                {o.label}
              </button>
            )
          })}
        </div>
        <div className="mt-8 flex justify-between gap-3">
          <button className={secondary} onClick={back}>Back</button>
          <button className={primary} disabled={answers[q.number] === undefined} onClick={next}>
            {editing ? 'Done' : 'Next'}
          </button>
        </div>
      </Shell>
    )
  }

  if (step === 'review') {
    return (
      <Shell>
        {banner}
        <h2 className="mb-5 text-xl font-semibold text-ink">Review your answers</h2>
        <div className="divide-y divide-slate-100">
          {questions.map((q) => (
            <div key={q.number} className="flex items-start justify-between gap-4 py-3">
              <div>
                <div className="text-sm text-slate-500">{q.text}</div>
                <div className="mt-0.5 font-medium">
                  {q.options.find((o) => o.value === answers[q.number])?.label ?? '—'}
                </div>
              </div>
              <button className="shrink-0 text-sm font-medium text-brand hover:underline" onClick={() => change(q.number)}>
                Change
              </button>
            </div>
          ))}
        </div>
        <button
          className={`${primary} mt-8 w-full`}
          disabled={busy || answeredCount < 5}
          onClick={submit}
        >
          {busy ? 'Submitting…' : 'Submit'}
        </button>
      </Shell>
    )
  }

  return (
    <Shell>
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-success-soft text-2xl text-success">
        ✓
      </div>
      <p className="text-center text-lg text-slate-700">{copy.thanks(data.first_name)}</p>
      <div className="mt-6 text-center">
        <Link to="/portal" className={primary}>Back to my portal</Link>
      </div>
    </Shell>
  )
}