<div align="center">

# GitAssign

**Issue triage and developer recommendation for open-source repositories.**

GitAssign mines a repository's commit and issue history, builds per-developer
expertise profiles, and recommends the best person for each new issue — with
per-signal evidence, workload balancing, and a reproducible evaluation harness.

[![Python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

</div>

---

## Overview

Assigning issues manually does not scale. GitAssign turns repository history
into an explainable recommendation:

- **Who** has worked on similar issues, components, and files?
- **What evidence** supports the match?
- **Is the developer available**, or already at capacity?
- **How good** is the whole ranking compared with simpler baselines?

GitAssign is **decision support**, not an autonomous bot. A maintainer previews
every recommendation and its evidence, then explicitly applies or overrides it.
GitHub writes are opt-in.

> B.Tech Major Project — RCOEM Nagpur, CSE (AIML), Session 2026–27<br>
> Guide: **Dr. Rashmi Welekar** (Associate Head, CSE)

---

## Features

| Capability | Description |
| --- | --- |
| **History ingestion** | Imports issues, pull requests, commits, and contributors from GitHub or a BugHub CSV |
| **Developer profiles** | Builds expertise profiles from resolved issues and file-level commit history |
| **Six-signal scoring** | Combines text similarity, past issues, components, file affinity, recency, and workload |
| **Explainable rankings** | Every recommendation includes per-signal contributions and human-readable reasons |
| **Workload balancing** | Capacity-aware batch assignment with conflict checks |
| **Priority triage** | Rule-based Critical / High / Medium / Low classification with factor evidence |
| **Evaluation harness** | Time-based replay, TF-IDF baseline, and an A–E ablation study |
| **Demo workflow** | Upload a source file with `BUG-*` markers to exercise the full pipeline |
| **Safety first** | Preview by default; applying assignments to GitHub requires an explicit action |

No neural networks, no GPU, and no model training: scoring is deterministic and
weights are configurable at runtime.

---

## How it works

```mermaid
flowchart LR
    A[GitHub API / BugHub CSV] --> B[Ingestion]
    B --> C[(SQLite)]
    C --> D[Developer profiles]
    C --> E[Issue extraction]
    D --> F[Scoring engine]
    E --> F
    F --> G[Recommendations + evidence]
    G --> H{Maintainer review}
    H -->|Apply| I[GitHub assignees]
    H -->|Override| F
    C --> J[Replay / ablation]
    J --> K[docs/results.md]
```

1. **Ingest** issues, pull requests, and commits into a local SQLite database.
2. **Build profiles** that map each developer to components, files, and resolved
   issue history.
3. **Score** every candidate with configurable signals and a workload penalty.
4. **Explain** the ranking, then let a maintainer preview, apply, or override it.
5. **Evaluate** the model with a chronological replay and ablation study.

---

## Repository structure

```text
GitAssign/
├── backend/
│   ├── app/
│   │   ├── core/                 # Scoring, assignment, priority, explanations
│   │   ├── db/                   # SQLite connection, migrations, schema
│   │   ├── evaluation/           # Replay harness, TF-IDF baseline, ablation
│   │   ├── ingestion/            # GitHub fetcher, loaders, historical linker
│   │   └── main.py               # FastAPI application
│   ├── config/weights.json       # Tunable scoring weights
│   ├── scripts/load_bughub.py    # BugHub CSV loader
│   ├── tests/                    # API and core unit tests
│   ├── Dockerfile
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/           # Dashboard views
│   │   ├── store/                # Redux Toolkit store + RTK Query API
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── Dockerfile
│   ├── nginx.conf                # SPA serving + /api reverse proxy
│   └── vite.config.ts
├── data/                         # Runtime SQLite DB and API cache (gitignored)
├── datasets/                     # BugHub CSV datasets
├── docs/results.md               # Generated ablation results
├── examples/                     # Demo fixture for the Demo Scan workflow
├── compose.yaml
├── .env.example
└── README.md
```

---

## Quick start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Compose v2
- Optional: a GitHub token for higher API rate limits

### 1. Configure

```bash
cp .env.example .env
```

Set `GITHUB_TOKEN` in `.env` if you plan to ingest live repositories. Without a
token, GitHub allows 60 requests per hour; with one, 5,000.

### 2. Start the stack

```bash
docker compose up --build
```

| Service | URL |
| --- | --- |
| Dashboard | <http://localhost:3000> |
| API | <http://localhost:8000> |
| API docs (Swagger) | <http://localhost:8000/docs> |

Stop the stack with `docker compose down`.

### 3. Choose a workflow

#### Option A — Load a BugHub dataset (best for evaluation)

The Eclipse JDT dataset is included at `datasets/eclipse_jdt.csv`.

```bash
docker compose exec backend python scripts/load_bughub.py \
    datasets/eclipse_jdt.csv eclipse/jdt
```

Then in the dashboard:

1. Enter `eclipse/jdt` and click **Load Repo Data**.
2. Open **Developers** and click **Build Profiles**.
3. Open **Issues**, select the **all** or **closed** filter, and click an issue.
4. Review the top-5 recommendations and the evidence behind each signal.
5. Open **Metrics** and run the ablation study once profiles exist.

More datasets and download instructions are in [`datasets/README.md`](datasets/README.md).

#### Option B — Ingest a live GitHub repository

1. Enter a repository such as `pallets/click` in the sidebar.
2. Choose how many pages to fetch (start with 3–5), then click **Ingest from GitHub**.
3. Wait for the pipeline status to become **completed**.
4. Build profiles and review the issue queue.

New open issues are previewed for manual assignment. To assign automatically,
set `AUTO_ASSIGN_NEW_ISSUES=true` and provide a token with permission to modify
issues in the target repository.

#### Option C — Scan a demo file

Use the **Demo Scan** tab to upload [`examples/demo_buggy_service.py`](examples/demo_buggy_service.py).
GitAssign detects `BUG-*` markers, creates queued issues, and recommends a
historical developer when profiles exist. This is a deterministic demo fixture,
not a general static-analysis engine.

---

## Local development

Requires **Python 3.11+** and **Node.js 18+**.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.db.init_db
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. Vite proxies `/api` to `http://localhost:8000`.

To serve the built dashboard directly from FastAPI, run `npm run build`; the
bundle is written to `backend/static/` and mounted by the API.

### Live issue sync

In development, the backend refreshes open issues for every loaded repository
once a minute. Set `LIVE_SYNC_INTERVAL_SECONDS=0` to disable polling, or raise
the interval to reduce GitHub API usage.

```bash
# Load a dataset from the backend/ directory
python scripts/load_bughub.py ../datasets/eclipse_jdt.csv eclipse/jdt
```

---

## Configuration

All settings are read from environment variables (or `.env`).

| Variable | Default | Description |
| --- | --- | --- |
| `GITHUB_TOKEN` | _empty_ | Personal access token for live ingestion and GitHub writes |
| `DB_PATH` | `data/gitassign.db` | SQLite database location |
| `CACHE_DIR` | `data/cache` | Raw GitHub API response cache |
| `WEIGHTS_PATH` | `config/weights.json` | Scoring weight configuration |
| `MAX_COMMIT_DETAILS` | `200` | Commit details fetched for file-affinity scoring |
| `LIVE_SYNC_INTERVAL_SECONDS` | `60` | Open-issue polling interval; `0` disables it |
| `AUTO_ASSIGN_NEW_ISSUES` | `false` | Automatically assign new issues during sync |
| `AUTO_ASSIGN_CAPACITY` | `3` | Minimum free capacity for automatic assignment |
| `AUTO_NOTIFY_DEVELOPER` | `false` | Mention the assignee in a GitHub comment |

Scoring weights live in [`backend/config/weights.json`](backend/config/weights.json).
Edit the file and restart, or remount it with Compose — no retraining required.

---

## Scoring model

Each issue–developer pair receives a weighted score:

```text
S(i, d) = w1 · TextSimilarity
        + w2 · PastIssueSimilarity
        + w3 · ComponentOverlap
        + w4 · FileAffinity
        + w5 · Recency
        - w6 · CurrentWorkload
```

| Weight | Default | Signal |
| --- | ---: | --- |
| `w1_text_similarity` | 0.35 | TF-IDF cosine similarity between issue text and resolved issues |
| `w2_past_issue_similarity` | 0.25 | Similarity to the developer's individual resolved issues |
| `w3_component_overlap` | 0.15 | Overlap between issue components and the developer's components |
| `w4_file_affinity` | 0.15 | Commit frequency on files mentioned in the issue |
| `w5_recency` | 0.05 | Time-decayed activity |
| `w6_workload_penalty` | 0.05 | Open assignments relative to `capacity_limit` (default `3`) |

### Priority mapping

| Signal | Effect |
| --- | --- |
| `crash`, `blocker`, `P0`, `critical` labels | +4 → **Critical** |
| `bug`, `high`, `data-loss` labels | +2 → **High** |
| `enhancement`, `question` labels | −1 → **Low** |
| `crash` / `security` / `CVE` keywords | +2 / +3 |
| "steps to reproduce" in the body | +0.5 |

The result is a **Critical / High / Medium / Low** label plus a numeric score
and the list of factors that produced it.

---

## API reference

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/repos` | List loaded repositories |
| `DELETE` | `/api/repos/{repo}` | Remove a repository's local data and cache |
| `GET` | `/api/issues?repo=&state=all` | Priority-sorted issues (`open` / `closed` / `all`) |
| `GET` | `/api/issues/{num}/recommendations?repo=` | Top-K developers with evidence |
| `POST` | `/api/assign/batch` | Preview workload-aware batch assignments |
| `POST` | `/api/assign/apply` | Apply previewed assignments and record results |
| `GET` | `/api/developers?repo=` | List developers |
| `GET` | `/api/developers/{user}/profile?repo=` | Full developer profile |
| `GET` | `/api/pipeline/status?repo=` | Background ingestion status |
| `POST` | `/api/pipeline/ingest` | Ingest a GitHub repository (background) |
| `POST` | `/api/pipeline/build-profiles` | Build profiles (background) |
| `GET` | `/api/evaluation/metrics` | Latest ablation results |
| `POST` | `/api/evaluation/run` | Run the ablation study (background) |
| `POST` | `/api/demo/scan` | Scan a file for `BUG-*` markers and queue issues |

Interactive documentation: <http://localhost:8000/docs>.

---

## Evaluation

The evaluation harness replays history chronologically: profiles are built from
issues resolved before a cutoff date, and recommendations are scored against
issues resolved after it. A TF-IDF baseline is included for comparison.

| Config | Signals enabled |
| --- | --- |
| A | Text similarity only |
| B | A + component overlap |
| C | B + file affinity |
| D | C + recency |
| E | Full model (all six signals) |

```bash
docker compose exec backend python -m app.evaluation.ablation_runner \
    eclipse/jdt 2009-01-01 2010-01-01 200
```

Results are written to [`docs/results.md`](docs/results.md) and displayed in the
**Metrics** tab. The Eclipse JDT target is roughly 55–65% Top-5 accuracy, against
a published text-only baseline of about 54%.

---

## Testing

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

Expected result: **45 tests passing**. CI runs the backend suite and the
frontend build on every push and pull request.

---

## Contributing

Contributions are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) for
the development workflow, commit conventions, and pull-request checklist.

For security issues, follow [`SECURITY.md`](SECURITY.md) instead of opening a
public issue.

---

## Tech stack

| Layer | Technologies |
| --- | --- |
| **Backend** | Python 3.11, FastAPI, SQLite, scikit-learn (TF-IDF), PyGithub, GitPython |
| **Frontend** | React 18, TypeScript, Vite, Redux Toolkit + RTK Query, Tailwind CSS, Recharts |
| **Deployment** | Docker Compose, Nginx |

---

## Team

| Member | Phase | Ownership |
| --- | --- | --- |
| Amit Saw (A-09) | Phase 1 | Data ingestion, database, historical linker |
| Ankit Kolhe (A-10) | Phase 2 | Scoring engine, profiles, explanations |
| Annalhq Shaikh (A-13) | Phase 3 | Evaluation, replay harness, ablation |
| Himanshu Joshi (A-49) | Phase 4 | Dashboard, API, Docker, tests |
| Krish Ramchandani (A-56) | Phase 4 | Assignment engine, integration |

---

## License

Released under the [MIT License](LICENSE).

---

## References

1. M. Borg et al., "Adopting Automated Bug Assignment in Practice," *Empirical Software Engineering*, 2024.
2. G. Murphy and D. Cubranic, "Automatic Bug Triage Using Text Categorization," *SEKE*, 2004.
3. X. Xia et al., "Accurate Developer Recommendation for Bug Resolution," *WCRE*, 2013.
4. S. Mani et al., "DeepTriage," *CoDS-COMAD*, 2019.
5. A. M. Dakhel et al., "Dev2vec," *Information and Software Technology*, 2023.
6. C. Zhou et al., "IssueCourier," *arXiv:2505.11205*, 2025.
7. D. Artchounin, "Tuning Machine Learning for Automatic Bug Assignment," KTH thesis, 2017.
8. A. Lamkanfi et al., "Eclipse and Mozilla Defect Tracking Dataset," *MSR*, 2013.
