# GitAssign — Data Directory

This directory holds:
- `cache/`       — raw GitHub API JSON responses (auto-created, gitignored)
- `gitassign.db` — SQLite database (auto-created, gitignored)
- `*.csv`        — cleaned bughub datasets (you download these)

---

## Quick Dataset Setup (Eclipse JDT — recommended first step)

### Step 1 — Download bughub

```bash
# Linux / macOS
git clone https://github.com/logpai/bughub /tmp/bughub

# Windows PowerShell
git clone https://github.com/logpai/bughub $env:TEMP\bughub
```

Find the Eclipse JDT CSV inside — usually at:
```
/tmp/bughub/Eclipse/EclipseJDT.csv
# or Windows: $env:TEMP\bughub\Eclipse\EclipseJDT.csv
```

### Step 2 — Copy to this directory

```bash
cp /tmp/bughub/Eclipse/EclipseJDT.csv data/eclipse_jdt.csv
# Windows: Copy-Item $env:TEMP\bughub\Eclipse\EclipseJDT.csv data\eclipse_jdt.csv
```

> **Note:** Bughub issues are loaded as `closed`. In the dashboard Issues tab, use the **all** or **closed** filter (not only open).

### Step 3 — Load into GitAssign

```bash
# From the gitassign root:
docker-compose exec backend python scripts/load_bughub.py data/eclipse_jdt.csv eclipse/jdt
```

Or without Docker:
```bash
cd backend
python scripts/load_bughub.py ../data/eclipse_jdt.csv eclipse/jdt
```

### Step 4 — Build profiles

```bash
docker-compose exec backend python -c "
from core.profile_builder import build_profiles
build_profiles('eclipse/jdt')
print('Done')
"
```

### Step 5 — Open the dashboard

Navigate to `http://localhost:3000`, enter `eclipse/jdt` in the repo box, click Load.

---

## Other Available Datasets from bughub

| Dataset | File | Repo slug to use |
|---------|------|------------------|
| Eclipse JDT | EclipseJDT.csv | eclipse/jdt |
| Mozilla Firefox | MozillaFirefox.csv | mozilla/firefox |
| Mozilla Core | MozillaCore.csv | mozilla/core |
| Eclipse Platform | EclipsePlatform.csv | eclipse/platform |
| Thunderbird | MozillaThunderbird.csv | mozilla/thunderbird |

---

## Live GitHub Repositories (via API)

Enter any public repo slug in the dashboard and click **Ingest from GitHub**.
Good starting repos (manageable size):

- `pallets/flask`   — ~4,000 closed issues, clear component structure
- `pallets/click`   — ~1,500 closed issues, good for quick testing
- `psf/requests`    — ~3,000 closed issues, well-labelled
- `django/django`   — large, active, domain-specific expertise visible

**Note:** Set `GITHUB_TOKEN` in `.env` for 5,000 req/hour instead of 60.
