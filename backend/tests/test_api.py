"""
API endpoint tests using FastAPI TestClient.
Run: pytest backend/tests/test_api.py -v
"""
import sys, os, json, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DB_PATH"] = "data/test_gitassign.db"

from fastapi.testclient import TestClient
from db.init_db import init_db

# Init a fresh test DB
init_db()

from main import app

client = TestClient(app)

# ── Health ────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_demo_scan_uses_fallback_developer():
    r = client.post("/api/demo/scan", json={
        "repo": "new/demo",
        "filename": "demo.py",
        "content": "# BUG-1: incorrect total\nvalue = 1",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["bugs"][0]["assigned_to"] == "demo_backend"
    assert data["bugs"][0]["assignment_source"] == "demo_fallback"
    issue_num = data["bugs"][0]["issue_num"]
    listed = client.get("/api/issues?repo=new/demo&state=open").json()
    assert listed["total"] == 1
    assert listed["issues"][0]["number"] == issue_num

def test_remove_repo_clears_local_data():
    response = client.delete("/api/repos/new/demo")
    assert response.status_code == 200
    assert response.json()["status"] == "removed"
    assert client.get("/api/repos").json()["repos"] == []

# ── Repos ─────────────────────────────────────────────────────────────────────

def test_list_repos_empty():
    r = client.get("/api/repos")
    assert r.status_code == 200
    assert "repos" in r.json()

def test_pipeline_status_idle():
    r = client.get("/api/pipeline/status?repo=unknown/repo")
    assert r.status_code == 200
    assert r.json()["status"] == "idle"

# ── Issues ───────────────────────────────────────────────────────────────────

def test_get_issues_unknown_repo():
    r = client.get("/api/issues?repo=unknown/repo")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["issues"] == []

def test_get_recommendations_404():
    r = client.get("/api/issues/9999/recommendations?repo=unknown/repo")
    assert r.status_code == 404

# ── Developers ────────────────────────────────────────────────────────────────

def test_list_developers_empty():
    r = client.get("/api/developers?repo=unknown/repo")
    assert r.status_code == 200
    assert r.json()["total"] == 0

def test_get_developer_profile_404():
    r = client.get("/api/developers/nobody/profile?repo=unknown/repo")
    assert r.status_code == 404

# ── Batch Assign ─────────────────────────────────────────────────────────────

def test_batch_assign_no_issues():
    r = client.post("/api/assign/batch", json={
        "repo": "unknown/repo",
        "issue_nums": [9999],
        "capacity": 3
    })
    assert r.status_code == 404

def test_batch_assign_rejects_closed_issue():
    conn = __import__("db.init_db", fromlist=["get_conn"]).get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO issues
        (repo, number, title, body, state, labels, assignees_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("unknown/repo", 1001, "Historical bug", "", "closed", "[]", "[]"))
    conn.commit()
    conn.close()
    r = client.post("/api/assign/batch", json={
        "repo": "unknown/repo", "issue_nums": [1001], "capacity": 3
    })
    assert r.status_code == 400

# ── Evaluation ────────────────────────────────────────────────────────────────

def test_get_metrics_empty():
    r = client.get("/api/evaluation/metrics")
    assert r.status_code == 200
    assert "results" in r.json()

# ── Pipeline ─────────────────────────────────────────────────────────────────

def test_ingest_starts_background():
    r = client.post("/api/pipeline/ingest", json={
        "repo": "pallets/click",
        "max_pages": 1
    })
    assert r.status_code == 200
    assert r.json()["status"] == "started"

def test_build_profiles_starts_background():
    r = client.post("/api/pipeline/build-profiles", json={"repo": "pallets/click"})
    assert r.status_code == 200
    assert r.json()["status"] == "started"

# ── Cleanup ───────────────────────────────────────────────────────────────────

def test_cleanup():
    """Remove test DB after tests."""
    db_path = os.environ.get("DB_PATH", "data/test_gitassign.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    assert True
