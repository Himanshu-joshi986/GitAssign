import { useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
  ArrowRight,
  Bug,
  CheckCircle2,
  FileCode2,
  FlaskConical,
  GitBranch,
  ScanSearch,
  Sparkles,
  UploadCloud,
  X,
} from 'lucide-react'
import { useDemoScanMutation, type DemoBug } from '../store/apiSlice'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { selectActiveRepo, setRepo, setTab } from '../store/uiSlice'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { EmptyState } from './ui/empty-state'
import { Input } from './ui/input'
import { cn } from '../lib/utils'

interface ScanResult {
  bugs: DemoBug[]
  profiles_used: number
  message: string
}

export default function DemoScan() {
  const activeRepo = useAppSelector(selectActiveRepo)
  const dispatch = useAppDispatch()
  const inputRef = useRef<HTMLInputElement>(null)

  const [repo, setRepoInput] = useState(activeRepo)
  const [filename, setFilename] = useState('')
  const [content, setContent] = useState('')
  const [dragging, setDragging] = useState(false)
  const [result, setResult] = useState<ScanResult | null>(null)
  const [scan, { isLoading, error }] = useDemoScanMutation()

  const lineCount = content ? content.split('\n').length : 0

  async function chooseFile(file?: File) {
    if (!file) return
    setFilename(file.name)
    setContent(await file.text())
    setResult(null)
  }

  function clearFile() {
    setFilename('')
    setContent('')
    setResult(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  async function handleScan() {
    if (!repo.trim() || !filename || !content) return
    const scanResult = await scan({ repo: repo.trim(), filename, content }).unwrap()
    setResult(scanResult)
    dispatch(setRepo(repo.trim()))
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-5 p-4 sm:p-6">
        <div>
          <Badge variant="outline" className="gap-1.5">
            <FlaskConical className="size-3 text-primary" />
            Demo workflow
          </Badge>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Scan a file and route its defects</h1>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            Upload a source file with explicit <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px] text-primary">BUG-*</code>{' '}
            markers. GitAssign creates queued issues and recommends a developer from repository history.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
          <Card className="h-fit">
            <CardHeader className="pb-3">
              <CardTitle>Scan input</CardTitle>
              <CardDescription>Repository context and the file to analyze</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                  Repository
                </label>
                <div className="relative">
                  <GitBranch className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
                  <Input
                    value={repo}
                    onChange={event => setRepoInput(event.target.value)}
                    placeholder="owner/new-repo"
                    className="bg-background/60 pl-8 font-mono text-xs"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <span className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                  Source file
                </span>
                <input
                  ref={inputRef}
                  type="file"
                  id="demo-file"
                  accept=".py,.js,.ts,.tsx,.java,.txt,.md"
                  className="sr-only"
                  onChange={event => chooseFile(event.target.files?.[0])}
                />

                {!filename ? (
                  <label
                    htmlFor="demo-file"
                    onDragOver={event => {
                      event.preventDefault()
                      setDragging(true)
                    }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={event => {
                      event.preventDefault()
                      setDragging(false)
                      chooseFile(event.dataTransfer.files?.[0])
                    }}
                    className={cn(
                      'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-4 py-8 text-center transition-colors',
                      dragging
                        ? 'border-primary bg-primary/10'
                        : 'border-border bg-background/40 hover:border-primary/40 hover:bg-accent/30',
                    )}
                  >
                    <div className="grid size-10 place-items-center rounded-xl border border-border bg-muted/60">
                      <UploadCloud className="size-5 text-primary" />
                    </div>
                    <div>
                      <p className="text-xs font-medium">Drop a file or click to browse</p>
                      <p className="mt-0.5 text-[10px] text-muted-foreground">Python, JS/TS, Java, text, or Markdown</p>
                    </div>
                  </label>
                ) : (
                  <motion.div
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-center gap-2.5 rounded-xl border border-border bg-background/50 p-3"
                  >
                    <div className="grid size-9 shrink-0 place-items-center rounded-lg border border-primary/25 bg-primary/10">
                      <FileCode2 className="size-4 text-primary" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-mono text-[11px]">{filename}</p>
                      <p className="text-[10px] text-muted-foreground">{lineCount} lines</p>
                    </div>
                    <Button variant="ghost" size="icon-sm" onClick={clearFile} aria-label="Remove file">
                      <X />
                    </Button>
                  </motion.div>
                )}
              </div>

              <Button className="w-full" onClick={handleScan} disabled={isLoading || !repo.trim() || !filename || !content}>
                {isLoading ? <ScanSearch className="animate-pulse" /> : <ScanSearch />}
                {isLoading ? 'Scanning file…' : 'Find bugs and assign'}
              </Button>

              {error && (
                <p className="rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-[11px] text-rose-300">
                  Scan failed. Check the repository name and file contents.
                </p>
              )}

              <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  Marker format
                </p>
                <pre className="mt-1.5 overflow-x-auto font-mono text-[10px] leading-relaxed text-foreground/80">
{`# BUG-1: tax uses unit price
tax = order.unit_price * order.tax_rate`}
                </pre>
              </div>
            </CardContent>
          </Card>

          <Card className="min-h-[460px]">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Scan results</CardTitle>
                  <CardDescription className="mt-1">Detected defects and routed developers</CardDescription>
                </div>
                {result && (
                  <Badge variant="success">
                    {result.bugs.length} bug{result.bugs.length === 1 ? '' : 's'}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <AnimatePresence mode="wait">
                {!result ? (
                  <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <EmptyState
                      icon={<ScanSearch />}
                      title="No scan yet"
                      description="Upload a marked file and run the scan. Results will list each defect, its line, and the recommended owner."
                    />
                  </motion.div>
                ) : (
                  <motion.div
                    key="results"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="space-y-3"
                  >
                    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border/60 bg-background/40 p-3">
                      <CheckCircle2 className="size-4 text-emerald-400" />
                      <p className="text-xs font-medium">{result.message}</p>
                      <Badge variant={result.profiles_used ? 'success' : 'warning'} className="ml-auto">
                        {result.profiles_used
                          ? `${result.profiles_used} profiles used`
                          : 'Demo fallback enabled'}
                      </Badge>
                    </div>

                    <div className="space-y-2">
                      {result.bugs.map(bug => (
                        <motion.div
                          key={bug.bug_id}
                          initial={{ opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="rounded-xl border border-border/80 bg-background/40 p-3 transition-colors hover:border-border hover:bg-accent/25"
                        >
                          <div className="flex items-start gap-3">
                            <div className="grid size-8 shrink-0 place-items-center rounded-lg border border-rose-500/25 bg-rose-500/10">
                              <Bug className="size-4 text-rose-400" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
                                <span className="font-mono text-rose-300">{bug.bug_id}</span>
                                <span>·</span>
                                <span>issue #{bug.issue_num}</span>
                                <span>·</span>
                                <span>line {bug.line}</span>
                              </div>
                              <p className="mt-1 text-xs font-medium">{bug.title}</p>
                              <p className="mt-1 line-clamp-2 text-[10px] leading-relaxed text-muted-foreground">
                                {bug.evidence}
                              </p>
                            </div>
                            <div className="shrink-0 text-right">
                              <p className="text-[11px] font-semibold text-primary">@{bug.assigned_to}</p>
                              <Badge variant={bug.assignment_source === 'historical_profile' ? 'success' : 'muted'} className="mt-1">
                                {bug.assignment_source === 'historical_profile' ? 'Historical match' : 'Demo fallback'}
                              </Badge>
                            </div>
                          </div>
                        </motion.div>
                      ))}
                    </div>

                    {result.bugs.length > 0 && (
                      <div className="flex items-center justify-between rounded-lg border border-border/60 bg-primary/[0.035] p-3">
                        <p className="inline-flex items-center gap-1.5 text-[10px] text-muted-foreground">
                          <Sparkles className="size-3 text-primary" />
                          Preview only — assignments are queued for review.
                        </p>
                        <Button size="sm" variant="outline" onClick={() => dispatch(setTab('issues'))}>
                          Open queue
                          <ArrowRight />
                        </Button>
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
