import { useCallback, useMemo, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  BookOpen, Camera, ChefHat, ChevronRight, Clapperboard, Feather, Flower2, Footprints, Gamepad2, Goal,
  HandHeart, MapPin, Music, Palette, Plane, Sparkles, Trophy,
} from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { getClubs } from './api'
import type { ClubData } from './api'
import { formatDate, useLoad } from './helpers'
import { useOpenBuddy } from './useOpenBuddy'
import { LoadState, Modal, PageTitle } from './ui'
import { card, inputCls, secondary } from '../styles'

const ICONS: Record<string, LucideIcon> = {
  Cricket: Trophy, Football: Goal, Badminton: Feather, 'Running and fitness': Footprints, Yoga: Flower2,
  Books: BookOpen, Cooking: ChefHat, Music, Movies: Clapperboard, Travel: Plane, Photography: Camera,
  'Art and craft': Palette, Gaming: Gamepad2, Volunteering: HandHeart,
}
const AVATARS_SHOWN = 5

const initials = (name: string) => name.split(/\s+/).map((p) => p[0]).join('').slice(0, 2).toUpperCase()
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

function ClubIcon({ interest, size = 'md' }: { interest: string; size?: 'md' | 'lg' }) {
  const Icon = ICONS[interest] ?? Sparkles
  const box = size === 'lg' ? 'h-12 w-12' : 'h-10 w-10'
  return (
    <span className={`flex ${box} shrink-0 items-center justify-center rounded-lg bg-brand-soft text-brand`}>
      <Icon size={size === 'lg' ? 24 : 20} aria-hidden />
    </span>
  )
}

/** A club at a glance: what, where, who (as faces), how many. The whole card opens its members. */
function ClubCard({ club, onOpen }: { club: ClubData; onOpen: () => void }) {
  const people = [
    ...club.joiners.map((j) => ({ key: `j${j.id}`, name: j.name, joiner: true })),
    ...club.buddies.map((b) => ({ key: `b${b.id}`, name: b.name, joiner: false })),
  ]
  const more = people.length - AVATARS_SHOWN
  return (
    <button
      type="button"
      onClick={onOpen}
      className={`${card} group flex h-full w-full flex-col p-4 text-left transition hover:border-brand/40 hover:shadow-[0_4px_14px_rgba(15,27,45,0.08)] focus-visible:outline-2 focus-visible:outline-brand`}
    >
      <div className="flex items-start gap-3">
        <ClubIcon interest={club.interest} />
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold text-ink">{club.interest}</div>
          <div className="mt-0.5 flex items-center gap-1 text-sm text-slate-500">
            <MapPin size={14} aria-hidden /> {club.location}
          </div>
        </div>
        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-sm font-semibold text-ink">{people.length}</span>
      </div>

      <div className="mt-4 flex items-center">
        {people.slice(0, AVATARS_SHOWN).map((p, i) => (
          <span
            key={p.key}
            title={`${p.name}${p.joiner ? ' (new joiner)' : ''}`}
            className={`flex h-8 w-8 items-center justify-center rounded-full text-[11px] font-semibold ring-2 ring-white ${
              i > 0 ? '-ml-1' : ''
            } ${p.joiner ? 'bg-success-soft text-success' : 'bg-brand-soft text-brand'}`}
          >
            {initials(p.name)}
          </span>
        ))}
        {more > 0 && (
          <span className="-ml-1 flex h-8 min-w-8 items-center justify-center rounded-full bg-slate-100 px-1.5 text-[11px] font-semibold text-slate-600 ring-2 ring-white">
            +{more}
          </span>
        )}
      </div>

      <div className="mt-auto flex items-center justify-between gap-2 pt-4 text-sm">
        <span className="text-slate-600">
          {plural(club.buddies.length, 'buddy', 'buddies')}
          {club.joiners.length > 0 && (
            <span className="font-medium text-success"> · {plural(club.joiners.length, 'new joiner', 'new joiners')}</span>
          )}
        </span>
        <span className="flex items-center gap-0.5 font-medium text-brand group-hover:underline">
          Members <ChevronRight size={16} aria-hidden />
        </span>
      </div>
    </button>
  )
}

