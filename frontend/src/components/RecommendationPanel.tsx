import { useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
  AlertCircle,
  ArrowLeft,
  Boxes,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Clock3,
  ExternalLink,
  FileCode2,
  FileText,
  Gauge,
  History,
  MousePointerClick,
  Sparkles,
  Trophy,
  UserRound,
  Users,
} from 'lucide-react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { selectActiveRepo, selectSelectedIssue, selectIssue, setTab } from '../store/uiSlice'
import {
  useGetRecommendationsQuery,
  type Recommendation,
  type SignalDetail,
} from '../store/apiSlice'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { EmptyState } from './ui/empty-state'
import { Progress } from './ui/progress'
import { Skeleton } from './ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from './ui/tooltip'
import { priorityMeta } from '../lib/priority'
import { cn, formatDate, initials } from '../lib/utils'

const SIGNAL_META: Record<
  string,
  { label: string; icon: typeof FileText; bar: string; text: string }
> = {
  text_similarity: { label: 'Text similarity', icon: FileText, bar: 'bg-emerald-400', text: 'text-emerald-400' },
  past_issue_similarity: { label: 'Historical match', icon: History, bar: 'bg-sky-400', text: 'text-sky-400' },
  component_overlap: { label: 'Components', icon: Boxes, bar: 'bg-violet-400', text: 'text-violet-400' },
  file_affinity: { label: 'File affinity', icon: FileCode2, bar: 'bg-amber-400', text: 'text-amber-400' },
  recency: { label: 'Recency', icon: Clock3, bar: 'bg-cyan-400', text: 'text-cyan-400' },
  workload: { label: 'Workload', icon: Gauge, bar: 'bg-rose-400', text: 'text-rose-400' },
  domain: { label: 'Domain fit', icon: Sparkles, bar: 'bg-fuchsia-400', text: 'text-fuchsia-400' },
}

