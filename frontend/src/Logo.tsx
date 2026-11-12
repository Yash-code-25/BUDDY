import { Compass } from 'lucide-react'

/** The COMPASS mark and name. */
export default function Logo({ subtitle = true }: { subtitle?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand text-white">
        <Compass size={20} strokeWidth={2.2} aria-hidden />
      </span>
      <span className="leading-tight">
        <span className="block text-[15px] font-bold tracking-[0.12em] text-ink">COMPASS</span>
        {subtitle && (
          <span className="block text-xs text-slate-500">United Group buddy program</span>
        )}
      </span>
    </span>
  )
}
