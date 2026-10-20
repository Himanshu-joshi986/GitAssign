import { motion } from 'motion/react'
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Database,
  Download,
  ExternalLink,
  GitBranch,
  Loader2,
  Minus,
  Plus,
  Trash2,
  X,
} from 'lucide-react'
import { Brand } from '../brand'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Progress } from '../ui/progress'
import { Separator } from '../ui/separator'
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip'
import { cn } from '../../lib/utils'
import { TABS, type TabId } from '../../lib/navigation'

export interface RepoSummary {
  repo: string
  issue_count: number
}

export interface PipelineState {
  status: 'idle' | 'queued' | 'running' | 'completed' | 'failed'
  message: string
  issues?: number
  contributors?: number
}

interface SidebarProps {
  activeRepo: string
  activeTab: TabId
  repos: RepoSummary[]
  pipeline?: PipelineState
  repoInput: string
  onRepoInputChange: (value: string) => void
  maxPages: number
  onMaxPagesChange: (value: number) => void
  onLoad: () => void
  onIngest: () => void
  onSelectRepo: (repo: string) => void
  onRemove: (repo: string) => void
  onNavigate: (tab: TabId) => void
  ingesting: boolean
  onClose?: () => void
}

const PIPELINE_META = {
  running: {
    icon: Loader2,
    className: 'text-amber-300',
    badge: 'warning' as const,
    label: 'Running',
  },
  queued: {
    icon: Loader2,
    className: 'text-amber-300',
    badge: 'warning' as const,
    label: 'Queued',
  },
  completed: {
    icon: CheckCircle2,
    className: 'text-emerald-400',
    badge: 'success' as const,
    label: 'Completed',
  },
  failed: {
    icon: AlertCircle,
    className: 'text-rose-400',
    badge: 'destructive' as const,
    label: 'Failed',
  },
  idle: {
    icon: CheckCircle2,
    className: 'text-muted-foreground',
    badge: 'muted' as const,
    label: 'Idle',
  },
}

function PipelineCard({ pipeline }: { pipeline: PipelineState }) {
  const meta = PIPELINE_META[pipeline.status]
  const Icon = meta.icon
  const spinning = pipeline.status === 'running' || pipeline.status === 'queued'

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-border bg-background/50 p-3"
    >
      <div className="flex items-center gap-2">
        <Icon className={cn('size-3.5', meta.className, spinning && 'animate-spin')} />
        <span className="text-xs font-medium">Ingestion pipeline</span>
        <Badge variant={meta.badge} className="ml-auto">
          {meta.label}
        </Badge>
      </div>
      <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">{pipeline.message}</p>
      {spinning && <Progress value={62} className="mt-2 h-1" indicatorClassName="animate-pulse" />}
      {(pipeline.issues !== undefined || pipeline.contributors !== undefined) && (
        <div className="mt-2 flex items-center gap-3 text-[10px] text-muted-foreground">
          {pipeline.issues !== undefined && <span>{pipeline.issues.toLocaleString()} issues</span>}
          {pipeline.contributors !== undefined && <span>{pipeline.contributors} contributors</span>}
        </div>
      )}
    </motion.div>
  )
}

