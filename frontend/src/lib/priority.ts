export type PriorityTier = 'Critical' | 'High' | 'Medium' | 'Low'

interface PriorityMeta {
  badge: 'destructive' | 'warning' | 'info' | 'success'
  dot: string
  text: string
  bar: string
  soft: string
}

export const PRIORITY_META: Record<PriorityTier, PriorityMeta> = {
  Critical: {
    badge: 'destructive',
    dot: 'bg-rose-400',
    text: 'text-rose-400',
    bar: 'bg-rose-400',
    soft: 'border-rose-500/25 bg-rose-500/10 text-rose-300',
  },
  High: {
    badge: 'warning',
    dot: 'bg-amber-400',
    text: 'text-amber-400',
    bar: 'bg-amber-400',
    soft: 'border-amber-500/25 bg-amber-500/10 text-amber-300',
  },
  Medium: {
    badge: 'info',
    dot: 'bg-sky-400',
    text: 'text-sky-400',
    bar: 'bg-sky-400',
    soft: 'border-sky-500/25 bg-sky-500/10 text-sky-300',
  },
  Low: {
    badge: 'success',
    dot: 'bg-emerald-400',
    text: 'text-emerald-400',
    bar: 'bg-emerald-400',
    soft: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300',
  },
}

export const PRIORITY_ORDER: PriorityTier[] = ['Critical', 'High', 'Medium', 'Low']

export function priorityMeta(tier?: string): PriorityMeta {
  return PRIORITY_META[(tier as PriorityTier) ?? 'Medium'] ?? PRIORITY_META.Medium
}