/** Everyone in one club: new joiners first (they are why clubs matter), then buddies. */
function ClubMembers({ club, onClose }: { club: ClubData; onClose: () => void }) {
  const openBuddy = useOpenBuddy()
  return (
    <Modal onClose={onClose} wide>
      <div className="mb-5 flex items-start gap-3">
        <ClubIcon interest={club.interest} size="lg" />
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-semibold text-ink">{club.interest}</h2>
          <p className="flex items-center gap-1 text-sm text-slate-500">
            <MapPin size={14} aria-hidden /> {club.location} · {plural(club.buddies.length + club.joiners.length, 'member', 'members')}
          </p>
        </div>
        <button type="button" className={secondary} onClick={onClose}>Close</button>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            New joiners ({club.joiners.length})
          </h3>
          {club.joiners.length === 0 ? (
            <p className="rounded-md bg-slate-50 px-3 py-2.5 text-sm text-slate-500">None yet</p>
          ) : (
            <ul className="divide-y divide-slate-100 rounded-md border border-slate-200">
              {club.joiners.map((j) => (
                <li key={j.id}>
                  <Link to={`/hr/joiners/${j.id}`} className="flex items-center gap-3 px-3 py-2.5 hover:bg-slate-50">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-success-soft text-[11px] font-semibold text-success">
                      {initials(j.name)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-ink">{j.name}</span>
                      <span className="block truncate text-xs text-slate-500">{j.department} · joins {formatDate(j.date_of_joining)}</span>
                    </span>
                    <ChevronRight size={16} className="shrink-0 text-slate-300" aria-hidden />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Buddies ({club.buddies.length})
          </h3>
          {club.buddies.length === 0 ? (
            <p className="rounded-md bg-slate-50 px-3 py-2.5 text-sm text-slate-500">None yet</p>
          ) : (
            <ul className="divide-y divide-slate-100 rounded-md border border-slate-200">
              {club.buddies.map((b) => (
                <li key={b.id}>
                  <button
                    type="button"
                    onClick={() => { onClose(); openBuddy(b.id) }}
                    className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-slate-50"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-soft text-[11px] font-semibold text-brand">
                      {initials(b.name)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-ink">{b.name}</span>
                      <span className="block truncate text-xs text-slate-500">{[b.designation, b.department].filter(Boolean).join(' · ')}</span>
                    </span>
                    <ChevronRight size={16} className="shrink-0 text-slate-300" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </Modal>
  )
}

/** Joiners and buddies grouped by what they enjoy, at each location. Information only: no emails. */
export default function ClubsPage() {
  const [params, setParams] = useSearchParams()
  const [opened, setOpened] = useState<ClubData | null>(null)
  const location = params.get('location') ?? ''
  const interest = params.get('interest') ?? ''
  // Load every club once and filter here, so the location chips can show their counts.
  const { data, error } = useLoad(useCallback(() => getClubs(''), []), 'Could not load the clubs.')

  function choose(key: 'location' | 'interest', value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    next.delete('buddy')
    setParams(next, { replace: true })
  }

  const all = useMemo(() => data?.clubs ?? [], [data])
  const clubs = all.filter((c) => (!location || c.location === location) && (!interest || c.interest === interest))
  const perLocation = (l: string) => all.filter((c) => c.location === l && (!interest || c.interest === interest)).length
  const members = clubs.reduce((n, c) => n + c.buddies.length + c.joiners.length, 0)
  const withJoiners = clubs.filter((c) => c.joiners.length > 0).length

  const chip = (value: string, label: string, count: number) => {
    const on = location === value
    return (
      <button
        key={value || 'all'}
        type="button"
        aria-pressed={on}
        onClick={() => choose('location', value)}
        className={`inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-sm font-medium transition ${
          on ? 'border-brand bg-brand text-white' : 'border-slate-200 bg-white text-slate-700 hover:border-slate-400'
        }`}
      >
        {label}
        <span className={`rounded-full px-1.5 text-xs ${on ? 'bg-white/20' : 'bg-slate-100 text-slate-500'}`}>{count}</span>
      </button>
    )
  }

  return (
    <div>
      <PageTitle title="Clubs" />

      <LoadState error={error} loading={!data} />
      {data && (
        <>
          <div className={`${card} mb-5 space-y-3 p-4`}>
            <div className="-mx-1 flex gap-2 overflow-x-auto px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden" role="group" aria-label="Location">
              {chip('', 'All locations', all.filter((c) => !interest || c.interest === interest).length)}
              {data.locations.map((l) => chip(l, l, perLocation(l)))}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <select
                className={`${inputCls} sm:max-w-xs`}
                aria-label="Interest"
                value={interest}
                onChange={(e) => choose('interest', e.target.value)}
              >
                <option value="">All interests</option>
                {data.interests.map((i) => <option key={i} value={i}>{i}</option>)}
              </select>
              <p className="text-sm text-slate-500">
                <span className="font-semibold text-ink">{plural(clubs.length, 'club', 'clubs')}</span>
                {' · '}{plural(members, 'membership', 'memberships')}
                {withJoiners > 0 && <> · <span className="font-medium text-success">{withJoiners} with new joiners</span></>}
              </p>
            </div>
          </div>

          {clubs.length === 0 ? (
            <p className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
              No clubs here yet. Clubs appear as joiners and buddies pick their hobbies in their portal.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {clubs.map((club) => (
                <ClubCard key={`${club.interest}|${club.location}`} club={club} onOpen={() => setOpened(club)} />
              ))}
            </div>
          )}
        </>
      )}

      {opened && <ClubMembers club={opened} onClose={() => setOpened(null)} />}
    </div>
  )
}
