import { useEffect, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import { ArrowRight, ClipboardList, Hand, HeartHandshake, Hourglass, UserCheck, UserX } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getHome } from './api'
import type { Tile } from './api'
import { card } from '../styles'
import { Notice, PageTitle } from './ui'

// What needs a person to act today, then the quiet overview numbers.
const ATTENTION = ['awaiting_pairing', 'manual', 'awaiting_assessment']

const ICON: Record<string, LucideIcon> = {
  awaiting_pairing: Hand,
  manual: UserX,
  awaiting_assessment: Hourglass,
  active_pairings: UserCheck,
  pool: HeartHandshake,
  buddies_pending: ClipboardList,
}

function TileCard({ tile, act }: { tile: Tile; act: boolean }) {
  const Icon = ICON[tile.key] ?? ClipboardList
  const needsAction = act && tile.count > 0
  return (
    <Link
      to={tile.link}
      className={`${card} group flex flex-col p-4 transition sm:p-5 hover:border-brand/40 hover:shadow-md ${needsAction ? 'border-amber-300' : ''}`}
    >
      <div className="flex items-start justify-between">
        <span className={`flex h-9 w-9 items-center justify-center rounded-lg sm:h-10 sm:w-10 ${
          needsAction ? 'bg-amber-50 text-amber-600' : 'bg-brand-soft text-brand'
        }`}>
          <Icon size={20} aria-hidden />
        </span>
        <ArrowRight size={16} className="hidden text-slate-300 transition sm:block group-hover:translate-x-0.5 group-hover:text-brand" aria-hidden />
      </div>
      <div className={`mt-3 text-2xl font-semibold tracking-tight sm:mt-4 sm:text-3xl ${tile.count === 0 ? 'text-slate-300' : 'text-ink'}`}>
        {tile.count}
      </div>
      <div className="mt-1 text-sm font-medium leading-snug text-slate-600">{tile.label}</div>
      {tile.detail && <div className="mt-0.5 text-xs text-slate-400">{tile.detail}</div>}
      {tile.urgent ? (
        <span className="mt-3 inline-flex w-fit rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-medium text-rose-700 ring-1 ring-inset ring-rose-200">
          {tile.urgent} joining within 3 days
        </span>
      ) : null}
    </Link>
  )
}

export default function HomePage() {
  const [tiles, setTiles] = useState<Tile[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getHome().then((d) => setTiles(d.tiles)).catch(() => setError('Could not load the home page.'))
  }, [])

  if (error) return <Notice>{error}</Notice>
  if (!tiles) return <p className="text-slate-500">Loading…</p>

  const attention = ATTENTION.map((k) => tiles.find((t) => t.key === k)).filter((t): t is Tile => !!t)
  const overview = tiles.filter((t) => !ATTENTION.includes(t.key))

  return (
    <div>
      <PageTitle title="Home" />
      <h2 className="mb-3 text-sm font-semibold text-slate-700">Needs your attention</h2>
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3">
        {attention.map((t) => <TileCard key={t.key} tile={t} act />)}
      </div>

      <h2 className="mb-3 mt-8 text-sm font-semibold text-slate-700">Overview</h2>
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3">
        {overview.map((t) => <TileCard key={t.key} tile={t} act={false} />)}
      </div>
    </div>
  )
}