function Disclosure({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          className="overflow-hidden"
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function DeveloperCard({ rec, rank }: { rec: Recommendation; rank: number }) {
  const explanation = rec.explanation
  const signals = Object.entries(explanation?.signals ?? {})
  const score = Math.round(rec.final_score * 100)
  const isTop = rank === 1

  return (
    <motion.article
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(rank * 0.04, 0.2) }}
      className={cn(
        'rounded-xl border p-4 transition-colors',
        isTop
          ? 'border-primary/30 bg-primary/[0.045] shadow-glow'
          : 'border-border/80 bg-card/60 hover:border-border hover:bg-accent/20',
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            'relative grid size-9 shrink-0 place-items-center rounded-full border text-[11px] font-semibold',
            isTop
              ? 'border-primary/40 bg-primary/15 text-primary'
              : 'border-border bg-muted text-foreground',
          )}
        >
          {initials(rec.developer)}
          {isTop && (
            <span className="absolute -right-1 -top-1 grid size-4 place-items-center rounded-full border border-primary/40 bg-background">
              <Trophy className="size-2.5 text-primary" />
            </span>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold">@{rec.developer}</span>
            {isTop && <Badge variant="default">Best match</Badge>}
            <span className="ml-auto shrink-0 font-mono text-[10px] text-muted-foreground">#{rank}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-3 text-[10px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <CheckCircle2 className="size-3 text-emerald-400" />
              {explanation?.resolved_total ?? 0} resolved
            </span>
            <span className="inline-flex items-center gap-1">
              <UserRound className="size-3 text-sky-400" />
              {explanation?.open_issues ?? 0} open
            </span>
            {(rec.domains ?? []).slice(0, 3).map(domain => (
              <Badge key={domain.name} variant="outline" className="text-[9px]">{domain.name}</Badge>
            ))}
          </div>
        </div>

        <div className="shrink-0 text-right">
          <div className={cn('text-xl font-semibold tabular-nums tracking-tight', isTop ? 'text-primary' : 'text-foreground')}>
            {score}
          </div>
          <div className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground">fit score</div>
        </div>
      </div>

      <Progress
        value={score}
        className="mt-3 h-1.5"
        indicatorClassName={isTop ? 'bg-primary' : 'bg-foreground/35'}
      />

      {explanation?.summary && (
        <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">{explanation.summary}</p>
      )}

      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {signals.slice(0, 6).map(([key, signal]) => {
          const detail = signal as SignalDetail
          const meta = SIGNAL_META[key] ?? {
            label: key.replace(/_/g, ' '),
            icon: Sparkles,
            bar: 'bg-foreground/40',
            text: 'text-muted-foreground',
          }
          const Icon = meta.icon
          return (
            <Tooltip key={key}>
              <TooltipTrigger asChild>
                <div className="cursor-help rounded-lg border border-border/60 bg-background/40 p-2">
                  <div className="flex items-center gap-1.5">
                    <Icon className={cn('size-3', meta.text)} />
                    <span className="truncate text-[10px] text-muted-foreground">{meta.label}</span>
                    <span className="ml-auto font-mono text-[10px] tabular-nums text-foreground">
                      {(detail.value * 100).toFixed(0)}%
                    </span>
                  </div>
                  <Progress value={detail.value * 100} className="mt-1.5 h-1" indicatorClassName={meta.bar} />
                </div>
              </TooltipTrigger>
              <TooltipContent>{detail.detail}</TooltipContent>
            </Tooltip>
          )
        })}
      </div>
    </motion.article>
  )
}

export default function RecommendationPanel() {
  const dispatch = useAppDispatch()
  const repo = useAppSelector(selectActiveRepo)
  const issueNum = useAppSelector(selectSelectedIssue)
  const [showBody, setShowBody] = useState(false)
  const [showFactors, setShowFactors] = useState(false)

  const { data, isLoading, error } = useGetRecommendationsQuery(
    { repo, issueNum: issueNum! },
    { skip: !repo || issueNum === null },
  )

  if (!issueNum) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center bg-background/30 p-6">
        <EmptyState
          icon={<MousePointerClick />}
          title="Select an issue to inspect matches"
          description="GitAssign ranks developers using text similarity, historical fixes, components, file affinity, recency, and workload."
        />
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="space-y-3 border-b border-border/70 p-4">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
        <div className="space-y-3 p-4">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-40" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center p-6">
        <EmptyState
          icon={<AlertCircle />}
          title="Recommendations unavailable"
          description="Build developer profiles for this repository, then select the issue again."
          action={
            <Button size="sm" variant="outline" onClick={() => dispatch(setTab('developers'))}>
              <Users />
              Open developers
            </Button>
          }
        />
      </div>
    )
  }

  const recommendations = data?.recommendations ?? []
  const priority = data?.priority
  const classification = data?.classification
  const priorityStyle = priorityMeta(priority?.tier)
  const githubUrl = `https://github.com/${repo}/issues/${issueNum}`

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-background/20">
      <div className="shrink-0 border-b border-border/70 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="ghost"
            size="icon-sm"
            className="lg:hidden"
            onClick={() => dispatch(selectIssue(null))}
            aria-label="Back to issue queue"
          >
            <ArrowLeft />
          </Button>
          <span className="font-mono text-xs text-muted-foreground">#{issueNum}</span>
          {priority && <Badge variant={priorityStyle.badge}>{priority.tier}</Badge>}
          {data?.issue_state && (
            <Badge variant={data.issue_state === 'open' ? 'success' : 'muted'} className="capitalize">
              {data.issue_state}
            </Badge>
          )}
          {classification && <Badge variant="outline" className="capitalize">{classification.kind}</Badge>}
          {classification && <Badge variant="muted" className="capitalize">{classification.severity}</Badge>}
          {priority && (
            <span className="font-mono text-[10px] text-muted-foreground">priority score {priority.score}</span>
          )}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon-sm" className="ml-auto" asChild>
                <a href={githubUrl} target="_blank" rel="noreferrer" aria-label="Open issue on GitHub">
                  <ExternalLink />
                </a>
              </Button>
            </TooltipTrigger>
            <TooltipContent>Open on GitHub</TooltipContent>
          </Tooltip>
        </div>

        <h2 className="mt-2 text-base font-semibold leading-snug tracking-tight">{data?.issue_title}</h2>

        {classification?.domains?.length ? (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {classification.domains.map(domain => <Badge key={domain.name} variant="outline">{domain.name}</Badge>)}
            {classification.summary && <span className="ml-1 text-[10px] text-muted-foreground">{classification.summary}</span>}
          </div>
        ) : null}

        {data?.issue_labels && data.issue_labels.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {data.issue_labels.slice(0, 6).map((label: string) => (
              <span
                key={label}
                className="rounded border border-border/70 bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground"
              >
                {label}
              </span>
            ))}
          </div>
        )}

        <div className="mt-2.5 flex flex-wrap items-center gap-3 text-[10px] text-muted-foreground">
          {data?.issue_author && (
            <span className="inline-flex items-center gap-1">
              <UserRound className="size-3" />
              @{data.issue_author}
            </span>
          )}
          {data?.issue_created && (
            <span className="inline-flex items-center gap-1">
              <CalendarDays className="size-3" />
              {formatDate(data.issue_created)}
            </span>
          )}
          {data?.issue_closed && data.issue_state === 'closed' && (
            <span>closed {formatDate(data.issue_closed)}</span>
          )}
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {priority?.factors && priority.factors.length > 0 && (
            <Button variant="outline" size="sm" onClick={() => setShowFactors(value => !value)}>
              Priority factors
              <ChevronDown className={cn('transition-transform', showFactors && 'rotate-180')} />
            </Button>
          )}
          {data?.issue_body && (
            <Button variant="outline" size="sm" onClick={() => setShowBody(value => !value)}>
              Issue details
              <ChevronDown className={cn('transition-transform', showBody && 'rotate-180')} />
            </Button>
          )}
        </div>

        <Disclosure open={showFactors}>
          <div className="mt-2 rounded-lg border border-border/70 bg-muted/40 p-3">
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Contributing priority factors
            </p>
            <ul className="space-y-1">
              {priority?.factors?.map((factor: string) => (
                <li key={factor} className="flex items-start gap-1.5 text-[11px] text-foreground/85">
                  <span className={cn('mt-1.5 size-1 shrink-0 rounded-full', priorityStyle.dot)} />
                  {factor}
                </li>
              ))}
            </ul>
          </div>
        </Disclosure>

        <Disclosure open={showBody}>
          <div className="mt-2 rounded-lg border border-border/70 bg-muted/40 p-3">
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Issue description
            </p>
            <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap font-sans text-[11px] leading-relaxed text-foreground/80">
              {data?.issue_body}
            </pre>
          </div>
        </Disclosure>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <div className="mb-3 flex items-end justify-between gap-2">
          <div>
            <h3 className="flex items-center gap-1.5 text-sm font-semibold">
              <Sparkles className="size-3.5 text-primary" />
              Recommended developers
            </h3>
            <p className="mt-0.5 text-[10px] text-muted-foreground">
              Ranked by weighted evidence and current workload
            </p>
          </div>
          <Badge variant="outline" className="font-mono">
            Top {recommendations.length}
          </Badge>
        </div>

        {recommendations.length === 0 ? (
          <EmptyState
            icon={<Users />}
            title="No recommendations yet"
            description="Build developer profiles from resolved issues and commit history to generate matches."
            action={
              <Button size="sm" variant="outline" onClick={() => dispatch(setTab('developers'))}>
                <Users />
                Build profiles
              </Button>
            }
          />
        ) : (
          <div className="space-y-3">
            {recommendations.map((rec, index) => (
              <DeveloperCard key={rec.developer} rec={rec} rank={index + 1} />
            ))}
            <p className="flex items-center justify-center gap-1.5 pt-1 text-[10px] text-muted-foreground">
              <Sparkles className="size-3" />
              Preview only — apply assignments explicitly from Batch Assign
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
