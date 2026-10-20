import { useMemo, useState } from 'react'
import { motion } from 'motion/react'
import {
  ArrowRight,
  CircleCheck,
  CircleDot,
  Inbox,
  RefreshCw,
  Search,
  X,
} from 'lucide-react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import {
  checkAll,
  clearChecked,
  selectActiveRepo,
  selectCheckedIssues,
  selectIssue,
  selectSelectedIssue,
  setTab,
  toggleChecked,
} from '../store/uiSlice'
import { useGetIssuesQuery, type Issue } from '../store/apiSlice'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { EmptyState } from './ui/empty-state'
import { Input } from './ui/input'
import { Segmented } from './ui/segmented'
import { Skeleton } from './ui/skeleton'
import { cn } from '../lib/utils'
import { priorityMeta } from '../lib/priority'

type IssueState = 'open' | 'closed' | 'all'

export default function IssueQueue() {
  const dispatch = useAppDispatch()
  const repo = useAppSelector(selectActiveRepo)
  const selected = useAppSelector(selectSelectedIssue)
  const checked = useAppSelector(selectCheckedIssues)
  const [stateFilter, setStateFilter] = useState<IssueState>('all')
  const [query, setQuery] = useState('')

  const { data, isLoading, isFetching, isError, refetch } = useGetIssuesQuery(
    { repo, state: stateFilter },
    { skip: !repo, pollingInterval: 60_000, refetchOnMountOrArgChange: true },
  )

  const issues = data?.issues ?? []

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return issues
    return issues.filter(issue => {
      const labels = Array.isArray(issue.labels) ? issue.labels.join(' ') : ''
      return (
        issue.title.toLowerCase().includes(term) ||
        String(issue.number).includes(term) ||
        labels.toLowerCase().includes(term)
      )
    })
  }, [issues, query])

  const allSelected = filtered.length > 0 && filtered.every(issue => checked.includes(issue.number))

  function handleSelectAll() {
    if (allSelected) dispatch(clearChecked())
    else dispatch(checkAll(filtered.map(issue => issue.number)))
  }

  return (
    <div className="flex min-h-0 w-full flex-1 flex-col border-b border-border/70 bg-card/30 lg:w-[400px] lg:flex-none lg:shrink-0 lg:border-b-0 lg:border-r">
      <div className="shrink-0 space-y-3 border-b border-border/70 p-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold tracking-tight">Issue queue</h2>
          <Badge variant="muted" className="font-mono">
            {issues.length.toLocaleString()}
          </Badge>
          {isFetching && <RefreshCw className="size-3 animate-spin text-primary" />}
          <Button
            variant="ghost"
            size="icon-sm"
            className="ml-auto"
            onClick={() => refetch()}
            aria-label="Refresh issues"
          >
            <RefreshCw className={cn(isFetching && 'animate-spin')} />
          </Button>
        </div>

        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="Search title, number, or label"
            aria-label="Search issues"
            className="h-9 bg-background/60 pl-8 pr-8 text-xs"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              className="absolute right-2 top-2.5 text-muted-foreground hover:text-foreground"
              aria-label="Clear search"
            >
              <X className="size-3.5" />
            </button>
          )}
        </div>

        <div className="flex items-center justify-between gap-2">
          <Segmented
            value={stateFilter}
            onChange={setStateFilter}
            options={[
              { value: 'all', label: 'All' },
              { value: 'open', label: 'Open' },
              { value: 'closed', label: 'Closed' },
            ]}
          />
          <button
            type="button"
            onClick={handleSelectAll}
            className="text-[11px] text-muted-foreground transition-colors hover:text-foreground"
          >
            {allSelected ? 'Deselect all' : 'Select all'}
          </button>
        </div>

        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          <span className="size-1.5 rounded-full bg-primary" />
          {checked.length > 0 ? `${checked.length} selected for batch assignment` : 'Select issues to batch assign'}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="space-y-2 p-3">
            {Array.from({ length: 7 }).map((_, index) => (
              <div key={index} className="space-y-2 rounded-lg border border-border/60 p-3">
                <div className="flex gap-2">
                  <Skeleton className="h-4 w-14" />
                  <Skeleton className="h-4 w-10" />
                </div>
                <Skeleton className="h-3.5 w-full" />
                <Skeleton className="h-3.5 w-2/3" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <EmptyState
            icon={<Inbox />}
            title="Could not load issues"
            description="Check the repository slug and make sure data has been loaded or ingested."
            action={
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                <RefreshCw />
                Retry
              </Button>
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<Inbox />}
            title={query ? 'No matching issues' : `No ${stateFilter === 'all' ? '' : stateFilter} issues`}
            description={
              query
                ? 'Try a different title, number, or label.'
                : stateFilter === 'open'
                  ? 'Historical datasets such as Eclipse JDT contain closed issues. Switch to All or Closed.'
                  : 'Load a dataset or ingest a GitHub repository to populate the queue.'
            }
          />
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="divide-y divide-border/50"
          >
            {filtered.map((issue: Issue) => {
              const tier = issue.priority?.tier ?? 'Medium'
              const meta = priorityMeta(tier)
              const isSelected = selected === issue.number
              const isChecked = checked.includes(issue.number)
              const isOpen = issue.state === 'open'

              return (
                <div
                  key={issue.number}
                  role="button"
                  tabIndex={0}
                  onClick={() => dispatch(selectIssue(isSelected ? null : issue.number))}
                  onKeyDown={event => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      dispatch(selectIssue(isSelected ? null : issue.number))
                    }
                  }}
                  className={cn(
                    'group relative cursor-pointer border-l-2 px-3 py-3 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/40',
                    isSelected
                      ? 'border-primary bg-primary/[0.055]'
                      : 'border-transparent hover:bg-accent/40',
                  )}
                >
                  <div className="flex items-start gap-2.5">
                    <input
                      type="checkbox"
                      aria-label={`Select issue ${issue.number}`}
                      className="mt-1 size-3.5 shrink-0 cursor-pointer rounded border-border accent-emerald-500"
                      checked={isChecked}
                      onClick={event => event.stopPropagation()}
                      onChange={() => dispatch(toggleChecked(issue.number))}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex items-center gap-1.5">
                        <Badge variant={meta.badge}>{tier}</Badge>
                        <span className="font-mono text-[10px] text-muted-foreground">#{issue.number}</span>
                        {issue.classification?.kind && <Badge variant="outline" className="capitalize">{issue.classification.kind}</Badge>}
                        <span
                          className={cn(
                            'ml-auto inline-flex items-center gap-1 text-[10px]',
                            isOpen ? 'text-emerald-400' : 'text-muted-foreground',
                          )}
                        >
                          {isOpen ? <CircleDot className="size-3" /> : <CircleCheck className="size-3" />}
                          {issue.state}
                        </span>
                      </div>
                      <p
                        className={cn(
                          'line-clamp-2 text-xs leading-relaxed',
                          isSelected ? 'text-foreground' : 'text-foreground/90',
                        )}
                      >
                        {issue.title}
                      </p>
                      {Array.isArray(issue.labels) && issue.labels.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {issue.labels.slice(0, 3).map(label => (
                            <span
                              key={label}
                              className="rounded border border-border/70 bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground"
                            >
                              {label}
                            </span>
                          ))}
                          {issue.labels.length > 3 && (
                            <span className="px-1 py-0.5 text-[10px] text-muted-foreground">
                              +{issue.labels.length - 3}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </motion.div>
        )}
      </div>

      <div className="shrink-0 border-t border-border/70 bg-background/40 p-3">
        {checked.length > 0 ? (
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-muted-foreground">
              <span className="font-mono text-foreground">{checked.length}</span> selected
            </span>
            <Button variant="ghost" size="sm" className="ml-auto" onClick={() => dispatch(clearChecked())}>
              Clear
            </Button>
            <Button size="sm" onClick={() => dispatch(setTab('assign'))}>
              Batch assign
              <ArrowRight />
            </Button>
          </div>
        ) : (
          <p className="text-center text-[10px] text-muted-foreground">
            Showing {filtered.length.toLocaleString()} of {issues.length.toLocaleString()} issues
          </p>
        )}
      </div>
    </div>
  )
}
