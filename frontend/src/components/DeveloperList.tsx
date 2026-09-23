import { useAppSelector } from '../store/hooks'
import { selectActiveRepo } from '../store/uiSlice'
import { useGetDevelopersQuery, useBuildProfilesMutation } from '../store/apiSlice'

export default function DeveloperList() {
  const repo = useAppSelector(selectActiveRepo)
  const { data, isLoading, refetch } = useGetDevelopersQuery(repo, { skip: !repo })
  const [buildProfiles, { isLoading: building }] = useBuildProfilesMutation()

  const devs = data?.developers ?? []

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-800 bg-gray-900 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-gray-200">Developer Profiles</h2>
          <p className="text-xs text-gray-500 mt-0.5">{devs.length} developers with expertise profiles</p>
        </div>
        <div className="flex gap-2">
          <button
            className="text-xs text-gray-400 hover:text-gray-200 border border-gray-700 px-3 py-1.5 rounded"
            onClick={() => refetch()}
          >↻ Refresh</button>
          <button
            className="text-sm bg-green-700 hover:bg-green-600 disabled:opacity-40 text-white px-4 py-1.5 rounded"
            disabled={building || !repo}
            onClick={() => buildProfiles({ repo }).then(() => refetch())}
          >
            {building ? 'Creating…' : '⚙ Create / Refresh Profiles'}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {!isLoading && devs.length === 0 && (
          <div className="text-center text-gray-600 py-8">
            <div className="text-4xl mb-2">👥</div>
            <div className="mb-2">No developer profiles found.</div>
            <div className="text-xs text-gray-600">
              Load a dataset or ingest a repo, then click "Build Profiles".
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {devs.map((dev: any, i: number) => (
            <div key={dev.username} className="bg-gray-800 border border-gray-700 rounded-lg p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-green-700 to-blue-700 flex items-center justify-center text-white font-bold text-sm shrink-0">
                  {dev.username[0]?.toUpperCase()}
                </div>
                <div className="min-w-0">
                  <div className="font-medium text-gray-200 truncate">@{dev.username}</div>
                  <div className="text-xs text-gray-500 truncate">{dev.last_active || 'No activity date'}</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-gray-700 rounded p-2 text-center">
                  <div className="font-bold text-green-400 text-lg">{dev.resolved_count}</div>
                  <div className="text-gray-400">Resolved</div>
                </div>
                <div className="bg-gray-700 rounded p-2 text-center">
                  <div className="font-bold text-yellow-400 text-lg">{dev.open_issues}</div>
                  <div className="text-gray-400">Open</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
