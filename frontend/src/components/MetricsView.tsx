import { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { useAppSelector } from '../store/hooks'
import { selectActiveRepo } from '../store/uiSlice'
import { useGetMetricsQuery, useRunEvaluationMutation, type AblationResult } from '../store/apiSlice'

export default function MetricsView() {
  const repo = useAppSelector(selectActiveRepo)
  const { data, isLoading, refetch } = useGetMetricsQuery(repo, { pollingInterval: 10000 })
  const [runEval, { isLoading: running }] = useRunEvaluationMutation()

  const [trainBefore, setTrainBefore] = useState('2010-01-01')
  const [testAfter,   setTestAfter]   = useState('2010-01-01')
  const [maxIssues,   setMaxIssues]   = useState(200)

  const results = data?.results ?? {}
  const chartData = Object.values(results).map((r: AblationResult) => ({
    name:  r.config,
    label: r.config_name,
    'Top-1':  r.top1,
    'Top-3':  r.top3,
    'Top-5':  r.top5,
    'MRR×100': +(r.mrr * 100).toFixed(1),
  }))

  async function handleRun() {
    await runEval({ repo, train_before: trainBefore, test_after: testAfter, max_issues: maxIssues })
    setTimeout(refetch, 3000)
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 bg-gray-900">
        <h2 className="font-semibold text-gray-200 mb-1">Evaluation Metrics</h2>
        <p className="text-xs text-gray-500">
          Ablation study — five signal configurations evaluated on temporal held-out test set.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {/* Run controls */}
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 mb-6">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Run Evaluation</h3>
          <div className="flex flex-wrap gap-3 items-end">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Train before</label>
              <input type="date"
                className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-gray-200"
                value={trainBefore}
                onChange={e => setTrainBefore(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Test after</label>
              <input type="date"
                className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-gray-200"
                value={testAfter}
                onChange={e => setTestAfter(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Max test issues</label>
              <input type="number" min={10} max={2000}
                className="w-24 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-gray-200"
                value={maxIssues}
                onChange={e => setMaxIssues(Number(e.target.value))} />
            </div>
            <button
              className="bg-green-700 hover:bg-green-600 disabled:opacity-40 text-white text-sm px-4 py-1.5 rounded"
              disabled={running || !repo}
              onClick={handleRun}
            >
              {running ? 'Running…' : '▶ Run Ablation'}
            </button>
            <button
              className="text-xs text-gray-400 hover:text-gray-200"
              onClick={() => refetch()}
            >↻ Refresh</button>
          </div>
          <p className="text-xs text-gray-600 mt-2">
            Evaluation runs in the background. Results update automatically.
          </p>
        </div>

        {isLoading && (
          <div className="text-center text-gray-500 py-8">Loading metrics…</div>
        )}

        {!isLoading && chartData.length === 0 && (
          <div className="text-center text-gray-600 py-8">
            <div className="text-4xl mb-2">📊</div>
            No evaluation results yet. Run the ablation above.
          </div>
        )}

        {chartData.length > 0 && (
          <>
            {/* Chart */}
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 mb-6">
              <h3 className="text-sm font-medium text-gray-300 mb-4">
                Accuracy by Signal Configuration (%)
              </h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                  <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 6 }}
                    labelStyle={{ color: '#d1d5db' }}
                    formatter={(v: number, name: string) => [`${v}%`, name]}
                  />
                  <Legend wrapperStyle={{ color: '#9ca3af', fontSize: 12 }} />
                  <Bar dataKey="Top-1" fill="#16a34a" radius={[3,3,0,0]} />
                  <Bar dataKey="Top-3" fill="#2563eb" radius={[3,3,0,0]} />
                  <Bar dataKey="Top-5" fill="#7c3aed" radius={[3,3,0,0]} />
                  <Bar dataKey="MRR×100" fill="#d97706" radius={[3,3,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Table */}
            <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-700 text-left">
                    <th className="px-4 py-2 text-gray-300 font-medium">Config</th>
                    <th className="px-4 py-2 text-gray-300 font-medium">Signals</th>
                    <th className="px-4 py-2 text-gray-300 font-medium text-right">Top-1</th>
                    <th className="px-4 py-2 text-gray-300 font-medium text-right">Top-3</th>
                    <th className="px-4 py-2 text-gray-300 font-medium text-right">Top-5</th>
                    <th className="px-4 py-2 text-gray-300 font-medium text-right">MRR</th>
                    <th className="px-4 py-2 text-gray-300 font-medium text-right">N</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.values(results).map((r: AblationResult, i) => (
                    <tr key={r.config} className={i % 2 === 0 ? 'bg-gray-800' : 'bg-gray-900/50'}>
                      <td className="px-4 py-2 font-bold text-green-400">{r.config}</td>
                      <td className="px-4 py-2 text-gray-400 text-xs">{r.config_name}</td>
                      <td className="px-4 py-2 text-right text-gray-200">{r.top1}%</td>
                      <td className="px-4 py-2 text-right text-gray-200">{r.top3}%</td>
                      <td className="px-4 py-2 text-right font-semibold text-green-400">{r.top5}%</td>
                      <td className="px-4 py-2 text-right text-gray-200">{r.mrr}</td>
                      <td className="px-4 py-2 text-right text-gray-500">{r.n}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
