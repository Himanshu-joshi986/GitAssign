# GitAssign: Real AI Triage + Domain Matching — Implementation Plan

**Goal:** Replace the placeholder "AI layer" (local TF-IDF only) with a working pipeline:

1. Ingest any GitHub repo.
2. Pull its open issues.
3. Classify each open issue (bug / feature / etc. + domains) with Gemini.
4. Find contributors who already have history in that repo.
5. Build cached domain profiles for those contributors — **build once, reuse forever** unless an explicit force rebuild is requested.
6. Match each open issue to the best-suited developer using the LLM classification + cached domain profiles + existing deterministic signals.

**Hard constraints:** no new Python/JS dependencies, no vector DB, no queue service, no model training.
Use only what is already installed: `requests`, SQLite, `fastapi`, existing React/RTK Query.

> Plan file location note: the harness restricts plan writes to `/home/ann/.opencode/plan`, so this plan lives here rather than in the repo's `plan/` directory. It can be copied into the repo after approval.

---

## Design summary

```
GitHub API
   │
   ├─ open issues ──────────────► issues table
   ├─ closed issues + PRs ──────► issues / pull_requests / issue_pr_links
   ├─ contributors ─────────────► repository_developers (+ contributions count)
   └─ commits + files ──────────► commits
                                        │
                                        ▼
                       ┌─────────────────────────────────┐
                       │ 1. Issue classifier (Gemini)    │
                       │    cached in issue_classifications
                       └─────────────────────────────────┘
                                        │
                       ┌─────────────────────────────────┐
                       │ 2. Domain profiler (Gemini)     │
                       │    history evidence per dev     │
                       │    cached in developer_domains  │
                       └─────────────────────────────────┘
                                        │
                                        ▼
                       ┌─────────────────────────────────┐
                       │ 3. Matcher                      │
                       │    existing 6 signals +         │
                       │    domain_match signal (#7)     │
                       └─────────────────────────────────┘
```

### What counts as "previous history" (contributor filter)

A contributor is a real candidate only if at least one is true:

- Has commits in `commits` for the repo (`author = username`).
- Has resolved at least one issue via `issue_pr_links.resolver`.
- Has authored a merged PR linked to a resolved issue.

Plain `/contributors` entries with `contributions = 0` are ignored. Bots (`type = Bot`) are ignored.
This is what makes the recommendation meaningful instead of returning random repository watchers.

### Cache rules (the "once only" requirement)

| Artifact | Table | Cache key | Default behaviour |
| --- | --- | --- | --- |
| Issue classification | `issue_classifications` | `(repo, issue_num)` + `input_hash` | Reuse if hash matches; reclassify only if issue title/body/labels changed, model changed, or `force=true` |
| Developer domain profile | `developer_domains` | `(repo, username)` | **Never recompute if a row exists.** Only `force=true` rebuilds. `evidence_hash` is stored for audit/future opt-in refresh |
| LLM errors | — | — | Fall back to deterministic heuristics; do **not** cache a failed call as final |

`force` is only exposed through the explicit `POST /api/pipeline/analyze` endpoint / UI button. The normal ingest and the live sync never force a rebuild.

---

## Step 0 — Baseline and safety net

1. Run `cd backend && pytest -q` and record the current passing count (README says 45).
2. Keep a copy of `backend/config/weights.json` values in notes.
3. No schema destructive changes: all new tables/columns are additive and created with `IF NOT EXISTS` / `_migrate_add_column`.

**Files:** none.

**Done when:** baseline test suite is green.

---

## Step 1 — Persistence: new cache tables and history columns

### 1.1 `backend/app/db/schema.sql`

Add:

