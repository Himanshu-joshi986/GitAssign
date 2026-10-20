import { motion } from 'motion/react'
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  GitBranch,
  Loader2,
  Menu,
  Radio,
} from 'lucide-react'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Separator } from '../ui/separator'
import { cn } from '../../lib/utils'
import { tabDefinition, type TabId } from '../../lib/navigation'
import type { PipelineState } from './sidebar'

interface TopbarProps {
  activeRepo: string
  activeTab: TabId
  pipeline?: PipelineState
  onMenu: () => void
}

const STATUS_META = {
  idle: { label: 'Idle', className: 'text-muted-foreground', icon: Radio },
  queued: { label: 'Queued', className: 'text-amber-400', icon: Loader2 },
  running: { label: 'Syncing', className: 'text-amber-400', icon: Loader2 },
  completed: { label: 'Synced', className: 'text-emerald-400', icon: CheckCircle2 },
  failed: { label: 'Sync failed', className: 'text-rose-400', icon: AlertCircle },
}

export function Topbar({ activeRepo, activeTab, pipeline, onMenu }: TopbarProps) {
  const tab = tabDefinition(activeTab)
  const status = STATUS_META[pipeline?.status ?? 'idle']
  const StatusIcon = status.icon
  const spinning = pipeline?.status === 'queued' || pipeline?.status === 'running'

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b border-border/70 bg-background/80 px-3 backdrop-blur-xl sm:px-4 lg:px-6">
      <Button variant="ghost" size="icon-sm" className="lg:hidden" onClick={onMenu} aria-label="Open navigation">
        <Menu />
      </Button>

      <nav className="flex min-w-0 items-center gap-1.5 text-xs" aria-label="Breadcrumb">
        <span className="hidden text-muted-foreground sm:inline">Workspace</span>
        <ChevronRight className="hidden size-3 text-muted-foreground/50 sm:inline" />
        {activeRepo ? (
          <>
            <span className="flex min-w-0 items-center gap-1.5 font-mono text-[11px] text-foreground">
              <GitBranch className="size-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate">{activeRepo}</span>
            </span>
            <ChevronRight className="size-3 shrink-0 text-muted-foreground/50" />
          </>
        ) : null}
        <span className="flex items-center gap-1.5 font-medium text-foreground">
          <tab.icon className="size-3.5 text-primary" />
          {tab.label}
        </span>
      </nav>

      <div className="ml-auto flex items-center gap-2">
        {pipeline && pipeline.status !== 'idle' && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="hidden sm:block"
          >
            <Badge variant="muted" className={cn('gap-1.5 border-border/70', status.className)}>
              <StatusIcon className={cn('size-3', spinning && 'animate-spin')} />
              {status.label}
            </Badge>
          </motion.div>
        )}
        <Separator orientation="vertical" className="hidden h-5 sm:block" />
        <Badge variant="outline" className="hidden gap-1.5 md:inline-flex">
          <span className="size-1.5 rounded-full bg-emerald-400" />
          Maintainer preview
        </Badge>
      </div>
    </header>
  )
}