export function Sidebar({
  activeRepo,
  activeTab,
  repos,
  pipeline,
  repoInput,
  onRepoInputChange,
  maxPages,
  onMaxPagesChange,
  onLoad,
  onIngest,
  onSelectRepo,
  onRemove,
  onNavigate,
  ingesting,
  onClose,
}: SidebarProps) {
  const activeLayoutId = onClose ? 'sidebar-active-mobile' : 'sidebar-active'
  return (
    <aside className="flex h-full w-[278px] flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex h-16 shrink-0 items-center justify-between px-4">
        <Brand />
        {onClose && (
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close navigation">
            <X />
          </Button>
        )}
      </div>

      <div className="no-scrollbar flex-1 overflow-y-auto px-3 pb-4">
        <div className="space-y-3 rounded-xl border border-sidebar-border bg-background/40 p-3">
          <div className="flex items-center justify-between">
            <Label>Repository</Label>
            <span className="text-[10px] text-muted-foreground">owner/repo</span>
          </div>

          <div className="relative">
            <GitBranch className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              value={repoInput}
              onChange={event => onRepoInputChange(event.target.value)}
              onKeyDown={event => event.key === 'Enter' && onLoad()}
              placeholder="pallets/click"
              aria-label="Repository slug"
              className="h-9 bg-background/70 pl-8 font-mono text-xs"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={onLoad}
              disabled={!repoInput.trim()}
              className="justify-center"
            >
              <Database />
              Load
            </Button>
            <Button
              size="sm"
              onClick={onIngest}
              disabled={ingesting || !repoInput.trim()}
              className="justify-center"
            >
              {ingesting ? <Loader2 className="animate-spin" /> : <Download />}
              Ingest
            </Button>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border/70 bg-background/50 px-2.5 py-1.5">
            <div>
              <p className="text-[11px] font-medium">Fetch depth</p>
              <p className="text-[10px] text-muted-foreground">100 items per page</p>
            </div>
            <div className="flex items-center gap-0.5">
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => onMaxPagesChange(Math.max(1, maxPages - 1))}
                aria-label="Decrease pages"
              >
                <Minus />
              </Button>
              <span className="w-6 text-center font-mono text-xs tabular-nums">{maxPages}</span>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => onMaxPagesChange(Math.min(50, maxPages + 1))}
                aria-label="Increase pages"
              >
                <Plus />
              </Button>
            </div>
          </div>
        </div>

        {pipeline && pipeline.status !== 'idle' && (
          <div className="mt-3">
            <PipelineCard pipeline={pipeline} />
          </div>
        )}

        <nav className="mt-4 space-y-0.5" aria-label="Workspace">
          <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground/70">
            Workspace
          </p>
          {TABS.map(tab => {
            const Icon = tab.icon
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onNavigate(tab.id)}
                className={cn(
                  'relative flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40',
                  active
                    ? 'text-foreground'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-foreground',
                )}
              >
                {active && (
                  <motion.span
                    layoutId={activeLayoutId}
                    className="absolute inset-0 rounded-lg border border-primary/20 bg-primary/10"
                    transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                  />
                )}
                <Icon className={cn('relative size-4', active ? 'text-primary' : 'text-muted-foreground')} />
                <span className="relative font-medium">{tab.label}</span>
                {active && <ChevronRight className="relative ml-auto size-3.5 text-primary/70" />}
              </button>
            )
          })}
        </nav>

        <div className="mt-4">
          <div className="flex items-center justify-between px-2 pb-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground/70">
              Repositories
            </p>
            <Badge variant="muted">{repos.length}</Badge>
          </div>
          <div className="space-y-0.5">
            {repos.length === 0 && (
              <p className="px-2 py-3 text-[11px] leading-relaxed text-muted-foreground">
                No repositories loaded yet. Load a dataset or ingest a GitHub repository.
              </p>
            )}
            {repos.map(repo => {
              const active = activeRepo === repo.repo
              return (
                <div
                  key={repo.repo}
                  className={cn(
                    'group flex items-center gap-1 rounded-lg border px-1 transition-colors',
                    active
                      ? 'border-primary/20 bg-primary/10'
                      : 'border-transparent hover:border-border hover:bg-sidebar-accent',
                  )}
                >
                  <button
                    type="button"
                    onClick={() => onSelectRepo(repo.repo)}
                    className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-1.5 py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
                  >
                    <span
                      className={cn(
                        'size-1.5 shrink-0 rounded-full',
                        active ? 'bg-primary shadow-[0_0_8px_hsl(var(--primary))]' : 'bg-muted-foreground/30',
                      )}
                    />
                    <GitBranch className="size-3.5 shrink-0 text-muted-foreground" />
                    <span className={cn('truncate text-xs', active ? 'text-foreground' : 'text-sidebar-foreground')}>
                      {repo.repo}
                    </span>
                    <span className="ml-auto shrink-0 font-mono text-[10px] text-muted-foreground">
                      {repo.issue_count.toLocaleString()}
                    </span>
                  </button>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        className="opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                        onClick={() => onRemove(repo.repo)}
                        aria-label={`Remove ${repo.repo}`}
                      >
                        <Trash2 className="text-muted-foreground hover:text-rose-400" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Remove local data</TooltipContent>
                  </Tooltip>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <div className="shrink-0 border-t border-sidebar-border p-3">
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2 rounded-lg px-2 py-2 text-[11px] text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground"
        >
          <BookOpen className="size-3.5" />
          API documentation
          <ExternalLink className="ml-auto size-3" />
        </a>
        <Separator className="my-2" />
        <div className="flex items-center gap-2 px-2">
          <span className="relative flex size-2">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-40" />
            <span className="relative inline-flex size-2 rounded-full bg-emerald-400" />
          </span>
          <span className="text-[10px] text-muted-foreground">Decision support · local workspace</span>
        </div>
      </div>
    </aside>
  )
}
