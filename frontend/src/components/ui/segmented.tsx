import { cn } from '../../lib/utils'

export interface SegmentedOption<T extends string> {
  value: T
  label: string
  count?: number
}

interface SegmentedProps<T extends string> {
  options: SegmentedOption<T>[]
  value: T
  onChange: (value: T) => void
  className?: string
}

export function Segmented<T extends string>({ options, value, onChange, className }: SegmentedProps<T>) {
  return (
    <div className={cn('inline-flex items-center rounded-lg border border-border bg-muted/50 p-0.5', className)}>
      {options.map(option => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={cn(
              'inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[11px] font-medium capitalize transition-colors',
              active
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {option.label}
            {option.count !== undefined && (
              <span className={cn('tabular-nums text-[10px]', active ? 'text-primary' : 'text-muted-foreground/70')}>
                {option.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
