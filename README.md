# GitAssign

**Intelligent Issue Triage & Developer Recommendation for Open-Source Repositories**

B.Tech Major Project — RCOEM Nagpur, CSE (AIML), Session 2026–27  
Guide: **Dr. Rashmi Welekar** (Associate Head, CSE)

GitAssign mines a repository's commit and issue history, builds per-developer expertise profiles, and recommends the right developer for each new issue — with per-signal evidence, workload balancing, and a full evaluation harness.

This is **decision support**: a maintainer previews the recommendation and evidence, then explicitly applies or overrides it.

---

## Quick Start (Docker — recommended)

```bash
# 1. Configure
cp .env.example .env
# Optional but recommended: set GITHUB_TOKEN in .env for higher API rate limits

# 2. Start
docker-compose up --build
```

| Service  | URL |
|----------|-----|
| Dashboard | http://localhost:3000 |
| API       | http://localhost:8000 |
| API docs  | http://localhost:8000/docs |

---

## What you must do after start

### Option A — Load Eclipse JDT (best for evaluation / demo)

```bash
# Download dataset
git clone https://github.com/logpai/bughub /tmp/bughub
# Windows PowerShell example:
# git clone https://github.com/logpai/bughub $env:TEMP\bughub

# BugHub stores this dataset under JDT/eclipse_jdt.csv
cp /tmp/bughub/JDT/eclipse_jdt.csv data/eclipse_jdt.csv

# Load into DB (repo slug: eclipse/jdt)
docker-compose exec backend python scripts/load_bughub.py data/eclipse_jdt.csv eclipse/jdt
```

Then in the dashboard:
1. Type `eclipse/jdt` → **Load Repo Data**
2. **Developers** tab → **Build Profiles**
3. **Issues** tab — use filter **all** / **closed** (bughub bugs are closed historical issues)
4. Click an issue → see top-5 recommendations + evidence
5. **Metrics** tab → **Run Ablation** (after profiles exist)

### Option B — Ingest a live GitHub repo

1. Enter e.g. `pallets/click` in the sidebar
2. Set pages (start with 3–5), click **Ingest from GitHub**
3. Wait for the pipeline status to become **completed**. Ingestion imports GitHub history and scans up to 25 small source files for marked `BUG-*:` demo defects, adding detections to the issue queue.
4. Refresh the issue queue, then **Build Profiles** if needed
5. Profiles are created from contributors and historical issue resolvers. New open issues are previewed for manual recommendation by default. Optional automatic assignment requires explicitly setting `AUTO_ASSIGN_NEW_ISSUES=true` and a write-capable `GITHUB_TOKEN`.
6. Set `GITHUB_TOKEN` in `.env` for 5,000 req/hour (vs 60 without). The token must be allowed to modify issues in the repository.

### Option C - Demo file scan

Use the **Demo Scan** tab to upload a source file and enter a repository slug.
The scanner detects explicit markers such as `BUG-1: incorrect total`, creates
open issues in the local queue, and recommends a historical developer when
profiles exist. For a new repository with no history, it assigns labeled demo
roles (`demo_backend`, `demo_api`, or `demo_qa`).

The same scan runs automatically during GitHub ingestion for up to 25 small
source files. This is a deterministic demo workflow, not a general static
analysis engine; unmarked defects require GitHub Issues or explicit markers.

---

## Local development (without Docker)

Requires **Python 3.11+** (3.11 recommended; 3.13 works with flexible deps) and **Node 18+**.

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python db/init_db.py
uvicorn main:app --reload --port 8000
```

### Frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 — Vite proxies `/api` → `http://localhost:8000`.

### Live issue sync

The local development backend refreshes open issues for every repository already
loaded into the database every 60 seconds. Set `LIVE_SYNC_INTERVAL_SECONDS=0`
to disable this polling, or use a larger interval to reduce GitHub API usage.
The dashboard refreshes its issue list every 60 seconds as well. New issues are
 shown for manual recommendation. By default, GitAssign changes GitHub assignees only after the explicit **Apply to GitHub** action.

Load bughub locally:

```bash
cd backend
python scripts/load_bughub.py ../data/eclipse_jdt.csv eclipse/jdt
```

---

## Project structure

