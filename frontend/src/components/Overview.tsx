import { motion } from 'motion/react'
import {
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  Circle,
  CircleDot,
  FolderGit2,
  Inbox,
  ListChecks,
  Radar,
  Users,
  Zap,
} from 'lucide-react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { selectActiveRepo, selectIssue, setTab } from '../store/uiSlice'
import {
  useGetDevelopersQuery,
  useGetIssuesQuery,
  useGetMetricsQuery,
  type AblationResult,
} from '../store/apiSlice'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { EmptyState } from './ui/empty-state'
import { Progress } from './ui/progress'
import { Skeleton } from './ui/skeleton'
import { StatCard } from './ui/stat-card'
import { PRIORITY_META, PRIORITY_ORDER, priorityMeta } from '../lib/priority'
import { cn, initials } from '../lib/utils'

export default function Overview() {
  const dispatch = useAppDispatch()
  const repo = useAppSelector(selectActiveRepo)

  const { data: issuesData, isLoading: issuesLoading } = useGetIssuesQuery(
    { repo, state: 'all' },
    { skip: !repo, pollingInterval: 60_000 },
  )
  const { data: developerData } = useGetDevelopersQuery(repo, { skip: !repo })
  const { data: metricsData } = useGetMetricsQuery(repo, { skip: !repo })

  const issues = issuesData?.issues ?? []
  const developers = developerData?.developers ?? []
  const results = Object.values(metricsData?.results ?? {}) as AblationResult[]

  const openIssues = issues.filter(issue => issue.state === 'open')
  const critical = issues.filter(issue => issue.priority?.tier === 'Critical')
  const high = issues.filter(issue => issue.priority?.tier === 'High')
  const needsAttention = [...issues]
    .filter(issue => ['Critical', 'High'].includes(issue.priority?.tier ?? ''))
    .slice(0, 6)
  const topDevelopers = developers.slice(0, 5)
  const maxResolved = Math.max(...topDevelopers.map(dev => dev.resolved_count ?? 0), 1)
  const bestResult = [...results].sort((a, b) => b.top5 - a.top5)[0]
  const maxTierCount = Math.max(...PRIORITY_ORDER.map(tier => issues.filter(i => i.priority?.tier === tier).length), 1)

  const workflow = [
    { label: 'Repository data loaded', done: issues.length > 0, hint: `${issues.length.toLocaleString()} issues` },
    { label: 'Developer profiles built', done: developers.length > 0, hint: `${developers.length} profiles` },
    { label: 'Evaluation completed', done: results.length > 0, hint: results.length ? `${results.length} configs` : 'Not run' },
    { label: 'Open queue triaged', done: issues.length > 0 && openIssues.length === 0, hint: `${openIssues.length} open` },
  ]

  function openIssue(number: number) {
    dispatch(selectIssue(number))
    dispatch(setTab('issues'))
  }

  if (issuesLoading) {
    return (
      <div className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-28" />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-72" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[1500px] space-y-5 p-4 sm:p-6">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"
        >
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="gap-1.5 font-mono">
                <FolderGit2 className="size-3" />
                {repo}
              </Badge>
              <Badge variant="success" className="gap-1.5">
                <span className="size-1.5 rounded-full bg-emerald-400" />
                Workspace ready
              </Badge>
            </div>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight">Repository overview</h1>
            <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Prioritize incoming issues, inspect explainable developer matches, and keep workload balanced — with a
              maintainer in control of every assignment.
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button variant="outline" onClick={() => dispatch(setTab('developers'))}>
              <Users />
              Profiles
            </Button>
            <Button onClick={() => dispatch(setTab('issues'))}>
              <Inbox />
              Open queue
            </Button>
          </div>
        </motion.div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Issues in queue"
            value={issues.length.toLocaleString()}
            hint={`${openIssues.length.toLocaleString()} open · ${(issues.length - openIssues.length).toLocaleString()} closed in view`}
            icon={<Inbox />}
            accent="sky"
            delay={0}
          />
          <StatCard
            label="Critical priority"
            value={critical.length.toLocaleString()}
            hint={`${high.length} high-priority issues`}
            icon={<Zap />}
            accent="rose"
            delay={0.05}
          />
          <StatCard
            label="Developers"
            value={developers.length.toLocaleString()}
            hint={developers.length ? 'Expertise profiles available' : 'Build profiles to enable matches'}
            icon={<Users />}
            accent="violet"
            delay={0.1}
          />
          <StatCard
            label="Best Top-5"
            value={bestResult ? `${bestResult.top5}%` : '—'}
            hint={bestResult ? `Config ${bestResult.config} · ${bestResult.n} test issues` : 'Run an evaluation to measure coverage'}
            icon={<BarChart3 />}
            accent="emerald"
            delay={0.15}
          />
        </div>

        <div className="grid gap-4 lg:grid-cols-12">
          <Card className="lg:col-span-4">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle>Priority distribution</CardTitle>
                <Badge variant="muted">{issues.length.toLocaleString()}</Badge>
              </div>
              <CardDescription>Rule-based triage across the loaded issue set</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3.5">
              {PRIORITY_ORDER.map(tier => {
                const count = issues.filter(issue => (issue.priority?.tier ?? 'Medium') === tier).length
                const meta = PRIORITY_META[tier]
                return (
                  <div key={tier} className="space-y-1.5">
                    <div className="flex items-center gap-2 text-xs">
                      <span className={cn('size-1.5 rounded-full', meta.dot)} />
                      <span className="font-medium">{tier}</span>
                      <span className="ml-auto font-mono text-[11px] text-muted-foreground">
                        {count.toLocaleString()}
                      </span>
                    </div>
                    <Progress
                      value={(count / maxTierCount) * 100}
                      className="h-1.5"
                      indicatorClassName={cn('transition-all', meta.bar)}
                    />
                  </div>
                )
              })}
              <div className="flex items-center gap-2 pt-1 text-[11px] text-muted-foreground">
                <Radar className="size-3.5 text-primary" />
                Factor evidence available for every issue
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-4">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle>Most experienced</CardTitle>
                <Button variant="ghost" size="sm" onClick={() => dispatch(setTab('developers'))}>
                  View all
                  <ArrowUpRight />
                </Button>
              </div>
              <CardDescription>Ranked by resolved issues in this repository</CardDescription>
            </CardHeader>
            <CardContent className="space-y-1">
              {topDevelopers.length === 0 ? (
                <EmptyState
                  compact
                  icon={<Users />}
                  title="No profiles yet"
                  description="Open Developers and build profiles from repository history."
                />
              ) : (
                topDevelopers.map((dev, index) => (
                  <div
                    key={dev.username}
                    className="flex items-center gap-3 rounded-lg px-1 py-2 transition-colors hover:bg-accent/40"
                  >
                    <span className="w-4 shrink-0 text-center font-mono text-[10px] text-muted-foreground">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <div className="grid size-7 shrink-0 place-items-center rounded-full border border-border bg-muted text-[10px] font-semibold">
                      {initials(dev.username)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-xs font-medium">@{dev.username}</span>
                        <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                          {dev.resolved_count} resolved
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-2">
                        <Progress value={(dev.resolved_count / maxResolved) * 100} className="h-1" />
                        <span className="shrink-0 text-[10px] text-muted-foreground">{dev.open_issues} open</span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card className="lg:col-span-4">
            <CardHeader className="pb-3">
              <CardTitle>Workspace readiness</CardTitle>
              <CardDescription>Complete these steps to unlock the full workflow</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {workflow.map(item => (
                <div key={item.label} className="flex items-center gap-2.5 rounded-lg border border-border/60 bg-background/40 px-2.5 py-2">
                  {item.done ? (
                    <CheckCircle2 className="size-4 shrink-0 text-emerald-400" />
                  ) : (
                    <Circle className="size-4 shrink-0 text-muted-foreground/50" />
                  )}
                  <span className={cn('flex-1 text-[11px]', item.done ? 'text-foreground' : 'text-muted-foreground')}>
                    {item.label}
                  </span>
                  <span className="font-mono text-[10px] text-muted-foreground">{item.hint}</span>
                </div>
              ))}
              <Button
                variant="secondary"
                size="sm"
                className="mt-1 w-full"
                onClick={() => dispatch(setTab(bestResult ? 'issues' : 'metrics'))}
              >
                <ListChecks />
                {bestResult ? 'Continue triage' : 'Run evaluation'}
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-12">
          <Card className="lg:col-span-7">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Needs attention</CardTitle>
                  <CardDescription className="mt-1">Critical and high-priority issues in the queue</CardDescription>
                </div>
                <Button variant="ghost" size="sm" onClick={() => dispatch(setTab('issues'))}>
                  Full queue
                  <ArrowUpRight />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-2">
              {needsAttention.length === 0 ? (
                <EmptyState
                  compact
                  icon={<CircleDot />}
                  title="No urgent issues"
                  description="Critical and high-priority issues will surface here."
                />
              ) : (
                <div className="divide-y divide-border/60">
                  {needsAttention.map(issue => {
                    const meta = priorityMeta(issue.priority?.tier)
                    return (
                      <button
                        key={issue.number}
                        type="button"
                        onClick={() => openIssue(issue.number)}
                        className="group flex w-full items-start gap-3 py-2.5 text-left"
                      >
                        <Badge variant={meta.badge} className="mt-0.5 shrink-0">
                          {issue.priority?.tier ?? 'Medium'}
                        </Badge>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs font-medium text-foreground group-hover:text-primary">
                            <span className="mr-1.5 font-mono text-[10px] text-muted-foreground">#{issue.number}</span>
                            {issue.title}
                          </p>
                          <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
                            {issue.labels?.slice(0, 2).map(label => (
                              <span key={label} className="rounded bg-muted px-1.5 py-0.5">
                                {label}
                              </span>
                            ))}
                            <span className="capitalize">{issue.state}</span>
                          </div>
                        </div>
                        <ArrowUpRight className="mt-1 size-3.5 shrink-0 text-muted-foreground/40 transition-colors group-hover:text-primary" />
                      </button>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="lg:col-span-5">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle>Evaluation snapshot</CardTitle>
                {bestResult && <Badge variant="success">Config {bestResult.config}</Badge>}
              </div>
              <CardDescription>Temporal replay against held-out issues</CardDescription>
            </CardHeader>
            <CardContent>
              {bestResult ? (
                <div className="space-y-4">
                  <div className="flex items-end gap-2">
                    <span className="text-4xl font-semibold tracking-tight text-primary">{bestResult.top5}%</span>
                    <span className="pb-1 text-xs text-muted-foreground">Top-5 accuracy</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { label: 'Top-1', value: `${bestResult.top1}%` },
                      { label: 'Top-3', value: `${bestResult.top3}%` },
                      { label: 'MRR', value: bestResult.mrr.toFixed(3) },
                    ].map(metric => (
                      <div key={metric.label} className="rounded-lg border border-border/70 bg-background/40 p-2 text-center">
                        <div className="text-sm font-semibold tabular-nums">{metric.value}</div>
                        <div className="text-[10px] text-muted-foreground">{metric.label}</div>
                      </div>
                    ))}
                  </div>
                  <p className="text-[11px] leading-relaxed text-muted-foreground">
                    {bestResult.config_name} · evaluated on {bestResult.n} issues. Compare all five ablation
                    configurations in Evaluation.
                  </p>
                  <Button variant="outline" size="sm" className="w-full" onClick={() => dispatch(setTab('metrics'))}>
                    <BarChart3 />
                    Open evaluation
                  </Button>
                </div>
              ) : (
                <EmptyState
                  compact
                  icon={<BarChart3 />}
                  title="No evaluation results"
                  description="Run the ablation study to measure Top-K accuracy against the text-only baseline."
                  action={
                    <Button size="sm" onClick={() => dispatch(setTab('metrics'))}>
                      <BarChart3 />
                      Run evaluation
                    </Button>
                  }
                />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