```sql
CREATE TABLE IF NOT EXISTS issue_classifications (
    repo                TEXT NOT NULL,
    issue_num           INTEGER NOT NULL,
    kind                TEXT NOT NULL,              -- bug|feature|docs|test|refactor|performance|security|chore
    domains_json        TEXT NOT NULL DEFAULT '[]', -- [{"name":"backend","confidence":0.8}]
    difficulty          INTEGER DEFAULT 3,          -- 1..5
    severity            TEXT DEFAULT 'medium',      -- low|medium|high|critical
    summary             TEXT,
    required_skills_json TEXT DEFAULT '[]',
    confidence          REAL DEFAULT 0,
    model               TEXT,
    input_hash          TEXT,
    created_at          TEXT NOT NULL,
    PRIMARY KEY (repo, issue_num)
);

CREATE TABLE IF NOT EXISTS developer_domains (
    repo                TEXT NOT NULL,
    username            TEXT NOT NULL,
    domains_json        TEXT NOT NULL DEFAULT '[]', -- [{"name":"backend","weight":0.6,"evidence":"..."}]
    preferred_kinds_json TEXT DEFAULT '[]',
    summary             TEXT,
    evidence_hash       TEXT,
    model               TEXT,
    built_at            TEXT NOT NULL,
    PRIMARY KEY (repo, username)
);

CREATE INDEX IF NOT EXISTS idx_issue_classifications_repo
    ON issue_classifications(repo);
CREATE INDEX IF NOT EXISTS idx_developer_domains_repo
    ON developer_domains(repo);
```

Also extend existing tables:

- `issues.state_reason TEXT` — lets us exclude `not_planned` closed issues from history.
- `pull_requests.author TEXT` — the PR author is the real resolver, not the merger.
- `repository_developers.contributions INTEGER DEFAULT 0` — GitHub contributor count.

### 1.2 `backend/app/db/init_db.py`

Add migrations:

```python
_migrate_add_column(conn, "issues", "state_reason", "TEXT")
_migrate_add_column(conn, "pull_requests", "author", "TEXT")
_migrate_add_column(conn, "repository_developers", "contributions", "INTEGER DEFAULT 0")
```

`create table if not exists` in `schema.sql` is already executed on startup, so the new tables need no migration step.

**Done when:** `python -m app.db.init_db` works on both a fresh DB and the existing `data/gitassign.db`.

---

## Step 2 — LLM client and taxonomy (no new dependencies)

### 2.1 New file: `backend/app/core/llm_client.py`

Responsibilities:

- Read config from environment:
  - `GEMINI_API_KEY` (empty = disabled)
  - `GEMINI_MODEL` (default `gemini-2.5-flash`)
  - `GEMINI_BASE_URL` (default `https://generativelanguage.googleapis.com/v1beta`)
  - `LLM_TIMEOUT_SECONDS` (default `60`)
  - `LLM_MAX_RETRIES` (default `3`)
  - `LLM_MAX_ISSUES_PER_RUN` (default `50`)
  - `LLM_ENABLED` (default `true`; key required)
- `is_enabled() -> bool`
- `generate_json(prompt: str, system: str | None = None) -> dict | None`
  - Uses existing `requests.post`.
  - Gemini endpoint: `POST {base}/models/{model}:generateContent?key=...`
  - Body: `{"contents": [{"parts": [{"text": prompt}]}], "systemInstruction": ..., "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}`
  - Strips markdown fences before `json.loads`.
  - Retries on HTTP 429/5xx with exponential backoff (`1s, 2s, 4s`); returns `None` on permanent failure.
  - Logs `[llm] model=... ok/failed` without printing the API key or prompt body.
- Optional simple in-process call counter for pipeline status (`llm_calls`).

### 2.2 New file: `backend/config/domains.json`

Fixed taxonomy so profiles and issues use the same vocabulary:

```json
{
  "domains": [
    {"name": "backend", "description": "server logic, services, business rules"},
    {"name": "frontend", "description": "UI, components, client state, styling"},
    {"name": "api", "description": "REST/GraphQL endpoints, contracts, SDKs"},
    {"name": "database", "description": "schemas, queries, migrations, persistence"},
    {"name": "auth", "description": "authentication, authorization, sessions, permissions"},
    {"name": "security", "description": "vulnerabilities, crypto, input validation, CVEs"},
    {"name": "infrastructure", "description": "Docker, Kubernetes, deployment, cloud"},
    {"name": "ci-cd", "description": "pipelines, release automation, build tooling"},
    {"name": "testing", "description": "test suites, fixtures, QA automation"},
    {"name": "docs", "description": "documentation, guides, examples"},
    {"name": "performance", "description": "latency, memory, profiling, optimization"},
    {"name": "data-ml", "description": "data processing, analytics, ML, statistics"},
    {"name": "mobile", "description": "Android, iOS, React Native, Flutter"},
    {"name": "networking", "description": "HTTP clients, sockets, protocols, proxies"},
    {"name": "developer-tools", "description": "CLI, linting, formatting, editor tooling"}
  ]
}
```

