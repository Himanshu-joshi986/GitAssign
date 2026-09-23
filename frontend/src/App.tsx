import { useState, useEffect } from 'react'
import { useAppDispatch, useAppSelector } from './store/hooks'
import { setRepo, setTab, selectActiveRepo, selectActiveTab,
         selectNotification, clearNotification } from './store/uiSlice'
import { useGetReposQuery, useGetPipelineStatusQuery, useIngestRepoMutation, useRemoveRepoMutation } from './store/apiSlice'
import IssueQueue from './components/IssueQueue'
import RecommendationPanel from './components/RecommendationPanel'
import BatchAssignment from './components/BatchAssignment'
import MetricsView from './components/MetricsView'
import DeveloperList from './components/DeveloperList'
import DemoScan from './components/DemoScan'

const TABS = [
  { id: 'demo',      label: '🧪 Demo Scan' },
  { id: 'issues',    label: '📋 Issues' },
  { id: 'assign',    label: '⚡ Batch Assign' },
  { id: 'metrics',   label: '📊 Metrics' },
  { id: 'developers',label: '👥 Developers' },
] as const

export default function App() {
  const dispatch    = useAppDispatch()
  const activeRepo  = useAppSelector(selectActiveRepo)
  const activeTab   = useAppSelector(selectActiveTab)
  const notification = useAppSelector(selectNotification)

  const { data: reposData } = useGetReposQuery(undefined, { pollingInterval: 15000 })
  const { data: pipeline } = useGetPipelineStatusQuery(activeRepo, {
    skip: !activeRepo,
    pollingInterval: 2000,
  })
  const [ingest, { isLoading: ingesting }] = useIngestRepoMutation()
  const [removeRepo] = useRemoveRepoMutation()

  const [repoInput, setRepoInput] = useState('')
  const [maxPages,  setMaxPages]  = useState(5)

  // Auto clear notification
  useEffect(() => {
    if (notification) {
      const t = setTimeout(() => dispatch(clearNotification()), 4000)
      return () => clearTimeout(t)
    }
  }, [notification, dispatch])

  async function handleIngest() {
    if (!repoInput.trim()) return
    const repo = repoInput.trim()
    await ingest({ repo, max_pages: maxPages })
    dispatch(setRepo(repo))
  }

  async function handleRemove(repo: string) {
    if (!window.confirm(`Remove all local data for ${repo}?`)) return
    await removeRepo(repo).unwrap()
    if (activeRepo === repo) {
      dispatch(setRepo(''))
      setRepoInput('')
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-4 sm:px-6 py-3 flex items-center gap-4">
        <span className="text-xl font-bold tracking-tight text-green-400">GitAssign</span>
        <span className="hidden sm:inline text-gray-500 text-sm">Live issue triage and developer intelligence</span>
        {activeRepo && pipeline && (
          <span className={`ml-auto text-xs px-2.5 py-1 rounded-full border ${
            pipeline.status === 'failed' ? 'text-red-300 border-red-800 bg-red-950/40' :
            pipeline.status === 'completed' ? 'text-green-300 border-green-800 bg-green-950/40' :
            pipeline.status === 'idle' ? 'text-gray-400 border-gray-700 bg-gray-800' :
            'text-amber-300 border-amber-800 bg-amber-950/40'
          }`}>
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-current mr-1.5 align-middle" />
            {pipeline.status === 'running' ? 'Live sync active' : pipeline.status}
          </span>
        )}
      </header>

      {/* Notification */}
      {notification && (
        <div className={`px-6 py-2 text-sm font-medium ${
          notification.type === 'success' ? 'bg-green-800 text-green-200' :
          notification.type === 'error'   ? 'bg-red-800 text-red-200' :
                                            'bg-blue-800 text-blue-200'
        }`}>
          {notification.message}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 max-w-[78vw] bg-gray-900 border-r border-gray-800 flex flex-col p-4 gap-4 shrink-0">
          {/* Repo selector */}
          <div>
            <label className="text-xs text-gray-400 uppercase tracking-wider mb-1 block">Repository</label>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100 mb-2 focus:outline-none focus:border-green-500"
              placeholder="owner/repo"
              value={repoInput}
              onChange={e => setRepoInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && dispatch(setRepo(repoInput.trim()))}
            />
            <button
              className="w-full bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm py-1.5 rounded mb-1 transition"
              onClick={() => dispatch(setRepo(repoInput.trim()))}
            >Load Repo Data</button>
            <div className="flex gap-1 items-center mb-1">
              <input
                type="number" min={1} max={50}
                className="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-300"
                value={maxPages}
                onChange={e => setMaxPages(Number(e.target.value))}
              />
              <button
                className="flex-1 bg-green-700 hover:bg-green-600 text-white text-sm py-1.5 rounded transition disabled:opacity-50"
                onClick={handleIngest}
                disabled={ingesting || !repoInput.trim()}
              >
                {ingesting ? 'Ingesting…' : '⬇ Ingest from GitHub'}
              </button>
            </div>
            <p className="text-xs text-gray-500">pages × 100 items each</p>
            {pipeline && pipeline.status !== 'idle' && (
              <div className={`mt-3 rounded border px-3 py-2 text-xs ${
                pipeline.status === 'failed' ? 'border-red-900 bg-red-950/30 text-red-300' :
                pipeline.status === 'completed' ? 'border-green-900 bg-green-950/30 text-green-300' :
                'border-amber-900 bg-amber-950/30 text-amber-300'
              }`}>
                <div className="font-medium capitalize">{pipeline.status}</div>
                <div className="mt-1 leading-relaxed opacity-80">{pipeline.message}</div>
                {pipeline.issues !== undefined && (
                  <div className="mt-1 opacity-70">{pipeline.issues} issues · {pipeline.contributors ?? 0} contributors</div>
                )}
              </div>
            )}
          </div>

          {/* Known repos */}
          {reposData?.repos && reposData.repos.length > 0 && (
            <div>
              <label className="text-xs text-gray-400 uppercase tracking-wider mb-1 block">Loaded Repos</label>
              <div className="flex flex-col gap-1">
                {reposData.repos.map(r => (
                  <div key={r.repo} className="flex gap-1 items-stretch">
                    <button
                      className={`flex-1 min-w-0 text-left text-sm px-2 py-1.5 rounded transition ${
                        activeRepo === r.repo
                          ? 'bg-green-800 text-green-200'
                          : 'bg-gray-800 hover:bg-gray-700 text-gray-300'
                      }`}
                      onClick={() => { dispatch(setRepo(r.repo)); setRepoInput(r.repo) }}
                    >
                      <div className="font-medium truncate">{r.repo}</div>
                      <div className="text-xs text-gray-500">{r.issue_count} issues</div>
                    </button>
                    <button
                      className="px-2 rounded bg-gray-800 text-gray-500 hover:bg-red-950 hover:text-red-300 transition"
                      title={`Remove ${r.repo}`}
                      aria-label={`Remove ${r.repo}`}
                      onClick={() => handleRemove(r.repo)}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Nav tabs */}
          <nav className="flex flex-col gap-1 mt-auto">
            {TABS.map(t => (
              <button
                key={t.id}
                className={`text-left text-sm px-3 py-2 rounded transition ${
                  activeTab === t.id
                    ? 'bg-green-900 text-green-300 font-medium'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                }`}
                onClick={() => dispatch(setTab(t.id))}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-hidden flex">
          {!activeRepo ? (
            <div className="flex-1 flex items-center justify-center text-gray-500 text-center p-8">
              <div>
                <div className="text-5xl mb-4">🔍</div>
                <div className="text-xl font-medium text-gray-400 mb-2">No repository selected</div>
                <div className="text-sm">Enter a repo slug on the left (e.g. <code className="text-green-400">pallets/flask</code>) and click Load or Ingest.</div>
                <div className="mt-4 text-xs text-gray-600">
                  To load bughub data: run <code className="text-green-600">python backend/scripts/load_bughub.py data/file.csv eclipse/jdt</code>
                </div>
              </div>
            </div>
          ) : (
            <>
              {activeTab === 'demo' && <DemoScan />}
              {activeTab === 'issues' && (
                <div className="flex flex-1 overflow-hidden">
                  <IssueQueue />
                  <RecommendationPanel />
                </div>
              )}
              {activeTab === 'assign'     && <BatchAssignment />}
              {activeTab === 'metrics'    && <MetricsView />}
              {activeTab === 'developers' && <DeveloperList />}
            </>
          )}
        </main>
      </div>
    </div>
  )
}
