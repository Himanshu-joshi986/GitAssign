import { useState } from 'react'
import { motion } from 'motion/react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { BarChart3, CalendarDays, Loader2, Play, RefreshCw, Trophy } from 'lucide-react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { notify, selectActiveRepo } from '../store/uiSlice'
import { useGetMetricsQuery, useRunEvaluationMutation, type AblationResult } from '../store/apiSlice'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { EmptyState } from './ui/empty-state'
import { Input } from './ui/input'
import { Progress } from './ui/progress'
import { Skeleton } from './ui/skeleton'
import { StatCard } from './ui/stat-card'
import { cn } from '../lib/utils'

const SERIES = [
  { key: 'Top-1', color: '#34d399' },
  { key: 'Top-3', color: '#38bdf8' },
  { key: 'Top-5', color: '#a78bfa' },
  { key: 'MRR × 100', color: '#fbbf24' },
]

export default function MetricsView() {
  const dispatch = useAppDispatch()
  const repo = useAppSelector(selectActiveRepo)
  const { data, isLoading, isFetching, refetch } = useGetMetricsQuery(repo, { pollingInterval: 10_000 })
  const [runEvaluation, { isLoading: running }] = useRunEvaluationMutation()

  const [trainBefore, setTrainBefore] = useState('2010-01-01')
  const [testAfter, setTestAfter] = useState('2010-01-01')
  const [maxIssues, setMaxIssues] = useState(200)

  const results = Object.values(data?.results ?? {}) as AblationResult[]
  const best = [...results].sort((a, b) => b.top5 - a.top5)[0]
  const chartData = results.map(result => ({
    name: result.config,
    label: result.config_name,
    'Top-1': result.top1,
    'Top-3': result.top3,
    'Top-5': result.top5,
    'MRR × 100': +(result.mrr * 100).toFixed(1),
  }))

  async function handleRun() {
    try {
      await runEvaluation({ repo, train_before: trainBefore, test_after: testAfter, max_issues: maxIssues }).unwrap()
      dispatch(notify({ message: 'Ablation started. Results will appear when the run completes.', type: 'info' }))
      window.setTimeout(() => refetch(), 3000)
    } catch {
      dispatch(notify({ message: 'Could not start the ablation run.', type: 'error' }))
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Badge variant="outline" className="gap-1.5">
              <BarChart3 className="size-3 text-primary" />
              Evaluation
            </Badge>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">Ablation study</h1>
            <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Chronological replay against held-out issues. Compare progressively richer signal configurations with a
              text-only baseline.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isFetching && <RefreshCw className="size-3.5 animate-spin text-primary" />}
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw />
              Refresh
            </Button>
          </div>
        </div>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Run evaluation</CardTitle>
            <CardDescription>
              Choose the temporal split and the number of held-out issues to replay.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-end gap-3">
              <div className="space-y-1">
                <label className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                  Train before
                </label>
                <div className="relative">
                  <CalendarDays className="pointer-events-none absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
                  <Input
                    type="date"
                    value={trainBefore}
                    onChange={event => setTrainBefore(event.target.value)}
                    className="h-9 w-40 bg-background/60 pl-8 text-xs"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                  Test after
                </label>
                <div className="relative">
                  <CalendarDays className="pointer-events-none absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
                  <Input
                    type="date"
                    value={testAfter}
                    onChange={event => setTestAfter(event.target.value)}
                    className="h-9 w-40 bg-background/60 pl-8 text-xs"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                  Max test issues
                </label>
                <Input
                  type="number"
                  min={10}
                  max={2000}
                  value={maxIssues}
                  onChange={event => setMaxIssues(Math.min(2000, Math.max(10, Number(event.target.value) || 10)))}
                  className="h-9 w-28 bg-background/60 font-mono text-xs"
                />
              </div>
              <Button onClick={handleRun} disabled={running || !repo}>
                {running ? <Loader2 className="animate-spin" /> : <Play />}
                {running ? 'Running…' : 'Run ablation'}
              </Button>
            </div>
            <p className="mt-2.5 text-[10px] text-muted-foreground">
              Evaluation runs in the background. The dashboard refreshes results automatically.
            </p>
          </CardContent>
        </Card>

        {isLoading ? (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <Skeleton key={index} className="h-28" />
              ))}
            </div>
            <Skeleton className="h-80" />
          </div>
        ) : results.length === 0 ? (
          <Card>
            <CardContent className="p-6">
              <EmptyState
                icon={<BarChart3 />}
                title="No evaluation results"
                description="Load a dataset, build developer profiles, then run the ablation study to measure Top-K accuracy."
              />
            </CardContent>
          </Card>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <StatCard
                label="Best Top-5"
                value={best ? `${best.top5}%` : '—'}
                hint={best ? `Config ${best.config} · ${best.config_name}` : undefined}
                icon={<Trophy />}
                accent="emerald"
              />
              <StatCard
                label="Best MRR"
                value={best ? best.mrr.toFixed(3) : '—'}
                hint="Mean reciprocal rank ×100 in the chart"
                icon={<BarChart3 />}
                accent="sky"
                delay={0.05}
              />
              <StatCard
                label="Test issues"
                value={best ? best.n.toLocaleString() : '—'}
                hint={`${results.length} ablation configurations`}
                icon={<CalendarDays />}
                accent="violet"
                delay={0.1}
              />
            </div>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle>Accuracy by signal configuration</CardTitle>
                <CardDescription>Top-K accuracy and MRR across configurations A–E</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={chartData} margin={{ top: 8, right: 12, left: -16, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis
                      dataKey="name"
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                      domain={[0, 100]}
                    />
                    <ChartTooltip
                      cursor={{ fill: 'hsl(var(--accent) / 0.35)' }}
                      contentStyle={{
                        background: 'hsl(var(--popover))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: 10,
                        fontSize: 11,
                        color: 'hsl(var(--popover-foreground))',
                      }}
                      labelStyle={{ color: 'hsl(var(--muted-foreground))', marginBottom: 4 }}
                      formatter={(value: number | string, name: string) => [`${value}${name === 'MRR × 100' ? '' : '%'}`, name]}
                    />
                    <Legend
                      wrapperStyle={{ fontSize: 11, color: 'hsl(var(--muted-foreground))', paddingTop: 8 }}
                      iconType="circle"
                      iconSize={7}
                    />
                    {SERIES.map(series => (
                      <Bar
                        key={series.key}
                        dataKey={series.key}
                        fill={series.color}
                        radius={[4, 4, 0, 0]}
                        maxBarSize={38}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card className="overflow-hidden">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Configuration comparison</CardTitle>
                    <CardDescription className="mt-1">Best configuration is highlighted</CardDescription>
                  </div>
                  {best && <Badge variant="success">Best: {best.config}</Badge>}
                </div>
              </CardHeader>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-y border-border/70 bg-muted/40 text-left text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                      <th className="px-4 py-2.5 font-medium">Config</th>
                      <th className="px-4 py-2.5 font-medium">Signals</th>
                      <th className="px-4 py-2.5 text-right font-medium">Top-1</th>
                      <th className="px-4 py-2.5 text-right font-medium">Top-3</th>
                      <th className="px-4 py-2.5 text-right font-medium">Top-5</th>
                      <th className="px-4 py-2.5 text-right font-medium">MRR</th>
                      <th className="px-4 py-2.5 text-right font-medium">N</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map(result => {
                      const isBest = best?.config === result.config
                      return (
                        <tr
                          key={result.config}
                          className={cn(
                            'border-b border-border/50 transition-colors last:border-0',
                            isBest ? 'bg-primary/[0.045]' : 'hover:bg-accent/30',
                          )}
                        >
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <span
                                className={cn(
                                  'grid size-5 place-items-center rounded font-mono text-[10px]',
                                  isBest ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground',
                                )}
                              >
                                {result.config}
                              </span>
                              {isBest && <Trophy className="size-3 text-primary" />}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">{result.config_name}</td>
                          <td className="px-4 py-3 text-right tabular-nums">{result.top1}%</td>
                          <td className="px-4 py-3 text-right tabular-nums">{result.top3}%</td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <Progress value={result.top5} className="h-1 w-14" indicatorClassName="bg-primary" />
                              <span className="w-9 tabular-nums text-foreground">{result.top5}%</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-right tabular-nums">{result.mrr}</td>
                          <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{result.n}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Card>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-center text-[10px] text-muted-foreground"
            >
              Results are written to <span className="font-mono">docs/results.md</span> and refreshed from the API.
            </motion.p>
          </>
        )}
      </div>
    </div>
  )
}