### 2.3 New file: `backend/app/core/domain_taxonomy.py`

- `load_domains()` — cached read of `config/domains.json`.
- `normalise_domains(raw)`:
  - Accepts strings or `{"name": ...}` objects.
  - Lowercases, maps aliases (`backend/api`, `front-end`, `db`, `devops` → canonical names).
  - Drops unknown names; caps at 3; normalises weights to sum to 1.
- `domain_match(issue_domains, dev_domains) -> float`:
  ```python
  # issue_domains: [{"name": "backend"}, ...] or ["backend"]
  # dev_domains:   {"backend": 0.6, "database": 0.4}
  sum(min(dev_domains.get(name, 0), 1) for each issue domain) / len(issue_domains)
  ```
- Deterministic fallbacks (used when LLM is disabled or fails):
  - `heuristic_domains(title, body, labels, files)` — keyword/path map:
    - `.tsx/.jsx/.css` → frontend
    - `docker|k8s|deploy` → infrastructure
    - `sql|migration|database` → database
    - `auth|login|token|oauth` → auth
    - `cve|security|vulnerab` → security
    - `.github/workflows|ci|build` → ci-cd
    - `test|pytest|jest` → testing
    - `readme|docs` → docs
    - `slow|memory|leak|performance` → performance
    - `android|ios|flutter` → mobile
    - default → backend if Python/Go/Java files else frontend if JS/TS files
  - `heuristic_kind(title, body, labels)`:
    - `bug|crash|error|broken` → bug
    - `feature|enhancement|request` → feature
    - `security|cve` → security
    - `perf|slow|memory` → performance
    - `docs|typo` → docs
    - `test` → test
    - `refactor` → refactor
    - default → chore
  - `heuristic_classification(...)` returns the same shape as the LLM output with `model="heuristic"`.

**Done when:** importing `domain_taxonomy` works with and without `config/domains.json`; heuristics produce valid taxonomy names.

---

## Step 3 — Issue classification with cache

### New file: `backend/app/core/issue_classifier.py`

Public API:

- `CLASSIFIER_PROMPT_VERSION = "v1"`
- `classify_issue(repo, issue, force=False) -> dict`
- `classify_open_issues(repo, force=False, limit=None, progress=None) -> dict`
- `load_classifications(repo) -> dict[int, dict]`
- `ensure_classified(repo, issue) -> dict` (on-demand path for a single issue click)

Implementation:

1. Build `input_hash = sha256(model + prompt_version + title + body[:4000] + labels).hexdigest()`.
2. Read the `issue_classifications` row:
   - If row exists and `input_hash` matches and `force` is false → return cached row immediately (**zero LLM calls**).
   - If cached `model == "heuristic"` and Gemini is now enabled → retry with LLM.
3. Build the prompt:

```
System: You are a senior open-source issue triage analyst. Return ONLY valid JSON.

User:
Allowed domains: <name: description list>
Issue:
  repo: {repo}
  number: #{number}
  title: {title}
  labels: {labels}
  body: {body truncated to 4000 chars}

Return:
{
  "kind": "bug|feature|docs|test|refactor|performance|security|chore",
  "domains": [{"name": "<allowed domain>", "confidence": 0.0-1.0}],
  "difficulty": 1-5,
  "severity": "low|medium|high|critical",
  "summary": "one sentence, max 200 chars",
  "required_skills": ["short skill names"],
  "confidence": 0.0-1.0
}
Rules: 1-3 domains, only from the allowed list.
```

4. Validate/coerce output:
   - Unknown kind → `chore`.
   - Unknown domains → dropped; empty → heuristic domains.
   - Difficulty clamp 1..5; severity from allowed set.
   - Summary truncated to 300 chars.
5. On `None` (no key/network/parse error) → `heuristic_classification(...)`, `model="heuristic"`.
6. Upsert into `issue_classifications`, commit.
7. `classify_open_issues`:
   - Query `issues WHERE repo=? AND state='open' ORDER BY created_at DESC`.
   - Skip cached; cap at `limit` or `LLM_MAX_ISSUES_PER_RUN` (0 = no cap).
   - Sequential calls are enough; optional `ThreadPoolExecutor(max_workers=2)` only if needed later.
   - Every 10 issues update the pipeline status message.
   - Return `{"classified": n, "cached": n, "failed": n, "llm_calls": n}`.

