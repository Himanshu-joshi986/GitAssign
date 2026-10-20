import { motion } from 'motion/react'
import {
  ArrowRight,
  Database,
  FolderGit2,
  GitBranch,
  ScanSearch,
  Sparkles,
  Users,
} from 'lucide-react'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { cn } from '../lib/utils'
import type { RepoSummary } from './layout/sidebar'

interface WelcomeProps {
  repos: RepoSummary[]
  onPrefill: (repo: string) => void
  onSelect: (repo: string) => void
}

const STEPS = [
  {
    icon: ScanSearch,
    title: '1 · Connect',
    text: 'Load a BugHub dataset or ingest issues, pull requests, and commits from GitHub.',
  },
  {
    icon: Users,
    title: '2 · Profile',
    text: 'Build expertise profiles from resolved issues, components, and file-level history.',
  },
  {
    icon: Sparkles,
    title: '3 · Recommend',
    text: 'Review ranked developers with evidence, then apply or override the recommendation.',
  },
]

export function Welcome({ repos, onPrefill, onSelect }: WelcomeProps) {
  return (
    <div className="relative flex-1 overflow-y-auto">
      <div className="pointer-events-none absolute inset-0 grid-fade opacity-70" />
      <div className="relative mx-auto flex max-w-5xl flex-col items-center px-4 py-12 text-center sm:py-20">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Badge variant="outline" className="gap-1.5 border-primary/25 bg-primary/5 text-primary">
            <Sparkles className="size-3" />
            Explainable developer routing
          </Badge>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.05 }}
          className="mt-5 max-w-3xl text-balance text-3xl font-semibold leading-tight tracking-tight sm:text-5xl"
        >
          Triage with <span className="text-primary">evidence</span>, not guesswork.
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.1 }}
          className="mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base"
        >
          Connect a repository to turn its history into transparent developer recommendations — with workload
          awareness and a maintainer in control of every assignment.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.15 }}
          className="mt-8 grid w-full max-w-3xl gap-3 sm:grid-cols-2"
        >
          <button
            type="button"
            onClick={() => onPrefill('eclipse/jdt')}
            className="group rounded-xl border border-border bg-card/60 p-4 text-left backdrop-blur-sm transition-all hover:border-primary/30 hover:bg-primary/[0.04]"
          >
            <div className="flex items-center gap-2">
              <span className="grid size-8 place-items-center rounded-lg border border-sky-500/20 bg-sky-500/10">
                <Database className="size-4 text-sky-400" />
              </span>
              <div>
                <p className="text-xs font-semibold">Load a local dataset</p>
                <p className="text-[10px] text-muted-foreground">Eclipse JDT · bundled CSV</p>
              </div>
              <Badge variant="muted" className="ml-auto">Offline</Badge>
            </div>
            <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground">
              Use historical BugHub data for a reproducible evaluation demo.
            </p>
            <span className="mt-2 inline-flex items-center gap-1 text-[10px] font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
              Use eclipse/jdt
              <ArrowRight className="size-3" />
            </span>
          </button>

          <button
            type="button"
            onClick={() => onPrefill('pallets/click')}
            className="group rounded-xl border border-border bg-card/60 p-4 text-left backdrop-blur-sm transition-all hover:border-primary/30 hover:bg-primary/[0.04]"
          >
            <div className="flex items-center gap-2">
              <span className="grid size-8 place-items-center rounded-lg border border-violet-500/20 bg-violet-500/10">
                <GitBranch className="size-4 text-violet-400" />
              </span>
              <div>
                <p className="text-xs font-semibold">Ingest from GitHub</p>
                <p className="text-[10px] text-muted-foreground">Issues, PRs, and commits</p>
              </div>
              <Badge variant="muted" className="ml-auto">Live</Badge>
            </div>
            <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground">
              Start with a focused repository such as <span className="font-mono text-foreground/80">pallets/click</span>.
            </p>
            <span className="mt-2 inline-flex items-center gap-1 text-[10px] font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
              Use pallets/click
              <ArrowRight className="size-3" />
            </span>
          </button>
        </motion.div>

        <p className="mt-3 text-[10px] text-muted-foreground">
          Then press <span className="kbd">Load</span> or <span className="kbd">Ingest</span> in the sidebar.
        </p>

        {repos.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 }}
            className="mt-8 w-full max-w-3xl"
          >
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              Resume a repository
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {repos.map(repo => (
                <Button key={repo.repo} variant="outline" size="sm" onClick={() => onSelect(repo.repo)}>
                  <FolderGit2 />
                  {repo.repo}
                  <span className="font-mono text-[10px] text-muted-foreground">{repo.issue_count}</span>
                </Button>
              ))}
            </div>
          </motion.div>
        )}

        <div className="mt-12 grid w-full max-w-3xl gap-3 text-left sm:grid-cols-3">
          {STEPS.map((step, index) => {
            const Icon = step.icon
            return (
              <motion.div
                key={step.title}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 + index * 0.06 }}
                className={cn(
                  'rounded-xl border border-border/70 bg-card/40 p-4 backdrop-blur-sm',
                  index === 1 && 'sm:translate-y-2',
                )}
              >
                <Icon className="size-4 text-primary" />
                <p className="mt-2.5 text-[11px] font-semibold">{step.title}</p>
                <p className="mt-1 text-[10px] leading-relaxed text-muted-foreground">{step.text}</p>
              </motion.div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
