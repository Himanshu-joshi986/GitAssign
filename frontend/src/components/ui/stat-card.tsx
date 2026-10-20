import * as React from 'react'
import { motion } from 'motion/react'
import { cn } from '../../lib/utils'

interface StatCardProps {
  label: string
  value: React.ReactNode
  icon: React.ReactNode
  hint?: string
  accent?: 'emerald' | 'sky' | 'violet' | 'amber' | 'rose'
  delay?: number
}

const ACCENTS: Record<NonNullable<StatCardProps['accent']>, string> = {
  emerald: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400',
  sky: 'border-sky-500/20 bg-sky-500/10 text-sky-400',
  violet: 'border-violet-500/20 bg-violet-500/10 text-violet-400',
  amber: 'border-amber-500/20 bg-amber-500/10 text-amber-400',
  rose: 'border-rose-500/20 bg-rose-500/10 text-rose-400',
}

export function StatCard({ label, value, icon, hint, accent = 'emerald', delay = 0 }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: [0.22, 1, 0.36, 1] }}
      className="surface group relative overflow-hidden p-4"
    >
      <div className="pointer-events-none absolute -right-8 -top-10 size-24 rounded-full bg-primary/5 blur-2xl transition-opacity group-hover:opacity-100" />
      <div className="flex items-start justify-between">
        <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">{label}</span>
        <span className={cn('grid size-7 place-items-center rounded-lg border [&_svg]:size-3.5', ACCENTS[accent])}>
          {icon}
        </span>
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight tabular-nums">{value}</div>
      {hint && <p className="mt-1 text-[11px] text-muted-foreground">{hint}</p>}
    </motion.div>
  )
}