**Cache proof:** a second `classify_open_issues(repo)` must issue zero LLM calls and return the same counts.

**Done when:** with `GEMINI_API_KEY` unset the pipeline still completes using heuristics; with a mock `generate_json` the row is stored and re-used.

---

## Step 4 — Correct contributor history and resolver attribution

### 4.1 `backend/app/ingestion/github_fetcher.py`

- `fetch_contributors`: keep existing shape; it already contains `contributions`.
- `fetch_pull_requests`: no change to fetch; ensure the raw payload's `user.login` is available to the loader.
- `fetch_issues`: no change, but open-issue fetch already uses `force_refresh=True` in the pipeline.

### 4.2 `backend/app/ingestion/db_loader.py`

- `upsert_repository_developers`: write `contributions`.
- `upsert_pull_requests`: write `author = pr.get("user", {}).get("login")`, keep `merged_by`.
- `upsert_issues`: write `state_reason = i.get("state_reason")`.

### 4.3 `backend/app/ingestion/historical_linker.py`

Fix the biggest correctness bug: today `resolver` is set to the **merger**, not the author.

- `link_via_pr_bodies`: resolver = PR `author` (fall back to `merged_by` only if author is missing).
- `link_via_commit_messages`: unchanged.
- Profile builder excludes issues with `state_reason = 'not_planned'`.

### 4.4 `backend/app/core/profile_builder.py`

- Candidate query:
  ```sql
  SELECT username FROM repository_developers
  WHERE repo=? AND contributions > 0
  UNION
  SELECT resolver FROM issue_pr_links WHERE repo=? AND resolver IS NOT NULL
  UNION
  SELECT author FROM commits WHERE repo=? AND author != ''
  ```
- Build a profile only if the developer has at least one commit or one resolved issue.
- Keep `build_profiles(..., persist=False)` replay behaviour untouched.
- Existing cached developer profiles are still refreshed here (this is cheap and deterministic); only the **LLM domain profile** is "once only".

**Done when:** for a live repo, `resolved_count`/`files_json` reflect the actual PR authors and not maintainers who clicked merge.

---

## Step 5 — Cached developer domain profiles

### New file: `backend/app/core/domain_profiler.py`

Public API:

- `DOMAIN_PROMPT_VERSION = "v1"`
- `collect_evidence(repo, username) -> dict`
- `build_domain_profile(repo, username, force=False) -> dict | None`
- `build_domain_profiles(repo, force=False, limit=None) -> dict`
- `load_domain_profiles(repo) -> dict[str, dict]`
- `ensure_domain_profiles(repo, usernames=None) -> dict` (on-demand, only missing users)

Evidence gathering (SQL, no extra API calls):

```python
{
  "username": "...",
  "resolved_issues": [{"number": 12, "title": "...", "labels": ["bug"], "body": "first 300 chars"}],  # max 20
  "commit_messages": ["fix: ...", "..."],                                                          # max 30
  "top_files": ["src/db/pool.py", "..."]                                                           # max 20
  "pr_titles": ["..."]                                                                             # max 15, authored merged PRs
  "resolved_count": 17,
  "commit_count": 143
}
```

Cache logic:

1. Compute `evidence_hash = sha256(model + prompt_version + canonical_json(evidence))`.
2. Read `developer_domains`:
   - **If a row exists and `force` is false → return it without calling the LLM**, regardless of hash. This is the strict "once only" behaviour.
   - `evidence_hash` is stored so a future opt-in refresh can detect changes.
3. Prompt:

```
System: You build evidence-based developer expertise profiles. Return ONLY valid JSON.

User:
Allowed domains: <name: description list>
Developer: {username}
Evidence:
  resolved issues: ...
  commit messages: ...
  files: ...
  merged PRs: ...

Return:
{
  "domains": [{"name": "<allowed>", "weight": 0.0-1.0, "evidence": "short reason"}],
  "preferred_kinds": ["bug", "feature"],
  "summary": "one sentence, max 200 chars"
}
Rules: 1-4 domains, weights sum to 1.0, only allowed names.
```

4. Validate with `normalise_domains`; on failure/heuristic:
   - Score domains from evidence using the same keyword/path heuristics, weighted by file/commit frequency.
   - `model="heuristic"`.
