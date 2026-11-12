// The shared look of buttons, inputs and cards, for the admin screens and the joiner and buddy
// portal alike. Controls are at least 40px tall so they are easy to tap on a phone.

const button =
  'inline-flex min-h-10 items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition ' +
  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ' +
  'disabled:cursor-not-allowed disabled:opacity-50'

export const primary = `${button} bg-brand text-white shadow-sm hover:bg-brand-dark`
export const secondary = `${button} border border-slate-300 bg-white text-slate-700 shadow-sm hover:border-slate-400 hover:bg-slate-50`

export const inputCls =
  'min-h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-base text-ink placeholder:text-slate-400 ' +
  'outline-none transition focus:border-brand focus:ring-3 focus:ring-brand/15 sm:text-sm'

export const card = 'rounded-lg border border-slate-200 bg-white shadow-[0_1px_2px_rgba(15,27,45,0.05)]'

// A section of a page: a white box with a border.
export const panel = `${card} p-4 sm:p-5`

// A small text-style action (Edit, Remove, Details) inside rows and cards.
export const linkButton = 'min-h-10 text-sm font-medium text-brand hover:text-brand-dark hover:underline'
// The one action at the end of a table row (Pause, Edit, Details).
export const rowAction = 'min-h-10 font-medium text-brand hover:text-brand-dark hover:underline'
