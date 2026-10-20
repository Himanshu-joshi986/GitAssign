"""
Offline AI pipeline tests (plan Step 9). No real HTTP / no GEMINI_API_KEY needed:
the LLM is monkeypatched, so every call is counted locally.
Run: pytest backend/tests/test_ai_pipeline.py -v
"""
import sys, os, json, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DB_PATH"] = "data/test_gitassign.db"
os.environ["GEMINI_API_KEY"] = ""  # disabled by default; per-test mocks re-enable

from app.db.init_db import init_db, get_conn
init_db()

REPO = "ai/triage"
ISSUE = {
    "number": 1,
    "title": "database pool leak on reconnect",
    "body": "sqlite connection pool leaks sockets; sql fix needed",
    "labels": ["bug"],
}
DEV = "ai_dev"
DEV_DOMAIN_WEIGHTS = json.dumps([
    {"name": "database", "weight": 0.7, "evidence": "sql files"},
    {"name": "backend", "weight": 0.3, "evidence": "py files"},
])


def _purge():
    conn = get_conn()
    for table in ("issue_classifications", "developer_domains", "issues", "commits",
                  "issue_pr_links", "pull_requests", "developer_profiles",
                  "repository_developers", "recommendations"):
        conn.execute(f"DELETE FROM {table} WHERE repo=?", (REPO,))
    conn.commit()
    conn.close()


@pytest.fixture(autouse=True)
def seeded():
    _purge()
    conn = get_conn()
    conn.execute("INSERT INTO repository_developers (repo, username, contributions) VALUES (?,?,4)", (REPO, DEV))
    conn.execute(
        "INSERT INTO issues (repo, number, title, body, labels, state, created_at) VALUES (?,?,?,?,?,'open','2026-02-01')",
        (REPO, ISSUE["number"], ISSUE["title"], ISSUE["body"], json.dumps(ISSUE["labels"])),
    )
    conn.execute(
        "INSERT INTO commits (sha, repo, author, message, files_json, created_at) VALUES ('ai-s1',?,?,?,?,'2026-01-01')",
        (REPO, DEV, "fix database pool leak", json.dumps(["src/db/pool.py"])),
    )
    conn.execute(
        "INSERT INTO developer_profiles (username, repo, files_json, components_json, resolved_text,"
        " resolved_issues_json, evidence_json, profile_version, last_active, open_issue_count,"
        " resolved_count, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (DEV, REPO,
         json.dumps(["src/db/pool.py"]), "{}",
         "database pool leak", json.dumps(["database pool leak"]), "[]",
         1, "2026-01-02", 0, 1, "2026-01-02"),
    )
    conn.commit()
    conn.close()
    yield
    _purge()


def _fake_llm_result():
    return {
        "kind": "bug",
        "domains": [{"name": "database", "confidence": 0.9}],
        "difficulty": 3,
        "severity": "high",
        "summary": "Connection pool leaks sockets",
        "required_skills": ["sql"],
        "confidence": 0.95,
    }


# ── 1. Heuristic classification stays inside the taxonomy ────────────────────

def test_heuristic_classification_never_returns_unknown_domains(monkeypatch):
    from app.core.domain_taxonomy import heuristic_classification, domain_names

    for title, body in [
        ("fix docker deploy crash", "k8s pod fails"),
        ("add oauth login support", ""),
        ("slow memory leak", "latency high"),
        ("", ""),
    ]:
        result = heuristic_classification(title, body)
        assert result["model"] == "heuristic"
        assert 1 <= len(result["domains"]) <= 3
        for d in result["domains"]:
            assert d["name"] in domain_names(), result


# ── 2. Classification cache skips the second LLM call ────────────────────────

def test_classification_cache_skips_second_llm_call(monkeypatch):
    from app.core import llm_client, issue_classifier

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = {"n": 0}

    def fake_generate(prompt, system=None):
        calls["n"] += 1
        return _fake_llm_result()

    monkeypatch.setattr(llm_client, "generate_json", fake_generate)

    first = issue_classifier.classify_issue(REPO, dict(ISSUE))
    assert calls["n"] == 1
    assert first["kind"] == "bug"

    second = issue_classifier.classify_issue(REPO, dict(ISSUE))
    assert calls["n"] == 1, "cached classification must not re-call the LLM"
    assert second == first


# ── 3. Changing the issue input triggers reclassification ────────────────────

def test_classification_reclassifies_when_input_changes(monkeypatch):
    from app.core import llm_client, issue_classifier

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = {"n": 0}

    def fake_generate(prompt, system=None):
        calls["n"] += 1
        return _fake_llm_result()

    monkeypatch.setattr(llm_client, "generate_json", fake_generate)
    issue_classifier.classify_issue(REPO, dict(ISSUE))
    assert calls["n"] == 1

    changed = dict(ISSUE, title="completely new crash on startup")
    issue_classifier.classify_issue(REPO, changed)
    assert calls["n"] == 2, "changed input hash must force a reclassify"


# ── 4. Domain profile is built once, then reused ─────────────────────────────