5. Upsert into `developer_domains` with `built_at = now`.
6. `build_domain_profiles`:
   - Candidates = contributors with history (Step 4 query).
   - Skip any candidate that already has a row unless `force`.
   - Batch up to 5 developers per LLM call using a JSON array response to reduce cost:

     ```
     Return: {"profiles": [{"username": "...", "domains": [...], ...}, ...]}
     ```
   - If batch output fails validation, retry those developers individually; then fall back to heuristics.
   - Cap per run with `LLM_MAX_PROFILES_PER_RUN` (default `100`).
   - Return `{"built": n, "cached": n, "heuristic": n, "llm_calls": n}`.

### Behaviour on new contributors

- New contributor with no domain row → built on the next `analyze` run or on-demand when they appear as a candidate.
- Existing contributor → reused forever.
- Explicit `force` → rebuild everyone (or one user if a username is supplied).

**Done when:** run twice; second run reports `built: 0, cached: N` and makes zero LLM calls.

---

## Step 6 — Matching: add the domain signal

### 6.1 `backend/config/weights.json`

Add and rebalance (sum = 1.0):

```json
{
  "w1_text_similarity": 0.30,
  "w2_past_issue_similarity": 0.20,
  "w3_component_overlap": 0.15,
  "w4_file_affinity": 0.10,
  "w5_recency": 0.05,
  "w6_workload_penalty": 0.05,
  "w7_domain_match": 0.15,
  "capacity_limit": 3
}
```

Set `w7_domain_match` to `0.0` to reproduce the old ranking exactly.

### 6.2 `backend/app/core/scoring_engine.py`

- `DEFAULT_WEIGHTS` gets `w7_domain_match: 0.0`.
- `load_weights()` merges file values over defaults so old configs never `KeyError`.
- Add:
  ```python
  def domain_match(issue_domains, dev_domains) -> float:
      # implemented in domain_taxonomy
  ```
- `ScoringEngine.score`:
  - Read `issue["classification"]["domains"]` and `profile["domains_json"]`.
  - `s7 = domain_match(...)`.
  - Add `w7 * s7` to the combined score.
  - Return `s7_domain` in the signal dict.
- `fit()` unchanged.

### 6.3 `backend/app/core/assignment_engine.py`

- `get_single_recommendation`:
  1. `classification = ensure_classified(repo, issue_dict)` (one cached LLM call at most).
  2. Load domain profiles; call `ensure_domain_profiles(repo, usernames=[p["username"] ...])` for missing ones, capped to avoid a UI request timing out. If the cap is exceeded, use what is cached; missing domains contribute `0`.
  3. Attach `classification` to the extracted issue and `domains_json` to each profile.
  4. Rank with the engine.
  5. Return `classification` and each developer's top domains in the response.
- `assign_batch`: same enrichment once for the whole batch, then rank as today.
- Persist top-K into the existing unused `recommendations` table with `signals_json` (cheap audit trail).
- Keep the workload-aware capacity loop intact.

### 6.4 `backend/app/core/explanation_engine.py`

- Add a `domain` signal:
  ```python
  "domain": {
      "value": s7,
      "label": "Domain fit: backend, database",
      "detail": "Issue domains: [...]; developer domains: [...]"
  }
  ```
- Include `matched_domains` and `classification` in the explanation summary.
- Keep the existing `ai_context` (local TF-IDF evidence) for historical proof.

**Done when:** a backend issue ranks a backend-heavy contributor above an equally active docs-only contributor, and the response shows the domain reason.

---

## Step 7 — Pipeline orchestration and API

### 7.1 `backend/app/main.py`

Add one shared helper:

```python
def _analyze_repo(repo, force=False, max_issues=None):
    from app.core.issue_classifier import classify_open_issues
    from app.core.domain_profiler import build_domain_profiles
    classified = classify_open_issues(repo, force=force, limit=max_issues)
    domains = build_domain_profiles(repo, force=force)
    return {**classified, **domains}
```

Ingest pipeline becomes:

1. Fetch closed + open issues, PRs, commits, contributors.
2. Upsert everything.
3. `run_all_strategies(repo)`.
4. `build_profiles(repo)` (deterministic, cheap).
5. `_analyze_repo(req.repo)` (LLM classification + domain profiles).
6. `_scan_ingested_source` (keep the demo fixture last, it is unrelated).
7. Status includes: `issues`, `open_issues`, `contributors`, `classified`, `domain_profiles`, `llm_calls`, `llm_enabled`.