```
gitassign/
├── backend/                 FastAPI, scoring, ingestion, evaluation
├── frontend/                React 18 + TypeScript + Redux Toolkit
├── data/                    SQLite DB, GitHub cache, CSV datasets
├── demo_buggy_service.py    Intentional demo defects for Demo Scan
├── docs/results.md          Ablation results (auto-written)
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Scoring formula

```
S(i, d) = w1·TextSimilarity
         + w2·PastIssueSimilarity
         + w3·ComponentOverlap
         + w4·FileAffinity
         + w5·Recency
         − w6·CurrentWorkload
```

Default weights in `backend/config/weights.json`:
`w1=0.35, w2=0.25, w3=0.15, w4=0.15, w5=0.05, w6=0.05`, `capacity_limit=3`.

Edit the JSON to tune — no retraining needed.

---

## Priority (rule-based)

| Signal | Effect |
|--------|--------|
| crash / blocker / P0 / critical label | +4 → Critical |
| bug / high / data-loss label | +2 → High |
| enhancement / question label | −1 → Low |
| crash / security / CVE keywords in text | +2 / +3 |
| “steps to reproduce” | +0.5 |

Output: **Critical / High / Medium / Low** + score + factor list.

---

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/repos` | List loaded repos |
| GET | `/api/issues?repo=&state=all` | Priority-sorted issues (`open` / `closed` / `all`) |
| GET | `/api/issues/{num}/recommendations?repo=` | Top-K developers + evidence |
| POST | `/api/assign/batch` | Preview workload-aware batch assignments |
| POST | `/api/assign/apply` | Apply previewed assignments to GitHub and record results |
| GET | `/api/developers?repo=` | Developer list |
| GET | `/api/developers/{user}/profile?repo=` | Full profile |
| GET | `/api/pipeline/status?repo=` | Live background ingestion status |
| GET | `/api/evaluation/metrics` | Latest ablation results |
| POST | `/api/evaluation/run` | Trigger ablation (background) |
| POST | `/api/pipeline/ingest` | Ingest GitHub repo (background) |
| POST | `/api/pipeline/build-profiles` | Build profiles (background) |
| POST | `/api/demo/scan` | Scan a file for marked demo bugs and create queue issues |

Interactive docs: http://localhost:8000/docs

---

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

Expected: **42 tests passing**.

---

## Ablation study

| Config | Signals |
|--------|---------|
| A | Text similarity only |
| B | A + component overlap |
| C | B + file affinity |
| D | C + recency |
| E | Full model (all 6 signals) |

```bash
docker-compose exec backend python evaluation/ablation_runner.py eclipse/jdt 2009-01-01 2010-01-01 200
```

Results → `docs/results.md` and the Metrics tab.

Target on Eclipse JDT: ~55–65% Top-5 (published text-only baseline ~54%).

---

## Tech stack

- **Backend:** Python 3.11, FastAPI, SQLite, scikit-learn (TF-IDF), PyGitHub, GitPython
- **Frontend:** React 18, TypeScript, Vite, Redux Toolkit + RTK Query, Tailwind, Recharts
- **Deploy:** Docker Compose + Nginx

No neural nets, no GPU, no model training — deterministic scoring with configurable weights.

---

## Team

| Member | Phase | Owns |
|--------|-------|------|
| Amit Saw (A-09) | Phase 1 | Data ingestion, DB, historical linker |
| Ankit Kolhe (A-10) | Phase 2 | Scoring engine, profiles, explanation |
| Annalhq Shaikh (A-13) | Phase 3 | Evaluation, replay harness, ablation |
| Himanshu Joshi (A-49) | Phase 4 | Dashboard, API, Docker, tests |
| Krish Ramchandani (A-56) | Phase 4 | Assignment engine, integration |

---

## References

1. M. Borg et al., "Adopting Automated Bug Assignment in Practice," *Empirical Software Eng.*, 2024.
2. G. Murphy & D. Cubranic, "Automatic bug triage using text categorization," *SEKE*, 2004.
3. X. Xia et al., "Accurate developer recommendation for bug resolution," *WCRE*, 2013.
4. S. Mani et al., "DeepTriage," *CoDS-COMAD*, 2019.
5. A. M. Dakhel et al., "Dev2vec," *Inf. Softw. Technol.*, 2023.
6. C. Zhou et al., "IssueCourier," *arXiv:2505.11205*, 2025.
7. D. Artchounin, "Tuning ML for automatic bug assignment," KTH thesis, 2017.
8. A. Lamkanfi et al., "Eclipse and Mozilla defect tracking dataset," *MSR*, 2013.
