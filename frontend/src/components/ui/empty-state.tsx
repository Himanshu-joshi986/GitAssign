import * as React from 'react'
import { cn } from '../../lib/utils'

interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  icon: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
  compact?: boolean
}

export function EmptyState({ icon, title, description, action, compact, className, ...props }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center',
        compact ? 'gap-2 py-10' : 'gap-3 py-16',
        className,
      )}
      {...props}
    >
      <div className="grid size-11 place-items-center rounded-xl border border-border bg-muted/60 text-muted-foreground [&_svg]:size-5">
        {icon}
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        {description && (
          <p className="mx-auto max-w-sm text-xs leading-relaxed text-muted-foreground">{description}</p>
        )}
      </div>
      {action}
    </div>
  )
}
