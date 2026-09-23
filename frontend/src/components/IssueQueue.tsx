import { useEffect, useState } from 'react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { selectIssue, toggleChecked, clearChecked, checkAll, setTab,
         selectSelectedIssue, selectCheckedIssues, selectActiveRepo } from '../store/uiSlice'
import { useGetIssuesQuery, type Issue } from '../store/apiSlice'

const TIER_STYLE: Record<string, string> = {
  Critical: 'bg-red-900 text-red-300 border-red-700',
  High:     'bg-orange-900 text-orange-300 border-orange-700',
  Medium:   'bg-yellow-900 text-yellow-300 border-yellow-700',
  Low:      'bg-green-900 text-green-300 border-green-700',
}

type IssueState = 'open' | 'closed' | 'all'

export default function IssueQueue() {
  const dispatch = useAppDispatch()
  const repo     = useAppSelector(selectActiveRepo)
  const selected = useAppSelector(selectSelectedIssue)
  const checked  = useAppSelector(selectCheckedIssues)
  const [stateFilter, setStateFilter] = useState<IssueState>('all')
  const [filterChanging, setFilterChanging] = useState(false)

  const { data, isLoading, isFetching, error } = useGetIssuesQuery(
    { repo, state: stateFilter }, {
      skip: !repo,
      pollingInterval: 60000,
      refetchOnMountOrArgChange: true,
    }
  )

  const issues = data?.issues ?? []

  useEffect(() => {
    if (filterChanging && !isFetching) setFilterChanging(false)
  }, [filterChanging, isFetching])

  function handleSelectAll() {
    if (checked.length === issues.length) dispatch(clearChecked())
    else dispatch(checkAll(issues.map(i => i.number)))
  }

  if (isLoading || filterChanging) return (
    <div className="w-96 border-r border-gray-800 flex items-center justify-center text-gray-500">
      Loading {stateFilter} issues…
    </div>
  )

  if (error) return (
    <div className="w-96 border-r border-gray-800 flex items-center justify-center text-red-400 p-4 text-sm">
      Failed to load issues. Check the repo name and that data has been loaded.
    </div>
  )

  return (
    <div className="w-96 border-r border-gray-800 flex flex-col overflow-hidden shrink-0">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800">
        <div className="flex items-center justify-between mb-2">
          <div>
            <span className="font-semibold text-gray-200">Issue Queue</span>
            <span className="ml-2 text-xs text-gray-500">{issues.length}</span>
            {isFetching && <span className="ml-2 text-xs text-green-500">↻</span>}
          </div>
          <button
            className="text-xs text-gray-400 hover:text-gray-200"
            onClick={handleSelectAll}
          >
            {checked.length === issues.length && issues.length > 0 ? 'Deselect all' : 'Select all'}
          </button>
        </div>
        {/* State filter — bughub datasets are mostly closed */}
        <div className="flex gap-1">
          {(['all', 'open', 'closed'] as IssueState[]).map(s => (
            <button
              key={s}
              className={`text-xs px-2 py-1 rounded capitalize transition ${
                stateFilter === s
                  ? 'bg-green-800 text-green-200'
                  : 'bg-gray-800 text-gray-400 hover:text-gray-200'
              }`}
              onClick={() => {
                if (s !== stateFilter) setFilterChanging(true)
                setStateFilter(s)
              }}
            >{s}</button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto divide-y divide-gray-800">
        {issues.length === 0 && (
          <div className="p-4 text-center text-gray-500 text-sm">
            No {stateFilter === 'all' ? '' : stateFilter + ' '}issues found for{' '}
            <code className="text-green-400">{repo}</code>.
            {stateFilter === 'open' && (
              <div className="mt-2 text-xs text-gray-600">
                Historical datasets (Eclipse JDT) are closed — switch to <strong>closed</strong> or <strong>all</strong>.
              </div>
            )}
          </div>
        )}
        {issues.map((issue: Issue) => {
          const tier  = issue.priority?.tier ?? 'Medium'
          const isSelected = selected === issue.number
          const isChecked  = checked.includes(issue.number)

          return (
            <div
              key={issue.number}
              className={`px-4 py-3 cursor-pointer transition group ${
                isSelected ? 'bg-gray-800' : 'hover:bg-gray-800'
              }`}
              onClick={() => dispatch(selectIssue(isSelected ? null : issue.number))}
            >
              <div className="flex items-start gap-2">
                <input
                  type="checkbox"
                  className="mt-1 accent-green-500 cursor-pointer shrink-0"
                  checked={isChecked}
                  onClick={e => e.stopPropagation()}
                  onChange={() => dispatch(toggleChecked(issue.number))}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs px-1.5 py-0.5 rounded border font-medium shrink-0 ${TIER_STYLE[tier]}`}>
                      {tier}
                    </span>
                    <span className="text-gray-500 text-xs shrink-0">#{issue.number}</span>
                    {issue.state && (
                      <span className="text-xs text-gray-600">{issue.state}</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-200 line-clamp-2 leading-snug">{issue.title}</p>
                  {Array.isArray(issue.labels) && issue.labels.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {issue.labels.slice(0, 3).map((l: string) => (
                        <span key={l} className="text-xs bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded">
                          {l}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {checked.length > 0 && (
        <div className="px-4 py-2 border-t border-gray-800 bg-gray-900 text-xs text-gray-400 flex items-center justify-between">
          <span>{checked.length} selected</span>
          <button
            className="text-green-400 hover:text-green-300"
            onClick={() => dispatch(setTab('assign'))}
          >
            Assign batch →
          </button>
        </div>
      )}
    </div>
  )
}
