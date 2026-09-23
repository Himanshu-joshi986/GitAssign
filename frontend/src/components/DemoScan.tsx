import { useState } from 'react'
import { useDemoScanMutation, type DemoBug } from '../store/apiSlice'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { selectActiveRepo, setRepo, setTab } from '../store/uiSlice'

export default function DemoScan() {
  const activeRepo = useAppSelector(selectActiveRepo)
  const dispatch = useAppDispatch()
  const [repo, setRepoInput] = useState(activeRepo)
  const [filename, setFilename] = useState('')
  const [content, setContent] = useState('')
  const [result, setResult] = useState<{ bugs: DemoBug[]; profiles_used: number; message: string } | null>(null)
  const [scan, { isLoading, error }] = useDemoScanMutation()

  async function chooseFile(file?: File) {
    if (!file) return
    setFilename(file.name)
    setContent(await file.text())
    setResult(null)
  }

  async function handleScan() {
    if (!repo.trim() || !filename || !content) return
    const scanResult = await scan({ repo: repo.trim(), filename, content }).unwrap()
    setResult(scanResult)
    dispatch(setRepo(repo.trim()))
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <p className="text-xs uppercase tracking-widest text-green-400 mb-2">Demo workflow</p>
          <h1 className="text-2xl font-semibold text-gray-100">Scan a file and route its bugs</h1>
          <p className="text-sm text-gray-400 mt-2 max-w-2xl">
            Upload a file containing marked defects such as <code className="text-green-300">BUG-1: incorrect total</code>.
            Existing profiles are preferred; a new repository receives demo developer assignments.
          </p>
        </div>

        <div className="grid lg:grid-cols-[1fr_1.2fr] gap-4">
          <section className="bg-gray-800 border border-gray-700 rounded-lg p-4">
            <label className="block text-xs uppercase tracking-wider text-gray-400 mb-1">Repository name</label>
            <input
              className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100 mb-4 focus:outline-none focus:border-green-500"
              placeholder="owner/new-repo"
              value={repo}
              onChange={e => setRepoInput(e.target.value)}
            />
            <label className="block text-xs uppercase tracking-wider text-gray-400 mb-1">Buggy file</label>
            <input
              type="file"
              accept=".py,.js,.ts,.java,.txt,.md"
              className="w-full text-sm text-gray-400 file:mr-3 file:rounded file:border-0 file:bg-gray-700 file:px-3 file:py-2 file:text-gray-200 hover:file:bg-gray-600"
              onChange={e => chooseFile(e.target.files?.[0])}
            />
            {filename && <div className="mt-3 text-xs text-gray-500">Loaded: {filename} · {content.split('\n').length} lines</div>}
            <button
              className="mt-5 w-full bg-green-700 hover:bg-green-600 disabled:opacity-40 text-white text-sm px-4 py-2 rounded transition"
              disabled={isLoading || !repo.trim() || !filename || !content}
              onClick={handleScan}
            >
              {isLoading ? 'Scanning…' : 'Find bugs and assign'}
            </button>
            {error && <p className="mt-3 text-xs text-red-300">Scan failed. Check the repository name and file.</p>}
          </section>

          <section className="bg-gray-900 border border-gray-800 rounded-lg p-4 min-h-64">
            {!result ? (
              <div className="h-full min-h-56 flex items-center justify-center text-center text-gray-600 text-sm">
                <div><div className="text-3xl mb-2">⌁</div><div>Scan results and assignments will appear here.</div></div>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between mb-4">
                  <div><h2 className="font-medium text-gray-200">{result.message}</h2><p className="text-xs text-gray-500">{result.profiles_used ? `${result.profiles_used} historical profiles used` : 'No history found; demo fallback enabled'}</p></div>
                  <span className="text-2xl font-bold text-green-400">{result.bugs.length}</span>
                </div>
                <div className="space-y-2">
                  {result.bugs.map(bug => (
                    <div key={bug.bug_id} className="border border-gray-700 rounded p-3 bg-gray-800">
                      <div className="flex items-start justify-between gap-3">
                        <div><div className="text-xs text-gray-500">{bug.bug_id} · issue #{bug.issue_num} · line {bug.line}</div><div className="text-sm text-gray-200 mt-1">{bug.title}</div></div>
                        <div className="text-right shrink-0"><div className="text-sm font-semibold text-green-400">@{bug.assigned_to}</div><div className="text-xs text-gray-500">{bug.assignment_source === 'demo_fallback' ? 'demo fallback' : 'historical match'}</div></div>
                      </div>
                      <p className="text-xs text-gray-500 mt-2">{bug.evidence}</p>
                    </div>
                  ))}
                </div>
                {result.bugs.length > 0 && (
                  <button className="mt-4 text-sm text-green-400 hover:text-green-300" onClick={() => dispatch(setTab('issues'))}>
                    Open these bugs in Issue Queue →
                  </button>
                )}
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
