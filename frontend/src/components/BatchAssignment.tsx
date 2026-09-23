import { useState } from 'react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { selectCheckedIssues, selectActiveRepo, setAssignResults,
         selectAssignResults, clearChecked, notify } from '../store/uiSlice'
import { useBatchAssignMutation, useApplyBatchAssignMutation, type Assignment } from '../store/apiSlice'

const TIER_BADGE: Record<string, string> = {
  Critical: 'bg-red-900 text-red-300',
  High:     'bg-orange-900 text-orange-300',
  Medium:   'bg-yellow-900 text-yellow-300',
  Low:      'bg-green-900 text-green-300',
}

function AssignmentCard({ a }: { a: Assignment }) {
  const [open, setOpen] = useState(false)
  return (
    <div className={`border rounded-lg p-4 mb-2 ${a.at_capacity ? 'border-orange-700 bg-orange-950/20' : 'border-gray-700 bg-gray-800'}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={`text-xs px-2 py-0.5 rounded font-medium ${TIER_BADGE[a.priority_tier] ?? TIER_BADGE.Medium}`}>
              {a.priority_tier}
            </span>
            <span className="text-gray-500 text-xs">#{a.issue_num}</span>
            {a.at_capacity && (
              <span className="text-xs bg-orange-900 text-orange-300 px-1.5 py-0.5 rounded">⚠ At capacity</span>
            )}
          </div>
          <p className="text-sm text-gray-200 truncate">{a.issue_title}</p>
        </div>
        <div className="text-right shrink-0">
          <div className="text-green-400 font-bold text-sm">@{a.assigned_to}</div>
          <div className="text-xs text-gray-500">score {(a.score * 100).toFixed(0)}</div>
          <div className="text-xs text-gray-600">{a.current_load} open</div>
        </div>
      </div>

      {/* Toggle evidence */}
      <button
        className="text-xs text-gray-500 hover:text-gray-300 mt-2"
        onClick={() => setOpen(!open)}
      >
        {open ? '▲ Hide evidence' : '▼ Show evidence'}
      </button>

      {open && a.explanation?.summary && (
        <div className="mt-2 text-xs text-gray-400 bg-gray-900 rounded p-3">
          <p className="mb-2 italic">{a.explanation.summary}</p>
          {a.explanation.signals && Object.entries(a.explanation.signals).map(([k, s]: [string, any]) => (
            <div key={k} className="flex justify-between text-xs text-gray-500 py-0.5 border-b border-gray-800">
              <span>{k.replace(/_/g, ' ')}</span>
              <span className="text-gray-300">{s.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function BatchAssignment() {
  const dispatch = useAppDispatch()
  const repo     = useAppSelector(selectActiveRepo)
  const checked  = useAppSelector(selectCheckedIssues)
  const results  = useAppSelector(selectAssignResults)

  const [capacity, setCapacity] = useState(3)
  const [assign, { isLoading }] = useBatchAssignMutation()
  const [apply, { isLoading: isApplying }] = useApplyBatchAssignMutation()

  async function handleAssign() {
    if (!checked.length) return
    try {
      const res = await assign({ repo, issue_nums: checked, capacity }).unwrap()
      dispatch(setAssignResults(res.assignments))
      dispatch(clearChecked())
      dispatch(notify({ message: `Assigned ${res.total} issues successfully`, type: 'success' }))
    } catch {
      dispatch(notify({ message: 'Assignment failed. Build profiles first.', type: 'error' }))
    }
  }

  async function handleApply() {
    if (!results.length) return
    try {
      const res = await apply({
        repo,
        issue_nums: results.map(a => a.issue_num),
        capacity,
        assignments: results,
      }).unwrap()
      dispatch(setAssignResults(res.assignments))
      dispatch(clearChecked())
      const assigned = res.assignments.filter(a => a.status === 'assigned').length
      dispatch(notify({ message: `Applied ${assigned} GitHub assignment${assigned === 1 ? '' : 's'}`, type: 'success' }))
    } catch {
      dispatch(notify({ message: 'GitHub assignment failed. Check token permissions.', type: 'error' }))
    }
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 bg-gray-900 flex items-center gap-4 flex-wrap">
        <div>
          <h2 className="font-semibold text-gray-200">Batch Assignment</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Select issues in the Issue Queue tab, then assign them here.
          </p>
        </div>
        <div className="flex items-center gap-3 ml-auto flex-wrap">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-400">Capacity per dev:</label>
            <input
              type="number" min={1} max={20}
              className="w-14 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200"
              value={capacity}
              onChange={e => setCapacity(Number(e.target.value))}
            />
          </div>
          <div className="text-sm text-gray-400">
            {checked.length} issue{checked.length !== 1 ? 's' : ''} selected
          </div>
          <button
            className="bg-green-700 hover:bg-green-600 disabled:opacity-40 text-white text-sm px-4 py-2 rounded transition"
            disabled={!checked.length || isLoading}
            onClick={handleAssign}
          >
            {isLoading ? 'Assigning…' : `⚡ Assign ${checked.length} Issues`}
          </button>
          {results.length > 0 && (
            <button
              className="bg-blue-700 hover:bg-blue-600 disabled:opacity-40 text-white text-sm px-4 py-2 rounded transition"
              disabled={isApplying}
              onClick={handleApply}
            >
              {isApplying ? 'Applying…' : 'Apply to GitHub'}
            </button>
          )}
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto p-6">
        {results.length === 0 ? (
          <div className="text-center text-gray-600 text-sm py-12">
            <div className="text-4xl mb-3">⚡</div>
            <div>Select issues from the Issue Queue tab, then click Assign.</div>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-gray-300">
                {results.length} assignments
              </h3>
              <button
                className="text-xs text-gray-500 hover:text-gray-300"
                onClick={() => dispatch(setAssignResults([]))}
              >Clear results</button>
            </div>
            {(results as Assignment[]).map(a => (
              <AssignmentCard key={a.issue_num} a={a} />
            ))}
          </>
        )}
      </div>
    </div>
  )
}
