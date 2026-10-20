import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  Circle,
  GitBranch,
  Loader2,
  Sparkles,
  Trash2,
  Users,
  Zap,
} from 'lucide-react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import {
  clearChecked,
  notify,
  selectActiveRepo,
  selectAssignResults,
  selectCheckedIssues,
  setAssignResults,
  setTab,
} from '../store/uiSlice'
import {
  useApplyBatchAssignMutation,
  useBatchAssignMutation,
  type Assignment,
} from '../store/apiSlice'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { EmptyState } from './ui/empty-state'
import { Input } from './ui/input'
import { Progress } from './ui/progress'
import { priorityMeta } from '../lib/priority'
import { cn, initials } from '../lib/utils'

function AssignmentCard({ assignment }: { assignment: Assignment }) {
  const [open, setOpen] = useState(false)
  const meta = priorityMeta(assignment.priority_tier)
  const signals = Object.entries(assignment.explanation?.signals ?? {})

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'rounded-xl border bg-card/60 transition-colors',
        assignment.at_capacity ? 'border-amber-500/30 bg-amber-500/[0.035]' : 'border-border/80',
      )}
    >
      <div className="flex items-start gap-3 p-4">
        <div className="grid size-8 shrink-0 place-items-center rounded-full border border-border bg-muted text-[10px] font-semibold">
          {initials(assignment.assigned_to)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant={meta.badge}>{assignment.priority_tier}</Badge>
            <span className="font-mono text-[10px] text-muted-foreground">#{assignment.issue_num}</span>
            {assignment.at_capacity && (
              <Badge variant="warning" className="gap-1">
                <AlertTriangle className="size-2.5" />
                At capacity
              </Badge>
            )}
            {assignment.status && (
              <Badge variant={assignment.status === 'assigned' ? 'success' : 'destructive'} className="capitalize">
                {assignment.status}
              </Badge>
            )}
          </div>
          <p className="mt-1.5 truncate text-xs font-medium">{assignment.issue_title}</p>
          <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
            <span className="inline-flex items-center gap-1 text-primary">
              <ArrowRight className="size-3" />
              @{assignment.assigned_to}
            </span>
            <span>·</span>
            <span>{assignment.current_load} open</span>
            {assignment.error && (
              <>
                <span>·</span>
                <span className="text-rose-400">{assignment.error}</span>
              </>
            )}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-base font-semibold tabular-nums">{Math.round(assignment.score * 100)}</div>
          <div className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground">fit</div>
        </div>
      </div>

      <div className="px-4 pb-3">
        <Progress
          value={assignment.score * 100}
          className="h-1"
          indicatorClassName={assignment.at_capacity ? 'bg-amber-400' : 'bg-primary'}
        />
        <button
          type="button"
          onClick={() => setOpen(value => !value)}
          className="mt-2 inline-flex items-center gap-1 text-[10px] text-muted-foreground transition-colors hover:text-foreground"
        >
          {open ? 'Hide evidence' : 'Show evidence'}
          <ChevronDown className={cn('size-3 transition-transform', open && 'rotate-180')} />
        </button>
      </div>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mx-4 mb-4 space-y-2 rounded-lg border border-border/60 bg-background/50 p-3">
              {assignment.explanation?.summary && (
                <p className="text-[11px] italic leading-relaxed text-muted-foreground">
                  {assignment.explanation.summary}
                </p>
              )}
              {signals.slice(0, 6).map(([key, signal]) => (
                <div key={key} className="flex items-center justify-between gap-3 border-b border-border/50 py-1 last:border-0">
                  <span className="text-[10px] capitalize text-muted-foreground">{key.replace(/_/g, ' ')}</span>
                  <span className="text-right text-[10px] text-foreground/80">{(signal as any).label}</span>
                </div>
              ))}
              {assignment.top3?.length > 1 && (
                <div className="pt-1">
                  <p className="mb-1 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Alternatives</p>
                  <div className="flex flex-wrap gap-1">
                    {assignment.top3.slice(1, 4).map(candidate => (
                      <span key={candidate.developer} className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        @{candidate.developer} · {Math.round(candidate.final_score * 100)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export default function BatchAssignment() {
  const dispatch = useAppDispatch()
  const repo = useAppSelector(selectActiveRepo)
  const checked = useAppSelector(selectCheckedIssues)
  const results = useAppSelector(selectAssignResults) as Assignment[]

  const [capacity, setCapacity] = useState(3)
  const [assign, { isLoading }] = useBatchAssignMutation()
  const [apply, { isLoading: isApplying }] = useApplyBatchAssignMutation()

  const atCapacity = results.filter(assignment => assignment.at_capacity).length
  const averageScore = results.length
    ? results.reduce((sum, assignment) => sum + assignment.score, 0) / results.length
    : 0

  async function handleAssign() {
    if (!checked.length) return
    try {
      const response = await assign({ repo, issue_nums: checked, capacity }).unwrap()
      dispatch(setAssignResults(response.assignments))
      dispatch(clearChecked())
      dispatch(notify({ message: `Previewed ${response.total} assignment${response.total === 1 ? '' : 's'}`, type: 'success' }))
    } catch {
      dispatch(notify({ message: 'Assignment failed. Build developer profiles first.', type: 'error' }))
    }
  }

  async function handleApply() {
    if (!results.length) return
    if (!window.confirm(`Apply ${results.length} assignment(s) to GitHub for ${repo}? This changes real issue assignees.`)) {
      return
    }
    try {
      const response = await apply({
        repo,
        issue_nums: results.map(assignment => assignment.issue_num),
        capacity,
        assignments: results,
      }).unwrap()
      dispatch(setAssignResults(response.assignments))
      dispatch(clearChecked())
      const assigned = response.assignments.filter(assignment => assignment.status === 'assigned').length
      dispatch(
        notify({
          message: `Applied ${assigned} GitHub assignment${assigned === 1 ? '' : 's'}`,
          type: 'success',
        }),
      )
    } catch {
      dispatch(notify({ message: 'GitHub assignment failed. Check token permissions.', type: 'error' }))
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Badge variant="outline" className="gap-1.5">
              <Zap className="size-3 text-primary" />
              Workflow
            </Badge>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">Batch assignment</h1>
            <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Preview capacity-aware matches for multiple issues, review the evidence, then apply explicitly to GitHub.
            </p>
          </div>

          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1">
              <span className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                Capacity / developer
              </span>
              <Input
                type="number"
                min={1}
                max={20}
                value={capacity}
                onChange={event => setCapacity(Math.min(20, Math.max(1, Number(event.target.value) || 1)))}
                className="h-9 w-20 bg-background/60 font-mono text-xs"
              />
            </div>
            <Button onClick={handleAssign} disabled={!checked.length || isLoading}>
              {isLoading ? <Loader2 className="animate-spin" /> : <Zap />}
              {isLoading
                ? 'Assigning…'
                : checked.length
                  ? `Assign ${checked.length} issue${checked.length === 1 ? '' : 's'}`
                  : 'Select issues'}
            </Button>
          </div>
        </div>

        {results.length > 0 && (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <Card className="p-4">
                <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  <Users className="size-3.5 text-sky-400" />
                  Assignments
                </div>
                <div className="mt-2 text-2xl font-semibold tabular-nums">{results.length}</div>
              </Card>
              <Card className="p-4">
                <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  <Sparkles className="size-3.5 text-primary" />
                  Average fit
                </div>
                <div className="mt-2 text-2xl font-semibold tabular-nums text-primary">
                  {Math.round(averageScore * 100)}
                </div>
              </Card>
              <Card className="p-4">
                <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  <AlertTriangle className="size-3.5 text-amber-400" />
                  At capacity
                </div>
                <div className="mt-2 text-2xl font-semibold tabular-nums">{atCapacity}</div>
              </Card>
            </div>

            <Card>
              <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
                <div>
                  <CardTitle>Assignment preview</CardTitle>
                  <CardDescription className="mt-1">
                    Nothing has been written to GitHub yet. Review, then apply.
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={() => dispatch(setAssignResults([]))}>
                    <Trash2 />
                    Clear
                  </Button>
                  <Button size="sm" variant="outline" onClick={handleApply} disabled={isApplying}>
                    {isApplying ? <Loader2 className="animate-spin" /> : <GitBranch />}
                    {isApplying ? 'Applying…' : 'Apply to GitHub'}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {results.map(assignment => (
                  <AssignmentCard key={assignment.issue_num} assignment={assignment} />
                ))}
              </CardContent>
            </Card>
          </>
        )}

        {results.length === 0 && (
          <Card>
            <CardContent className="p-6">
              <EmptyState
                icon={<Zap />}
                title="No assignments previewed"
                description="Select issues from the queue, then run a workload-aware batch preview. GitAssign never writes to GitHub without an explicit apply."
                action={
                  <Button size="sm" onClick={() => dispatch(setTab('issues'))}>
                    <ArrowRight />
                    Choose issues
                  </Button>
                }
              />
              <div className="mx-auto mt-2 grid max-w-3xl gap-3 sm:grid-cols-3">
                {[
                  { icon: Circle, title: '1 · Select', text: 'Pick issues in the queue using checkboxes.' },
                  { icon: Zap, title: '2 · Preview', text: 'Review ranked developers, workload, and evidence.' },
                  { icon: CheckCircle2, title: '3 · Apply', text: 'Explicitly write assignees to GitHub with a token.' },
                ].map(step => {
                  const Icon = step.icon
                  return (
                    <div key={step.title} className="rounded-lg border border-border/60 bg-background/40 p-3">
                      <Icon className="size-4 text-primary" />
                      <p className="mt-2 text-xs font-medium">{step.title}</p>
                      <p className="mt-1 text-[10px] leading-relaxed text-muted-foreground">{step.text}</p>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
