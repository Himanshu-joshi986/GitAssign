import { useMemo, useState } from 'react'
import { motion } from 'motion/react'
import {
  CheckCircle2,
  Clock3,
  RefreshCw,
  Search,
  Sparkles,
  Settings2,
  UserRound,
  Users,
} from 'lucide-react'
import { useAppSelector } from '../store/hooks'
import { selectActiveRepo } from '../store/uiSlice'
import { useAnalyzeRepoMutation, useBuildProfilesMutation, useGetDevelopersQuery } from '../store/apiSlice'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { EmptyState } from './ui/empty-state'
import { Input } from './ui/input'
import { Progress } from './ui/progress'
import { Skeleton } from './ui/skeleton'
import { StatCard } from './ui/stat-card'
import { cn, formatRelative, initials } from '../lib/utils'

const AVATARS = [
  'from-emerald-500/30 to-teal-500/10 text-emerald-300',
  'from-sky-500/30 to-blue-500/10 text-sky-300',
  'from-violet-500/30 to-purple-500/10 text-violet-300',
  'from-amber-500/30 to-orange-500/10 text-amber-300',
  'from-rose-500/30 to-pink-500/10 text-rose-300',
]

export default function DeveloperList() {
  const repo = useAppSelector(selectActiveRepo)
  const { data, isLoading, isFetching, refetch } = useGetDevelopersQuery(repo, { skip: !repo })
  const [buildProfiles, { isLoading: building }] = useBuildProfilesMutation()
  const [analyzeRepo, { isLoading: analyzing }] = useAnalyzeRepoMutation()
  const [query, setQuery] = useState('')

  const developers = data?.developers ?? []
  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return developers
    return developers.filter(developer => developer.username?.toLowerCase().includes(term))
  }, [developers, query])

  const totalResolved = developers.reduce((sum, developer) => sum + (developer.resolved_count ?? 0), 0)
  const totalOpen = developers.reduce((sum, developer) => sum + (developer.open_issues ?? 0), 0)
  const maxResolved = Math.max(...developers.map(developer => developer.resolved_count ?? 0), 1)

  async function handleBuild() {
    await buildProfiles({ repo })
    refetch()
  }

  async function handleAnalyze() {
    await analyzeRepo({ repo }).unwrap()
    refetch()
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Badge variant="outline" className="gap-1.5">
              <Users className="size-3 text-primary" />
              Profiles
            </Badge>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">Developer expertise</h1>
            <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Profiles are built from resolved issues, components, and commit history. The scoring engine uses them to
              rank candidates for every new issue.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className={cn(isFetching && 'animate-spin')} />
              Refresh
            </Button>
            <Button size="sm" onClick={handleBuild} disabled={building || !repo}>
              {building ? <RefreshCw className="animate-spin" /> : <Settings2 />}
              {building ? 'Building…' : 'Build profiles'}
            </Button>
            <Button variant="secondary" size="sm" onClick={handleAnalyze} disabled={analyzing || !repo}>
              {analyzing ? <RefreshCw className="animate-spin" /> : <Sparkles />}
              {analyzing ? 'Analyzing…' : 'AI analyze'}
            </Button>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard
            label="Developers"
            value={developers.length.toLocaleString()}
            hint="With expertise profiles"
            icon={<Users />}
            accent="violet"
          />
          <StatCard
            label="Resolved issues"
            value={totalResolved.toLocaleString()}
            hint="Historical evidence available"
            icon={<CheckCircle2 />}
            accent="emerald"
            delay={0.05}
          />
          <StatCard
            label="Current open load"
            value={totalOpen.toLocaleString()}
            hint="Used by the workload penalty"
            icon={<Clock3 />}
            accent="amber"
            delay={0.1}
          />
        </div>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
            <div>
              <CardTitle>Team profiles</CardTitle>
              <CardDescription className="mt-1">
                {filtered.length} of {developers.length} developers
              </CardDescription>
            </div>
            <div className="relative w-full max-w-[240px]">
              <Search className="pointer-events-none absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
              <Input
                value={query}
                onChange={event => setQuery(event.target.value)}
                placeholder="Find a developer"
                className="h-9 bg-background/60 pl-8 text-xs"
              />
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 6 }).map((_, index) => (
                  <Skeleton key={index} className="h-36" />
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <EmptyState
                icon={<Users />}
                title={query ? 'No matching developers' : 'No developer profiles'}
                description={
                  query
                    ? 'Try a different username.'
                    : 'Load a dataset or ingest a repository, then build profiles to populate this team view.'
                }
                action={
                  !query ? (
                    <Button size="sm" onClick={handleBuild} disabled={building || !repo}>
                      <Settings2 />
                      Build profiles
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {filtered.map((developer, index) => (
                  <motion.div
                    key={developer.username}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.28, delay: Math.min(index * 0.025, 0.2) }}
                    className="rounded-xl border border-border/80 bg-background/40 p-4 transition-colors hover:border-border hover:bg-accent/25"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          'grid size-9 shrink-0 place-items-center rounded-full border border-border bg-gradient-to-br text-[11px] font-semibold',
                          AVATARS[index % AVATARS.length],
                        )}
                      >
                        {initials(developer.username)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-semibold">@{developer.username}</p>
                        <p className="mt-0.5 inline-flex items-center gap-1 text-[10px] text-muted-foreground">
                          <Clock3 className="size-3" />
                          {formatRelative(developer.last_active)}
                        </p>
                      </div>
                      {index < 3 && <Badge variant="muted">Top {index + 1}</Badge>}
                    </div>

                    <div className="mt-3 grid grid-cols-2 gap-2">
                      <div className="rounded-lg border border-border/60 bg-card/60 p-2 text-center">
                        <div className="text-base font-semibold tabular-nums text-emerald-400">
                          {developer.resolved_count}
                        </div>
                        <div className="text-[9px] uppercase tracking-[0.1em] text-muted-foreground">Resolved</div>
                      </div>
                      <div className="rounded-lg border border-border/60 bg-card/60 p-2 text-center">
                        <div className="text-base font-semibold tabular-nums text-amber-400">
                          {developer.open_issues}
                        </div>
                        <div className="text-[9px] uppercase tracking-[0.1em] text-muted-foreground">Open</div>
                      </div>
                    </div>

                    <div className="mt-3">
                      <div className="mb-1 text-[9px] uppercase tracking-[0.1em] text-muted-foreground">AI domains</div>
                      {developer.domains?.length ? (
                        <div className="flex flex-wrap gap-1">
                          {developer.domains.slice(0, 3).map(domain => (
                            <Badge key={domain} variant="outline" className="text-[10px]">{domain}</Badge>
                          ))}
                        </div>
                      ) : (
                        <span className="text-[10px] text-muted-foreground">Not analyzed yet</span>
                      )}
                      {developer.domain_summary && <p className="mt-1 line-clamp-2 text-[10px] text-muted-foreground">{developer.domain_summary}</p>}
                    </div>

                    <div className="mt-3 space-y-1">
                      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <UserRound className="size-3" />
                          Experience
                        </span>
                        <span className="font-mono">
                          {Math.round(((developer.resolved_count ?? 0) / maxResolved) * 100)}%
                        </span>
                      </div>
                      <Progress
                        value={((developer.resolved_count ?? 0) / maxResolved) * 100}
                        className="h-1"
                      />
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
