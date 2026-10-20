import { cn } from '../lib/utils'

export function Brand({ compact = false, className }: { compact?: boolean; className?: string }) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <div className="relative grid size-9 shrink-0 place-items-center rounded-xl border border-primary/25 bg-primary/10 shadow-glow">
        <svg viewBox="0 0 32 32" fill="none" className="size-5" aria-hidden="true">
          <path d="M11 9v9a4 4 0 0 0 4 4h6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" className="text-primary" />
          <circle cx="11" cy="8" r="2.6" fill="currentColor" className="text-primary" />
          <circle cx="11" cy="22" r="2.6" fill="currentColor" className="text-primary" />
          <circle cx="22" cy="22" r="2.6" fill="currentColor" className="text-primary" />
          <path d="M22 14v5.4" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" className="text-primary" />
        </svg>
      </div>
      {!compact && (
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-semibold tracking-tight text-foreground">GitAssign</span>
            <span className="rounded border border-border bg-muted px-1 py-px font-mono text-[9px] text-muted-foreground">
              v1.0
            </span>
          </div>
          <p className="truncate text-[10px] text-muted-foreground">Issue triage intelligence</p>
        </div>
      )}
    </div>
  )
}