Important: if `GEMINI_API_KEY` is missing, the pipeline still completes and reports `"llm_enabled": false`; heuristics fill the data.

New endpoint:

```http
POST /api/pipeline/analyze
Body: {"repo": "owner/name", "force": false, "max_issues": 50}
→ {"status": "started", "repo": ..., "llm_enabled": true|false}
```

Background task; updates `_pipeline_status` with the same stage messages.

Other endpoint changes:

- `GET /api/issues`: attach `classification` from `load_classifications(repo)`. Do not trigger LLM calls from a list request.
- `GET /api/issues/{num}/recommendations`: include `classification`; enrich profiles; return `domains` per developer.
- `GET /api/developers`: include `domains` (top 2–3 names) and `summary`.
- `GET /api/developers/{username}/profile`: parse `domains_json`.
- `GET /api/ai/status?repo=`: optional small endpoint returning `{llm_enabled, model, classified, missing, domain_profiles}` for the UI badge.
- `DELETE /api/repos/{repo}`: also clear `issue_classifications` and `developer_domains`.

### 7.2 Live sync

`_sync_open_issues` should call `_analyze_repo(repo)` after `build_profiles`. The issue classifier only calls the LLM for **new or edited** issues, so a 60s poll is safe. Domain profile builder skips all existing rows.

### 7.3 Configuration

`.env.example`:

```bash
# Gemini (LLM triage + domain profiles). Leave empty to use deterministic fallbacks.
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
LLM_ENABLED=true
LLM_TIMEOUT_SECONDS=60
LLM_MAX_ISSUES_PER_RUN=50
LLM_MAX_PROFILES_PER_RUN=100
```

`compose.yaml`: pass the same variables through to the backend service.

**Done when:** `POST /api/pipeline/ingest` on a small real repo produces classifications and domain profiles with a key, and completes with heuristics without a key.

---

## Step 8 — Minimal frontend surfacing

No new packages, no new screens.

### `frontend/src/store/apiSlice.ts`

- Extend types:
  - `Issue.classification?: { kind, domains: {name,confidence}[], severity, difficulty, summary }`
  - `Recommendation.domains?: {name, weight}[]`, `domain_summary?: string`
  - `Developer.domains?: string[]`, `domain_summary?: string`
- Add endpoints:
  - `analyzeRepo: POST /pipeline/analyze` (invalidates `Issues`, `Profiles`)
  - `getAiStatus: GET /ai/status?repo=` (optional, for a small badge)

### `frontend/src/components/DeveloperList.tsx`

- Add an **AI analyze** button next to **Build profiles** (calls `analyzeRepo`).
- Show top 2–3 domain chips on each developer card.
- Distinguish "Profiles" (history counts) from "AI domains" (cached expertise summary).

### `frontend/src/components/RecommendationPanel.tsx`

- Header chips: issue `kind`, `severity`, and domains.
- Show the new `domain` signal in the signal grid (it already renders every signal dynamically).
- On each developer card, show their top domains next to `resolved/open`.

### `frontend/src/components/IssueQueue.tsx`

- Small `kind` badge next to the priority tier when `classification` exists.
- No extra fetch; data comes from `/api/issues`.

### `frontend/src/components/layout/sidebar.tsx`

- Pipeline status already shows issues/contributors. Add `classified` and `domain profiles` counts when present.
- Keep the "LLM disabled / heuristic mode" visible when `llm_enabled` is false.

**Done when:** a user can see *why* an issue was classified and *what* a developer is good at, without leaving the current views.

---

## Step 9 — Tests (all offline)

### New file: `backend/tests/test_ai_pipeline.py`

Use `monkeypatch` to avoid network calls.

1. `test_heuristic_classification_never_returns_unknown_domains`
2. `test_classification_cache_skips_second_llm_call`
   - Monkeypatch `llm_client.generate_json`, count calls.
   - Call `classify_issue` twice; assert `calls == 1` and identical rows.
3. `test_classification_reclassifies_when_input_changes`
   - Change title; assert a second LLM call.
4. `test_domain_profile_is_built_once`
   - Monkeypatch the batch LLM call; run `build_domain_profiles` twice; assert second run `built == 0` and `calls` unchanged.
