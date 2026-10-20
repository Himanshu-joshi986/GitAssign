"""
GitAssign — FastAPI REST service
All endpoints the React frontend consumes.
"""
import os, json, asyncio, hashlib
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()  # also cwd .env

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from db.init_db import init_db, get_conn
from ingestion.db_loader import load_repo
from ingestion.historical_linker import run_all_strategies
from core.issue_extractor import extract
from core.priority_mapper import prioritise_batch, map_priority
from core.profile_builder import build_profiles, load_profiles, load_profile
from core.assignment_engine import assign_batch, get_single_recommendation
from evaluation.ablation_runner import run_ablation, get_latest_results

LIVE_SYNC_INTERVAL = max(float(os.environ.get("LIVE_SYNC_INTERVAL_SECONDS", "60")), 0)
# GitHub writes stay opt-in. Preview and explicit Apply remain the default flow.
AUTO_ASSIGN_NEW_ISSUES = os.environ.get("AUTO_ASSIGN_NEW_ISSUES", "false").lower() in ("1", "true", "yes")
AUTO_NOTIFY_DEVELOPER = os.environ.get("AUTO_NOTIFY_DEVELOPER", "false").lower() in ("1", "true", "yes")
_pipeline_status: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("[startup] GitAssign API ready")
    sync_task = asyncio.create_task(_live_sync_loop()) if LIVE_SYNC_INTERVAL else None
    yield
    if sync_task:
        sync_task.cancel()
        await asyncio.gather(sync_task, return_exceptions=True)


def _sync_open_issues(repo: str):
    from ingestion.github_fetcher import fetch_issues, fetch_contributors
    from ingestion.db_loader import upsert_issues, upsert_repository_developers

    issues = fetch_issues(repo, state="open", force_refresh=True)
    upsert_issues(repo, issues)
    contributors = fetch_contributors(repo)
    upsert_repository_developers(repo, contributors)
    build_profiles(repo)
    if AUTO_ASSIGN_NEW_ISSUES:
        _auto_assign_open_issues(repo)
    return len(issues)


def _set_pipeline_status(repo: str, status: str, message: str, **extra):
    _pipeline_status[repo] = {
        "repo": repo,
        "status": status,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }

def _auto_assign_open_issues(repo: str):
    """Assign every currently unassigned open issue once it has a profile candidate."""
    from ingestion.github_fetcher import GITHUB_TOKEN
    if not GITHUB_TOKEN:
        print(f"[auto-assign] {repo}: skipped because GITHUB_TOKEN is not configured")
        return 0
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM issues WHERE repo=? AND state='open'", (repo,)
    ).fetchall()
    conn.close()
    unassigned = []
    for row in rows:
        try:
            if not json.loads(row["assignees_json"] or "[]"):
                unassigned.append(dict(row))
        except Exception:
            unassigned.append(dict(row))
    if not unassigned:
        return 0
    proposed = assign_batch(unassigned, repo, capacity=int(os.environ.get("AUTO_ASSIGN_CAPACITY", "3")))
    results = _apply_assignments(repo, unassigned, proposed, notify=AUTO_NOTIFY_DEVELOPER)
    assigned = sum(1 for result in results if result.get("status") == "assigned")
    if assigned:
        print(f"[auto-assign] {repo}: assigned {assigned} new issues")
    return assigned


async def _live_sync_loop():
    """Keep open issues current for repositories already loaded locally."""
    while True:
        try:
            conn = get_conn()
            repos = [row[0] for row in conn.execute("SELECT DISTINCT repo FROM issues").fetchall()]
            conn.close()
            for repo in repos:
                try:
                    count = await asyncio.to_thread(_sync_open_issues, repo)
                    print(f"[live-sync] {repo}: {count} open issues refreshed")
                except Exception as exc:
                    print(f"[live-sync] {repo} failed: {exc}")
        except Exception as exc:
            print(f"[live-sync] repository scan failed: {exc}")
        await asyncio.sleep(LIVE_SYNC_INTERVAL)


