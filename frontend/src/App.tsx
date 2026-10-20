import { lazy, Suspense, useEffect, useState } from 'react'
import { AnimatePresence, MotionConfig, motion } from 'motion/react'
import { Loader2 } from 'lucide-react'
import { TooltipProvider } from './components/ui/tooltip'
import { Sidebar } from './components/layout/sidebar'
import { Topbar } from './components/layout/topbar'
import { Toaster } from './components/layout/toaster'
import { Welcome } from './components/welcome'
import Overview from './components/Overview'
import IssueQueue from './components/IssueQueue'
import RecommendationPanel from './components/RecommendationPanel'
import BatchAssignment from './components/BatchAssignment'
import DeveloperList from './components/DeveloperList'
import DemoScan from './components/DemoScan'

const MetricsView = lazy(() => import('./components/MetricsView'))

function TabFallback() {
  return (
    <div className="flex flex-1 items-center justify-center gap-2 text-xs text-muted-foreground">
      <Loader2 className="size-4 animate-spin text-primary" />
      Loading view…
    </div>
  )
}
import { useAppDispatch, useAppSelector } from './store/hooks'
import {
  clearNotification,
  notify,
  selectActiveRepo,
  selectActiveTab,
  selectNotification,
  setRepo,
  setTab,
} from './store/uiSlice'
import {
  useGetPipelineStatusQuery,
  useGetReposQuery,
  useIngestRepoMutation,
  useRemoveRepoMutation,
} from './store/apiSlice'
import type { TabId } from './lib/navigation'

export default function App() {
  const dispatch = useAppDispatch()
  const activeRepo = useAppSelector(selectActiveRepo)
  const activeTab = useAppSelector(selectActiveTab)
  const notification = useAppSelector(selectNotification)

  const { data: reposData } = useGetReposQuery(undefined, { pollingInterval: 15_000 })
  const { data: pipeline } = useGetPipelineStatusQuery(activeRepo, {
    skip: !activeRepo,
    pollingInterval: 2_000,
  })
  const [ingest, { isLoading: ingesting }] = useIngestRepoMutation()
  const [removeRepo] = useRemoveRepoMutation()

  const [mobileOpen, setMobileOpen] = useState(false)
  const [repoInput, setRepoInput] = useState('')
  const [maxPages, setMaxPages] = useState(5)

  const repos = reposData?.repos ?? []

  useEffect(() => {
    if (activeRepo) setRepoInput(activeRepo)
  }, [activeRepo])

  useEffect(() => {
    if (!notification) return
    const timer = window.setTimeout(() => dispatch(clearNotification()), 4_000)
    return () => window.clearTimeout(timer)
  }, [notification, dispatch])

  function openRepo(repo: string) {
    const value = repo.trim()
    if (!value) return
    setRepoInput(value)
    dispatch(setRepo(value))
    setMobileOpen(false)
  }

  async function handleIngest() {
    const repo = repoInput.trim()
    if (!repo) return
    try {
      await ingest({ repo, max_pages: maxPages }).unwrap()
      dispatch(setRepo(repo))
      dispatch(notify({ message: `Ingestion started for ${repo}`, type: 'info' }))
      setMobileOpen(false)
    } catch {
      dispatch(notify({ message: `Could not start ingestion for ${repo}`, type: 'error' }))
    }
  }

  async function handleRemove(repo: string) {
    if (!window.confirm(`Remove all local data for ${repo}?`)) return
    try {
      await removeRepo(repo).unwrap()
      if (activeRepo === repo) {
        dispatch(setRepo(''))
        setRepoInput('')
      }
      dispatch(notify({ message: `Removed local data for ${repo}`, type: 'success' }))
    } catch {
      dispatch(notify({ message: `Could not remove ${repo}`, type: 'error' }))
    }
  }

  function handleNavigate(tab: TabId) {
    dispatch(setTab(tab))
    setMobileOpen(false)
  }

  const renderSidebar = (onClose?: () => void) => (
    <Sidebar
      activeRepo={activeRepo}
      activeTab={activeTab}
      repos={repos}
      pipeline={pipeline}
      repoInput={repoInput}
      onRepoInputChange={setRepoInput}
      maxPages={maxPages}
      onMaxPagesChange={value => setMaxPages(Math.min(50, Math.max(1, value || 1)))}
      onLoad={() => openRepo(repoInput)}
      onIngest={handleIngest}
      onSelectRepo={openRepo}
      onRemove={handleRemove}
      onNavigate={handleNavigate}
      ingesting={ingesting}
      onClose={onClose}
    />
  )

  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider delayDuration={150}>
      <div className="relative flex h-dvh overflow-hidden bg-background">
        <div className="pointer-events-none absolute inset-x-0 top-0 z-0 h-72 bg-[radial-gradient(ellipse_at_top,hsl(var(--primary)/0.08),transparent_65%)]" />

        <div className="relative z-10 hidden h-full shrink-0 lg:block">{renderSidebar()}</div>

        <AnimatePresence>
          {mobileOpen && (
            <div className="fixed inset-0 z-50 lg:hidden">
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setMobileOpen(false)}
                className="absolute inset-0 bg-black/70 backdrop-blur-sm"
              />
              <motion.div
                initial={{ x: '-100%' }}
                animate={{ x: 0 }}
                exit={{ x: '-100%' }}
                transition={{ type: 'spring', stiffness: 380, damping: 36 }}
                className="relative h-full w-[290px] shadow-2xl"
              >
                {renderSidebar(() => setMobileOpen(false))}
              </motion.div>
            </div>
          )}
        </AnimatePresence>

        <div className="relative z-10 flex min-w-0 flex-1 flex-col">
          <Topbar
            activeRepo={activeRepo}
            activeTab={activeTab}
            pipeline={pipeline}
            onMenu={() => setMobileOpen(true)}
          />

          <main className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={activeRepo ? activeTab : 'welcome'}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
                className="flex min-h-0 flex-1 flex-col"
              >
                {!activeRepo ? (
                  <Welcome repos={repos} onPrefill={setRepoInput} onSelect={openRepo} />
                ) : (
                  <>
                    {activeTab === 'overview' && <Overview />}
                    {activeTab === 'issues' && (
                      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
                        <IssueQueue />
                        <RecommendationPanel />
                      </div>
                    )}
                    {activeTab === 'assign' && <BatchAssignment />}
                    {activeTab === 'developers' && <DeveloperList />}
                    {activeTab === 'metrics' && (
                      <Suspense fallback={<TabFallback />}>
                        <MetricsView />
                      </Suspense>
                    )}
                    {activeTab === 'demo' && <DemoScan />}
                  </>
                )}
              </motion.div>
            </AnimatePresence>
          </main>
        </div>

        <Toaster notification={notification} onClose={() => dispatch(clearNotification())} />
      </div>
      </TooltipProvider>
    </MotionConfig>
  )
}