5. `test_domain_profile_force_rebuilds`
   - `force=True` triggers one more call.
6. `test_domain_match_scores_overlap`
   - `["backend"]` vs `{"backend": 0.8}` ≈ 0.8; empty issue domains → 0.
7. `test_scoring_includes_domain_signal`
   - Same profile, classification with/without matching domain → higher score with domain.
8. `test_llm_failure_falls_back_to_heuristic`
   - `generate_json` returns `None`; classification row `model == "heuristic"`, no exception.
9. `test_recommendations_include_classification`
   - Seed an issue + profile, call the API, assert `classification` and `s7_domain` exist.

### Existing tests

- `test_core.py` should still pass: domain defaults are 0 when absent.
- `test_api.py` should still pass: new fields are additive.
- Ensure no test requires `GEMINI_API_KEY`; unset/blank in test env.

**Done when:** full suite green offline, and no test makes a real HTTP call.

---

## Step 10 — Docs and end-to-end verification

### Docs

- `README.md`:
  - Replace "No neural networks / no model training" with: deterministic scoring + optional LLM triage (Gemini).
  - Add `GEMINI_API_KEY` to configuration table.
  - Document the new `POST /api/pipeline/analyze` endpoint and the cache guarantees.
  - Explain heuristic fallback when no key is configured.
- `CONTRIBUTING.md`: add a line about not committing keys and using `.env`.
- `.env.example` and `compose.yaml` updated as above.

### Manual end-to-end run

```bash
# 1. Start fresh-ish
cd backend
pytest -q

# 2. With a key
export GEMINI_API_KEY=...
uvicorn app.main:app --port 8000

# 3. Small repo first
curl -X POST localhost:8000/api/pipeline/ingest \
  -H 'content-type: application/json' \
  -d '{"repo":"pallets/click","max_pages":2}'

# 4. Poll status until completed
curl 'localhost:8000/api/pipeline/status?repo=pallets/click'

# 5. Inspect open issues + classifications
curl 'localhost:8000/api/issues?repo=pallets/click&state=open'

# 6. Re-run analysis: must be cache-only
curl -X POST localhost:8000/api/pipeline/analyze \
  -H 'content-type: application/json' \
  -d '{"repo":"pallets/click"}'
# expect classified=0, domain_profiles built=0
```

### Acceptance checklist

- [ ] Ingest works for an arbitrary public repo with open issues.
- [ ] Open issues are classified into `kind` + 1–3 taxonomy domains.
- [ ] Classification is cached; a second run makes zero LLM calls for unchanged issues.
- [ ] Contributors without history are excluded from profiles/candidates.
- [ ] Domain profiles are built only for contributors with previous history.
- [ ] Domain profiles are built once and reused; only `force=true` rebuilds.
- [ ] Recommendations show domain fit and existing evidence signals.
- [ ] Removing a repo clears classifications and domain profiles too.
- [ ] The app works with `GEMINI_API_KEY` unset (heuristic fallback, clearly labelled).
- [ ] No new dependencies in `requirements.txt` / `package.json`.
- [ ] Existing + new tests pass offline.

---

## Suggested commit order

1. `feat(db): add issue classification and developer domain caches`
2. `feat(ai): add Gemini JSON client, taxonomy, and heuristic fallbacks`
3. `feat(triage): classify open issues with cached LLM results`
4. `fix(ingestion): attribute issue resolution to PR authors and filter contributors by history`
5. `feat(profiles): build cached developer domain profiles`
6. `feat(matching): add domain-match signal to ranking and explanations`
7. `feat(api): orchestrate analysis in ingest and expose cached classification/domains`
8. `feat(ui): surface AI classification, domains, and analysis action`
9. `test/docs: cover caching/fallbacks and document Gemini setup`

## Explicit non-goals (keep it minimal)

- No embeddings/vector database; Gemini does classification, SQLite caches it.
- No automatic GitHub assignment changes; the existing preview → apply flow remains.
- No LLM-generated comments or autonomous bot behaviour.
- No re-architecture of the evaluation harness. Replay ignores the domain signal when no domain cache exists, so old ablation numbers remain reproducible with `w7_domain_match: 0`.
- No streaming/progress UI; the existing 2s pipeline poll is enough.
