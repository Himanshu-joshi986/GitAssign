import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'

export interface Issue {
  id: number
  repo: string
  number: number
  title: string
  body: string
  labels: string[]
  state: string
  created_at: string
  priority?: {
    tier: 'Critical' | 'High' | 'Medium' | 'Low'
    score: number
    factors: string[]
    color: string
  }
}

export interface SignalDetail {
  value: number
  label: string
  detail: string
}

export interface Recommendation {
  developer: string
  final_score: number
  s1_text: number
  s2_past: number
  s3_component: number
  s4_file: number
  s5_recency: number
  s6_workload: number
  explanation: {
    summary: string
    signals: Record<string, SignalDetail>
    open_issues: number
    resolved_total: number
  }
}

export interface Assignment {
  issue_num: number
  issue_title: string
  priority_tier: string
  assigned_to: string
  score: number
  at_capacity: boolean
  current_load: number
  explanation: Recommendation['explanation']
  top3: Recommendation[]
  status?: string
  error?: string
}

export interface AblationResult {
  config: string
  config_name: string
  top1: number
  top3: number
  top5: number
  mrr: number
  n: number
}

export interface DemoBug {
  bug_id: string
  issue_num: number
  title: string
  filename: string
  line: number
  assigned_to: string
  assignment_source: 'historical_profile' | 'demo_fallback'
  evidence: string
}

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({ baseUrl: '/api' }),
  tagTypes: ['Issues', 'Profiles', 'Metrics', 'Repos'],
  endpoints: (builder) => ({

    // Repos
    getRepos: builder.query<{ repos: { repo: string; issue_count: number }[] }, void>({
      query: () => '/repos',
    }),

    removeRepo: builder.mutation<{ status: string; repo: string }, string>({
      query: (repo) => ({ url: `/repos/${encodeURIComponent(repo)}`, method: 'DELETE' }),
      invalidatesTags: ['Issues', 'Profiles', 'Repos'],
    }),

    // Issues
    getIssues: builder.query<{ issues: Issue[]; total: number }, { repo: string; state?: string }>({
      query: ({ repo, state = 'all' }) => `/issues?repo=${encodeURIComponent(repo)}&state=${state}&limit=200`,
      providesTags: ['Issues'],
    }),

    // Recommendations for one issue
    getRecommendations: builder.query<
      {
        recommendations: Recommendation[]
        issue_title: string
        issue_body: string
        issue_state: string
        issue_created: string
        issue_closed: string
        issue_author: string
        issue_labels: string[]
        priority: Issue['priority']
      },
      { repo: string; issueNum: number }
    >({
      query: ({ repo, issueNum }) => `/issues/${issueNum}/recommendations?repo=${encodeURIComponent(repo)}&top_k=5`,
    }),

    // Developers list
    getDevelopers: builder.query<{ developers: any[]; total: number }, string>({
      query: (repo) => `/developers?repo=${encodeURIComponent(repo)}`,
      providesTags: ['Profiles'],
    }),

    // Batch assign
    batchAssign: builder.mutation<
      { assignments: Assignment[]; total: number },
      { repo: string; issue_nums: number[]; capacity: number }
    >({
      query: (body) => ({ url: '/assign/batch', method: 'POST', body }),
    }),

    applyBatchAssign: builder.mutation<
      { assignments: Assignment[]; total: number },
      { repo: string; issue_nums: number[]; capacity: number; assignments?: Assignment[] }
    >({
      query: (body) => ({ url: '/assign/apply', method: 'POST', body }),
      invalidatesTags: ['Issues', 'Profiles'],
    }),

    // Evaluation metrics
    getMetrics: builder.query<{ results: Record<string, AblationResult> }, string | undefined>({
      query: (repo) => `/evaluation/metrics${repo ? `?repo=${encodeURIComponent(repo)}` : ''}`,
      providesTags: ['Metrics'],
    }),

    getPipelineStatus: builder.query<{
      repo: string; status: 'idle' | 'queued' | 'running' | 'completed' | 'failed'
      message: string; updated_at?: string; issues?: number; contributors?: number
    }, string>({
      query: (repo) => `/pipeline/status?repo=${encodeURIComponent(repo)}`,
    }),

    demoScan: builder.mutation<{
      repo: string; filename: string; bugs: DemoBug[]; profiles_used: number; message: string
    }, { repo: string; filename: string; content: string }>({
      query: (body) => ({ url: '/demo/scan', method: 'POST', body }),
    }),

    // Run evaluation
    runEvaluation: builder.mutation<{ status: string; message: string }, {
      repo: string; train_before: string; test_after: string; max_issues: number
    }>({
      query: (body) => ({ url: '/evaluation/run', method: 'POST', body }),
      invalidatesTags: ['Metrics'],
    }),

    // Ingest repo
    ingestRepo: builder.mutation<{ status: string; message: string }, { repo: string; max_pages: number }>({
      query: (body) => ({ url: '/pipeline/ingest', method: 'POST', body }),
      invalidatesTags: ['Issues', 'Profiles', 'Repos'],
    }),

    // Build profiles
    buildProfiles: builder.mutation<{ status: string }, { repo: string }>({
      query: (body) => ({ url: '/pipeline/build-profiles', method: 'POST', body }),
      invalidatesTags: ['Profiles'],
    }),
  }),
})

export const {
  useGetReposQuery,
  useRemoveRepoMutation,
  useGetIssuesQuery,
  useGetRecommendationsQuery,
  useGetDevelopersQuery,
  useBatchAssignMutation,
  useApplyBatchAssignMutation,
  useGetMetricsQuery,
  useGetPipelineStatusQuery,
  useDemoScanMutation,
  useRunEvaluationMutation,
  useIngestRepoMutation,
  useBuildProfilesMutation,
} = api
