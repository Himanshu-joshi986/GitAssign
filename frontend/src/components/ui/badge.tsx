import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium leading-none transition-colors [&_svg]:size-3',
  {
    variants: {
      variant: {
        default: 'border-primary/30 bg-primary/12 text-primary',
        secondary: 'border-border bg-secondary text-secondary-foreground',
        outline: 'border-border text-muted-foreground',
        destructive: 'border-destructive/30 bg-destructive/12 text-destructive',
        warning: 'border-amber-500/30 bg-amber-500/12 text-amber-400',
        info: 'border-sky-500/30 bg-sky-500/12 text-sky-400',
        success: 'border-emerald-500/30 bg-emerald-500/12 text-emerald-400',
        muted: 'border-transparent bg-muted text-muted-foreground',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
