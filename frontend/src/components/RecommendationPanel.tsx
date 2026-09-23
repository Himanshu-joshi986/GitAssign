import { useAppSelector } from '../store/hooks'
import { selectSelectedIssue, selectActiveRepo } from '../store/uiSlice'
import { useGetRecommendationsQuery, type Recommendation, type SignalDetail } from '../store/apiSlice'
import { useState } from 'react'

const SIGNAL_COLORS = [
  'bg-blue-700', 'bg-purple-700', 'bg-teal-700',
  'bg-indigo-700', 'bg-cyan-700', 'bg-rose-700'
]

function ScoreBar({ value, max = 1 }: { value: number; max?: number }) {
  const pct = Math.min((value / max) * 100, 100)
  return (
    <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
      <div
        className="h-full bg-green-500 rounded-full transition-all"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

function SignalChip({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={`${color} rounded px-2 py-1 text-xs text-white`}>
      <div className="font-medium">{(value * 100).toFixed(0)}%</div>
      <div className="opacity-75 text-xs leading-tight">{label}</div>
    </div>
  )
}

function DevCard({ rec, rank }: { rec: Recommendation; rank: number }) {
  const exp = rec.explanation
  const signals = exp?.signals ?? {}

  const signalKeys = Object.keys(signals)

  return (
    <div className="border border-gray-700 rounded-lg p-4 mb-3 bg-gray-800">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-green-800 text-green-300 text-xs flex items-center justify-center font-bold">
            {rank}
          </span>
          <span className="font-semibold text-gray-200">@{rec.developer}</span>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold text-green-400">
            {(rec.final_score * 100).toFixed(0)}
          </div>
          <div className="text-xs text-gray-500">score</div>
        </div>
      </div>

      <ScoreBar value={rec.final_score} />

      {exp?.summary && (
        <p className="text-xs text-gray-400 mt-2 leading-relaxed">{exp.summary}</p>
      )}

      <div className="flex gap-3 mt-2 text-xs text-gray-500">
        <span>✅ {exp?.resolved_total ?? 0} resolved</span>
        <span>📂 {exp?.open_issues ?? 0} open</span>
      </div>

      <div className="grid grid-cols-3 gap-1.5 mt-3">
        {signalKeys.slice(0, 6).map((key, i) => {
          const s = signals[key] as SignalDetail
          return (
            <div key={key} title={s.detail}
              className={`${SIGNAL_COLORS[i]} rounded px-1.5 py-1 text-white`}>
              <div className="text-xs font-bold">{(s.value * 100).toFixed(0)}%</div>
              <div className="text-xs opacity-75 leading-tight truncate">
                {key.replace(/_/g, ' ')}
              </div>
            </div>
          )
        })}
      </div>

      {signalKeys.length > 0 && (
        <div className="mt-2 text-xs text-gray-500 italic truncate" title={signals[signalKeys[0]]?.detail}>
          {signals[signalKeys[0]]?.label}
        </div>
      )}
    </div>
  )
}

export default function RecommendationPanel() {
  const repo        = useAppSelector(selectActiveRepo)
  const issueNum    = useAppSelector(selectSelectedIssue)
  const [showBody, setShowBody] = useState(false)
  const [showFactors, setShowFactors] = useState(false)

  const { data, isLoading, error } = useGetRecommendationsQuery(
    { repo, issueNum: issueNum! },
    { skip: !repo || issueNum === null }
  )

  if (!issueNum) return (
    <div className="flex-1 flex items-center justify-center text-gray-600 text-sm">
      ← Select an issue to see recommendations
    </div>
  )

  if (isLoading) return (
    <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
      Computing recommendations…
    </div>
  )

  if (error) return (
    <div className="flex-1 flex items-center justify-center text-red-400 text-sm p-6">
      Could not load recommendations. Build developer profiles first.
    </div>
  )

  const recs = data?.recommendations ?? []

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800 bg-gray-900">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-semibold text-gray-200">#{issueNum}</span>
          {data?.priority && (
            <span className={`text-xs px-2 py-0.5 rounded font-medium border ${
              data.priority.tier === 'Critical' ? 'bg-red-900 text-red-300 border-red-700' :
              data.priority.tier === 'High'     ? 'bg-orange-900 text-orange-300 border-orange-700' :
              data.priority.tier === 'Medium'   ? 'bg-yellow-900 text-yellow-300 border-yellow-700' :
                                                   'bg-green-900 text-green-300 border-green-700'
            }`}>
              {data.priority.tier} · Score {data.priority.score}
            </span>
          )}
          {data?.issue_state && (
            <span className={`text-xs px-2 py-0.5 rounded ${
              data.issue_state === 'closed' ? 'bg-gray-700 text-gray-300' :
              data.issue_state === 'open'   ? 'bg-green-900 text-green-300' :
                                              'bg-gray-700 text-gray-300'
            }`}>{data.issue_state}</span>
          )}
        </div>
        <p className="text-sm text-gray-300 line-clamp-2">{data?.issue_title}</p>

        {data?.issue_labels && data.issue_labels.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {data.issue_labels.slice(0, 5).map((l: string, i: number) => (
              <span key={i} className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">
                {l}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center gap-3 mt-2 text-xs text-gray-500 flex-wrap">
          {data?.issue_author && <span>by @{data.issue_author}</span>}
          {data?.issue_created && <span>created {new Date(data.issue_created).toLocaleDateString()}</span>}
          {data?.issue_closed && data.issue_state === 'closed' && (
            <span>closed {new Date(data.issue_closed).toLocaleDateString()}</span>
          )}
        </div>

        <div className="flex gap-2 mt-3">
          {data?.priority?.factors && data.priority.factors.length > 0 && (
            <button
              className="text-xs px-3 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded transition"
              onClick={() => setShowFactors(!showFactors)}
            >
              {showFactors ? '▲' : '▼'} Priority Factors ({data.priority.factors.length})
            </button>
          )}
          {data?.issue_body && (
            <button
              className="text-xs px-3 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded transition"
              onClick={() => setShowBody(!showBody)}
            >
              {showBody ? '▲' : '▼'} Issue Details
            </button>
          )}
        </div>

        {showFactors && data?.priority?.factors && (
          <div className="mt-2 bg-gray-800 rounded p-3 border border-gray-700">
            <div className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wider">
              Contributing Priority Factors
            </div>
            <ul className="text-xs text-gray-300 space-y-0.5">
              {data.priority.factors.map((f: string, i: number) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="text-green-400 mt-0.5">•</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {showBody && data?.issue_body && (
          <div className="mt-2 bg-gray-800 rounded p-3 border border-gray-700">
            <div className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wider">
              Issue Description
            </div>
            <pre className="text-xs text-gray-300 whitespace-pre-wrap leading-relaxed font-sans max-h-40 overflow-y-auto">
              {data.issue_body}
            </pre>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <h3 className="text-xs text-gray-500 uppercase tracking-wider mb-3 font-medium">
          Top {recs.length} Developer Recommendations
        </h3>
        {recs.length === 0 ? (
          <div className="text-center text-gray-600 text-sm py-8">
            No recommendations. Build developer profiles first via the pipeline.
          </div>
        ) : (
          recs.map((rec, i) => <DevCard key={rec.developer} rec={rec} rank={i + 1} />)
        )}
      </div>
    </div>
  )
}