app = FastAPI(title="GitAssign API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ────────────────────────────────────────────────────────────────────
class IngestRequest(BaseModel):
    repo: str
    max_pages: int = 10

class BuildProfilesRequest(BaseModel):
    repo: str

class BatchAssignRequest(BaseModel):
    repo: str
    issue_nums: list[int]
    capacity: int = 3

class ApplyBatchRequest(BatchAssignRequest):
    """Explicit confirmation for changing GitHub issue assignees."""
    assignments: Optional[list[dict]] = None

class EvalRequest(BaseModel):
    repo: str
    train_before: str = "2010-01-01"
    test_after:   str = "2010-01-01"
    max_issues:   int = 200

class DemoScanRequest(BaseModel):
    repo: str
    filename: str
    content: str

# ── Helper ────────────────────────────────────────────────────────────────────
def _get_issues_from_db(repo: str, state: str = "open", limit: int = 200) -> list:
    conn = get_conn()
    if state == "all":
        rows = conn.execute("""
            SELECT * FROM issues WHERE repo=?
            ORDER BY created_at DESC LIMIT ?
        """, (repo, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM issues WHERE repo=? AND state=?
            ORDER BY created_at DESC LIMIT ?
        """, (repo, state, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}

@app.post("/api/demo/scan")
def demo_scan(req: DemoScanRequest):
    """Find marked demo bugs in a file and recommend a real or demo developer."""
    repo = req.repo.strip()
    filename = req.filename.strip() or "uploaded_file"
    if not repo:
        raise HTTPException(status_code=400, detail="Repository name is required")
    if len(req.content) > 500_000:
        raise HTTPException(status_code=413, detail="Demo files must be smaller than 500 KB")

    import re
    profiles = load_profiles(repo)
    demo_developers = [
        {"username": "demo_backend", "focus": "backend and calculations"},
        {"username": "demo_api", "focus": "API and input handling"},
        {"username": "demo_qa", "focus": "testing and edge cases"},
    ]
    bugs = []
    for line_number, line in enumerate(req.content.splitlines(), start=1):
        match = re.search(r"\bBUG(?:-[A-Z0-9]+)?\s*:\s*(.+)", line, re.IGNORECASE)
        if not match:
            continue
        title = match.group(1).strip()
        issue = {
            "repo": repo,
            "number": line_number,
            "title": title,
            "body": f"Detected in {filename} at line {line_number}: {line.strip()}",
            "labels": json.dumps(["demo", "bug"]),
            "state": "open",
        }
        recommendations = get_single_recommendation(issue, repo, top_k=1) if profiles else []
        if recommendations:
            assigned_to = recommendations[0]["developer"]
            source = "historical_profile"
            evidence = recommendations[0].get("explanation", {}).get("summary", "Historical profile match")
        else:
            fallback = demo_developers[len(bugs) % len(demo_developers)]
            assigned_to = fallback["username"]
            source = "demo_fallback"
            evidence = f"No developer history found; routed to the demo role for {fallback['focus']}."
        issue_num = 900000 + int(hashlib.sha1(f"{filename}:{title}".encode()).hexdigest()[:8], 16) % 99999
        conn = get_conn()
        conn.execute("""
            INSERT INTO issues
                (repo, number, title, body, labels, state, created_at, author, assignees_json)
            VALUES (?, ?, ?, ?, ?, 'open', ?, 'demo-scanner', ?)
            ON CONFLICT(repo, number) DO UPDATE SET
                title=excluded.title, body=excluded.body, labels=excluded.labels,
                state='open', assignees_json=excluded.assignees_json
        """, (
            repo,
            issue_num,
            title,
            f"Detected in {filename} at line {line_number}: {line.strip()}",
            json.dumps(["demo", "bug"]),
            datetime.now(timezone.utc).isoformat(),
            json.dumps([assigned_to]),
        ))
        conn.commit()
        conn.close()
        bugs.append({
            "bug_id": f"DEMO-{len(bugs) + 1}",
            "issue_num": issue_num,
            "title": title,
            "filename": filename,
            "line": line_number,
            "assigned_to": assigned_to,
            "assignment_source": source,
            "evidence": evidence,
        })
    return {
        "repo": repo,
        "filename": filename,
        "bugs": bugs,
        "profiles_used": len(profiles),
        "message": f"Found {len(bugs)} marked bug(s)" if bugs else "No BUG markers found",
    }

def _scan_ingested_source(repo: str) -> int:
    """Scan fetched repository source files and add marked bugs to the queue."""
    from ingestion.github_fetcher import fetch_source_files
    found = 0
    for source in fetch_source_files(repo, max_files=int(os.environ.get("MAX_SOURCE_SCAN_FILES", "25"))):
        result = demo_scan(DemoScanRequest(repo=repo, filename=source["path"], content=source["content"]))
        found += len(result["bugs"])
    return found

# -- Issues -------------------------------------------------------------------

@app.get("/api/issues")
def get_issues(repo: str, state: str = "all", limit: int = 100):
    """Priority-sorted issue list. state: open | closed | all"""
    if state not in ("open", "closed", "all"):
        raise HTTPException(status_code=400, detail="state must be open, closed, or all")
    raw = _get_issues_from_db(repo, state=state, limit=limit)
    if not raw:
        return {"issues": [], "repo": repo, "total": 0}
    extracted = [extract(i) for i in raw]
    # Preserve original state for UI filters
    for i, e in enumerate(extracted):
        e["state"] = raw[i].get("state", "")
    prioritised = prioritise_batch(extracted)
    return {"issues": prioritised, "repo": repo, "total": len(prioritised)}

@app.get("/api/issues/{issue_num}/recommendations")
def get_recommendations(repo: str, issue_num: int, top_k: int = 5):
    """Top-K developer recommendations with explanations for one issue."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM issues WHERE repo=? AND number=?", (repo, issue_num)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Issue #{issue_num} not found in {repo}")

    issue_dict = dict(row)
    recommendations = get_single_recommendation(issue_dict, repo, top_k=top_k)
    priority = map_priority(extract(issue_dict))

    return {
        "issue_num":       issue_num,
        "issue_title":     issue_dict.get("title", ""),
        "issue_body":      issue_dict.get("body", ""),
        "issue_state":     issue_dict.get("state", ""),
        "issue_created":   issue_dict.get("created_at", ""),
        "issue_closed":    issue_dict.get("closed_at", ""),
        "issue_author":    issue_dict.get("author", ""),
        "issue_labels":    json.loads(issue_dict.get("labels") or "[]"),
        "priority":        priority,
        "recommendations": recommendations,
        "repo":            repo,
    }

# -- Developers ---------------------------------------------------------------

@app.get("/api/developers")
def list_developers(repo: str):
    """List all developers with profiles for a repo."""
    profiles = load_profiles(repo)
    return {
        "developers": [
            {
                "username":      p["username"],
                "resolved_count": p.get("resolved_count", 0),
                "open_issues":   p.get("open_issue_count", 0),
                "last_active":   p.get("last_active", ""),
            }
            for p in sorted(profiles, key=lambda x: x.get("resolved_count", 0), reverse=True)
        ],
        "total": len(profiles),
        "repo":  repo,
    }

@app.get("/api/developers/{username}/profile")
def get_developer_profile(repo: str, username: str):
    """Full developer profile."""
    profile = load_profile(repo, username)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile for {username} in {repo}")
    try:
        profile["files"]      = json.loads(profile.get("files_json") or "{}")
        profile["components"] = json.loads(profile.get("components_json") or "{}")
    except Exception:
        pass
    return profile

# -- Assignment ---------------------------------------------------------------

@app.post("/api/assign/batch")
def batch_assign(req: BatchAssignRequest):
    """Workload-aware batch assignment."""
    conn = get_conn()
    issues = []
    for num in req.issue_nums:
        row = conn.execute(
            "SELECT * FROM issues WHERE repo=? AND number=?", (req.repo, num)
        ).fetchone()
        if row:
            issues.append(dict(row))
    conn.close()

    if not issues:
        raise HTTPException(status_code=404, detail="No matching issues found")
    closed = [issue["number"] for issue in issues if issue.get("state") != "open"]
    if closed:
        raise HTTPException(status_code=400, detail=f"Only open issues can be assigned: {closed}")

    assignments = assign_batch(issues, req.repo, capacity=req.capacity)
    return {"assignments": assignments, "total": len(assignments), "repo": req.repo}

@app.post("/api/assign/apply")
def apply_batch(req: ApplyBatchRequest):
    """Apply recommendations to GitHub, returning independent per-issue results."""
    conn = get_conn()
    issues = []
    for num in req.issue_nums:
        row = conn.execute(
            "SELECT * FROM issues WHERE repo=? AND number=?", (req.repo, num)
        ).fetchone()
        if row:
            issues.append(dict(row))
    conn.close()
    if not issues:
        raise HTTPException(status_code=404, detail="No matching issues found")
    closed = [issue["number"] for issue in issues if issue.get("state") != "open"]
    if closed:
        raise HTTPException(status_code=400, detail=f"Only open issues can be assigned: {closed}")

    proposed = req.assignments or assign_batch(issues, req.repo, capacity=req.capacity)
    by_num = {a.get("issue_num"): a for a in proposed}
    return {"assignments": _apply_assignments(req.repo, issues, proposed),
            "total": len(issues), "repo": req.repo}

def _apply_assignments(repo: str, issues: list, proposed: list, notify: bool = True):
    from ingestion.github_fetcher import assign_issue, comment_issue

    by_num = {a.get("issue_num"): a for a in proposed}
    results = []
    for issue in issues:
        issue_num = issue["number"]
        assignment = by_num.get(issue_num, {})
        developer = assignment.get("assigned_to")
        now = datetime.now(timezone.utc).isoformat()
        try:
            current_assignees = json.loads(issue.get("assignees_json") or "[]")
        except Exception:
            current_assignees = []
        if not developer:
            result = {**assignment, "issue_num": issue_num, "status": "failed",
                      "error": assignment.get("error", "No developer recommendation")}
        elif current_assignees:
            result = {**assignment, "status": "skipped",
                      "error": f"Already assigned to {', '.join(current_assignees)}"}
        else:
            remote = assign_issue(repo, issue_num, developer)
            result = {**assignment, "status": "assigned" if remote["ok"] else "failed"}
            if not remote["ok"]:
                result["error"] = remote.get("error", "GitHub assignment failed")
            if remote["ok"]:
                conn = get_conn()
                conn.execute(
                    "UPDATE issues SET assignees_json=? WHERE repo=? AND number=?",
                    (json.dumps([developer]), repo, issue_num),
                )
                conn.commit()
                conn.close()
                if notify:
                    notification = comment_issue(
                        repo, issue_num,
                        f"Automatically assigned to @{developer} based on repository history and similar resolved issues."
                    )
                    result["notified"] = notification["ok"]
                    if not notification["ok"]:
                        result["notification_error"] = notification.get("error")
        conn = get_conn()
        conn.execute("""
            INSERT INTO assignments (repo, issue_num, developer, status, github_response, created_at)
            VALUES (?,?,?,?,?,?)
        """, (repo, issue_num, developer, result["status"],
              json.dumps(result.get("error", "")), now))
        conn.commit()
        conn.close()
        results.append(result)
    return results

# -- Evaluation ---------------------------------------------------------------

@app.get("/api/evaluation/metrics")
def get_metrics(repo: str = None):
    """Return latest ablation results from disk."""
    results = get_latest_results()
    return {"results": results, "repo": repo}

@app.post("/api/evaluation/run")
async def run_evaluation(req: EvalRequest, bg: BackgroundTasks):
    """Trigger evaluation in background."""
    def _run():
        run_ablation(
            repo=req.repo,
            train_before=req.train_before,
            test_after=req.test_after,
            max_issues=req.max_issues,
        )
    bg.add_task(_run)
    return {"status": "started", "repo": req.repo,
            "message": "Evaluation running in background — check /api/evaluation/metrics"}

# -- Pipeline (ingest + profile build) ----------------------------------------

@app.post("/api/pipeline/ingest")
async def ingest(req: IngestRequest, bg: BackgroundTasks):
    """Ingest a GitHub repository in the background."""
    _set_pipeline_status(req.repo, "queued", "Preparing repository ingestion")

    def _run():
        try:
            from ingestion.github_fetcher import fetch_issues, fetch_pull_requests, fetch_commits
            from ingestion.github_fetcher import fetch_contributors
            from ingestion.db_loader import (upsert_issues, upsert_pull_requests, upsert_commits,
                                             upsert_repository_developers)
            print(f"[ingest] starting {req.repo}")
            _set_pipeline_status(req.repo, "running", "Fetching issues, pull requests, and commits")
            historical = fetch_issues(req.repo, state="closed", max_pages=req.max_pages)
            current = fetch_issues(req.repo, state="open", max_pages=req.max_pages, force_refresh=True)
            prs     = fetch_pull_requests(req.repo, max_pages=req.max_pages)
            commits = fetch_commits(req.repo, max_pages=req.max_pages)
            contributors = fetch_contributors(req.repo, max_pages=req.max_pages, force_refresh=True)
            upsert_issues(req.repo, historical + current)
            upsert_pull_requests(req.repo, prs)
            upsert_commits(req.repo, commits)
            upsert_repository_developers(req.repo, contributors)
            _set_pipeline_status(req.repo, "running", "Linking historical issues and building profiles")
            run_all_strategies(req.repo)
            build_profiles(req.repo)
            scanned = _scan_ingested_source(req.repo)
            _set_pipeline_status(
                req.repo,
                "completed",
                "Repository is ready",
                issues=len(historical) + len(current) + scanned,
                contributors=len(contributors),
                scanned_bugs=scanned,
            )
            print(f"[ingest] done {req.repo}: {len(historical) + len(current)} issues, {len(contributors)} contributors")
        except Exception as exc:
            _set_pipeline_status(req.repo, "failed", str(exc))
            print(f"[ingest] failed {req.repo}: {exc}")
    bg.add_task(_run)
    return {"status": "started", "repo": req.repo,
            "message": "Ingestion running in background"}

@app.get("/api/pipeline/status")
def pipeline_status(repo: str):
    """Return the latest background pipeline state for a repository."""
    return _pipeline_status.get(repo, {
        "repo": repo,
        "status": "idle",
        "message": "No pipeline run yet",
    })

@app.post("/api/pipeline/build-profiles")
async def build_profiles_endpoint(req: BuildProfilesRequest, bg: BackgroundTasks):
    def _run():
        build_profiles(req.repo)
    bg.add_task(_run)
    return {"status": "started", "repo": req.repo}

@app.get("/api/repos")
def list_repos():
    """List all repos that have data in the database."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT repo, COUNT(*) as cnt FROM issues GROUP BY repo ORDER BY cnt DESC"
    ).fetchall()
    conn.close()
    return {"repos": [{"repo": r["repo"], "issue_count": r["cnt"]} for r in rows]}

@app.delete("/api/repos/{repo:path}")
def remove_repo(repo: str):
    """Remove all locally stored data for one repository."""
    repo = repo.strip()
    if not repo:
        raise HTTPException(status_code=400, detail="Repository name is required")
    conn = get_conn()
    tables = [
        "issues", "pull_requests", "commits", "issue_pr_links",
        "developer_profiles", "repository_developers", "issue_priority",
        "recommendations", "assignments",
    ]
    existing = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in tables:
        if table in existing:
            conn.execute(f'DELETE FROM "{table}" WHERE repo=?', (repo,))
    conn.commit()
    conn.close()
    _pipeline_status.pop(repo, None)
    from ingestion.github_fetcher import CACHE_DIR
    import shutil
    cache_path = Path(CACHE_DIR) / repo.replace("/", "__")
    if cache_path.exists():
        shutil.rmtree(cache_path)
    return {"status": "removed", "repo": repo}

# ── Serve frontend static files ───────────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