def test_domain_profile_is_built_once(monkeypatch):
    from app.core import llm_client, domain_profiler

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = {"n": 0}

    def fake_generate(prompt, system=None):
        calls["n"] += 1
        return {
            "profiles": [{
                "username": DEV,
                "domains": [{"name": "database", "weight": 0.8, "evidence": "sql files"}],
                "preferred_kinds": ["bug"],
                "summary": "Database specialist.",
            }]
        }

    monkeypatch.setattr(llm_client, "generate_json", fake_generate)

    first = domain_profiler.build_domain_profiles(REPO)
    assert first["built"] == 1
    assert calls["n"] == 1  # batched: 1 call for the whole run

    second = domain_profiler.build_domain_profiles(REPO)
    assert second["built"] == 0 and second["cached"] == 1
    assert calls["n"] == 1, "second run must make zero LLM calls"

    # On-demand path also skips existing rows.
    ensure = domain_profiler.ensure_domain_profiles(REPO, usernames=[DEV])
    assert ensure["built"] == 0 and ensure["cached"] == 1
    assert calls["n"] == 1


# ── 5. force=True rebuilds the profile ──────────────────────────────────────

def test_domain_profile_force_rebuilds(monkeypatch):
    from app.core import llm_client, domain_profiler

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = {"n": 0}

    def fake_generate(prompt, system=None):
        calls["n"] += 1
        return {
            "profiles": [{
                "username": DEV,
                "domains": [{"name": "backend", "weight": 1.0}],
                "preferred_kinds": [],
                "summary": "Backend specialist.",
            }]
        }

    monkeypatch.setattr(llm_client, "generate_json", fake_generate)
    domain_profiler.build_domain_profiles(REPO)
    assert calls["n"] == 1

    result = domain_profiler.build_domain_profiles(REPO, force=True)
    assert result["built"] == 1
    assert calls["n"] == 2, "force must trigger one more LLM call"


# ── 6. domain_match scoring maths ───────────────────────────────────────────

def test_domain_match_scores_overlap():
    from app.core.domain_taxonomy import domain_match

    score = domain_match(
        [{"name": "backend"}],
        {"backend": 0.8, "database": 0.2},
    )
    assert abs(score - 0.8) < 1e-6
    assert domain_match([], {"backend": 1.0}) == 0.0
    assert domain_match([{"name": "backend"}], {}) == 0.0


# ── 7. Scoring includes the domain signal ───────────────────────────────────

def test_scoring_includes_domain_signal():
    from app.core.scoring_engine import ScoringEngine

    engine = ScoringEngine()
    issue = {
        "repo": REPO,
        "number": 1,
        "title": "database pool leak",
        "text": "database pool leak",
        "components": [],
        "mentioned_files": [],
        "classification": {"domains": [{"name": "database"}]},
    }
    base = {
        "username": DEV,
        "files_json": "[\"src/db/pool.py\"]",
        "components_json": "{}",
        "resolved_issues_json": "[\"database pool leak\"]",
        "resolved_text": "database pool leak",
        "open_issue_count": 0,
        "last_active": "2026-01-02",
    }

    fitting = dict(base, domains_json=DEV_DOMAIN_WEIGHTS)
    docs_only = dict(base, domains_json=json.dumps([{"name": "docs", "weight": 1.0}]))
    scoring = engine.score(issue, fitting)
    control = engine.score(issue, docs_only)

    assert scoring["s7_domain"] > 0
    assert control["s7_domain"] == 0.0
    assert scoring["final_score"] > control["final_score"]

    # Old-style issue/profile without domains must not raise and scores equal.
    plain_issue = dict(issue)
    plain_issue.pop("classification")
    a = engine.score(plain_issue, fitting)
    b = engine.score(plain_issue, docs_only)
    assert a["s7_domain"] == 0.0 and b["s7_domain"] == 0.0


# ── 8. LLM failure falls back to heuristics ─────────────────────────────────

def test_llm_failure_falls_back_to_heuristic(monkeypatch):
    from app.core import llm_client, issue_classifier

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fail_generate(prompt, system=None):
        return None

    monkeypatch.setattr(llm_client, "generate_json", fail_generate)

    result = issue_classifier.classify_issue(REPO, dict(ISSUE))
    assert result["model"] == "heuristic"
    assert 1 <= len(result["domains"]) <= 3
    # A failed LLM call must never be cached as a *final* LLM answer.
    cached = issue_classifier._fetch_cached(REPO, ISSUE["number"])
    assert cached["model"] == "heuristic"
    # And when the key is later present, the heuristic row is retried.
    monkeypatch.setattr(llm_client, "generate_json", lambda *a, **k: _fake_llm_result())
    retried = issue_classifier.classify_issue(REPO, dict(ISSUE))
    assert retried["model"] == llm_client.model_name()


# ── 9. API recommendations include classification + domain signal ───────────

def test_recommendations_include_classification():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get(f"/api/issues/{ISSUE['number']}/recommendations?repo={REPO}")
    assert r.status_code == 200
    body = r.json()

    assert body["classification"], "issue classification missing from response"
    assert body["classification"]["kind"] in ("bug", "performance", "refactor", "test", "security", "docs", "feature", "chore")

    assert body["recommendations"], "expected at least one recommendation"
    rec = body["recommendations"][0]
    assert "s7_domain" in rec
    assert "domains" in rec and "domain_summary" in rec
    assert rec["explanation"]["signals"]["domain"]["value"] == rec["s7_domain"]
