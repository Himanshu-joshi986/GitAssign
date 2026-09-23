"""
GitAssign test suite.
Run: pytest backend/tests/ -v
"""
import sys, os, json, pytest

# Make sure backend modules are on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.issue_extractor import extract
from core.priority_mapper import map_priority
from core.scoring_engine  import (
    text_similarity, component_overlap,
    file_affinity, recency_score, workload_penalty, ScoringEngine
)
from core.explanation_engine import explain

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_issue():
    return {
        "id": 1, "repo": "test/repo", "number": 42,
        "title": "NullPointerException in connection pool under high load",
        "body":  "Steps to reproduce: run 500 concurrent connections. "
                 "Files affected: src/net/pool.py src/db/connector.py",
        "labels": '["bug", "crash", "networking"]',
        "state": "open", "created_at": "2024-01-15T10:00:00Z",
    }

@pytest.fixture
def sample_profile():
    return {
        "username": "priya_dev",
        "repo": "test/repo",
        "files_json": json.dumps({
            "src/net/pool.py": 12,
            "src/db/connector.py": 5,
            "src/auth/token.py": 3,
        }),
        "components_json": json.dumps({
            "networking": 8,
            "bug": 15,
            "crash": 4,
        }),
        "resolved_text": (
            "NullPointerException connection pool deadlock high load "
            "networking database connector timeout socket"
        ),
        "last_active": "2024-08-01T00:00:00Z",
        "open_issue_count": 1,
        "resolved_count": 23,
    }

# ── Issue Extractor Tests ─────────────────────────────────────────────────────

class TestIssueExtractor:
    def test_extracts_text(self, sample_issue):
        result = extract(sample_issue)
        assert "NullPointerException" in result["text"]

    def test_extracts_labels(self, sample_issue):
        result = extract(sample_issue)
        assert "bug" in result["labels_lower"]
        assert "crash" in result["labels_lower"]

    def test_detects_severity_keywords(self, sample_issue):
        result = extract(sample_issue)
        assert "crash" in result["severity_keywords"]

    def test_extracts_mentioned_files(self, sample_issue):
        result = extract(sample_issue)
        assert any("pool.py" in f for f in result["mentioned_files"])

    def test_extracts_components(self, sample_issue):
        result = extract(sample_issue)
        assert "networking" in result["components"]

    def test_handles_empty_body(self):
        issue = {"id": 2, "repo": "r", "number": 1,
                 "title": "Test", "body": None, "labels": "[]", "state": "open"}
        result = extract(issue)
        assert result["text"].strip() == "Test"

# ── Priority Mapper Tests ─────────────────────────────────────────────────────

class TestPriorityMapper:
    def test_crash_keyword_is_critical(self, sample_issue):
        extracted = extract(sample_issue)
        result = map_priority(extracted)
        assert result["tier"] in ("Critical", "High")
        assert result["score"] > 0

    def test_enhancement_is_low(self):
        issue = {"id": 3, "repo": "r", "number": 2,
                 "title": "Add dark mode support",
                 "body": "Enhancement request for better UX",
                 "labels": '["enhancement"]', "state": "open"}
        extracted = extract(issue)
        result = map_priority(extracted)
        assert result["tier"] in ("Low", "Medium")

    def test_security_is_critical(self):
        issue = {"id": 4, "repo": "r", "number": 3,
                 "title": "SQL injection vulnerability in login",
                 "body": "CVE-2024-0001 auth bypass via injection",
                 "labels": '["security"]', "state": "open"}
        extracted = extract(issue)
        result = map_priority(extracted)
        assert result["tier"] == "Critical"
        assert result["score"] >= 5

    def test_steps_to_reproduce_boost(self, sample_issue):
        extracted = extract(sample_issue)
        result = map_priority(extracted)
        assert any("Steps to reproduce" in f for f in result["factors"])

    def test_has_color(self, sample_issue):
        result = map_priority(extract(sample_issue))
        assert result["color"] in ("red", "orange", "yellow", "green")

# ── Scoring Engine Signal Tests ───────────────────────────────────────────────

class TestScoringSignals:
    def test_empty_profile_corpus_is_safe(self, sample_issue):
        engine = ScoringEngine()
        engine.fit("test/repo", [{"username": "new_contributor", "resolved_text": ""}])
        result = engine.score(extract(sample_issue), {
            "username": "new_contributor",
            "resolved_text": "",
            "files_json": "{}",
            "components_json": "{}",
            "resolved_issues_json": "[]",
            "open_issue_count": 0,
            "last_active": "",
        })
        assert result["s1_text"] == 0.0
        assert result["s2_past"] == 0.0

    def test_text_similarity_identical(self):
        s = text_similarity("connection pool deadlock", "connection pool deadlock")
        assert s == pytest.approx(1.0, abs=0.05)

    def test_text_similarity_unrelated(self):
        s = text_similarity("connection pool deadlock", "dark mode user interface button")
        assert s < 0.2

    def test_component_overlap_full(self):
        score = component_overlap(
            ["networking", "bug"],
            {"networking": 5, "bug": 10}
        )
        assert score == pytest.approx(1.0)

    def test_component_overlap_partial(self):
        score = component_overlap(
            ["networking", "auth"],
            {"networking": 5}
        )
        assert score == pytest.approx(0.5)

    def test_component_overlap_empty(self):
        assert component_overlap([], {"networking": 5}) == 0.0
        assert component_overlap(["networking"], {}) == 0.0

    def test_file_affinity_match(self):
        score = file_affinity(
            ["src/net/pool.py"],
            {"src/net/pool.py": 10, "other.py": 2}
        )
        assert score > 0

    def test_file_affinity_no_match(self):
        score = file_affinity(
            ["src/net/pool.py"],
            {"src/auth/token.py": 10}
        )
        assert score == 0.0

    def test_recency_recent(self):
        from datetime import datetime, timezone, timedelta
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        score = recency_score(yesterday)
        assert score > 0.95

    def test_recency_old(self):
        score = recency_score("2015-01-01T00:00:00Z")
        assert score < 0.01

    def test_recency_empty(self):
        assert recency_score("") == 0.0

    def test_workload_under_capacity(self):
        assert workload_penalty(1, capacity=3) == pytest.approx(1/3, abs=0.01)

    def test_workload_at_capacity(self):
        assert workload_penalty(3, capacity=3) == pytest.approx(1.0)

    def test_workload_zero(self):
        assert workload_penalty(0, capacity=3) == 0.0

# ── Explanation Engine Tests ──────────────────────────────────────────────────

class TestExplanationEngine:
    def test_returns_all_signal_keys(self, sample_issue, sample_profile):
        extracted = extract(sample_issue)
        signals = {
            "final_score": 0.72,
            "s1_text": 0.65, "s2_past": 0.55,
            "s3_component": 0.75, "s4_file": 0.60,
            "s5_recency": 0.90, "s6_workload": 0.10,
        }
        result = explain(extracted, sample_profile, signals)
        assert "text_similarity" in result["signals"]
        assert "file_affinity" in result["signals"]
        assert "workload" in result["signals"]

    def test_summary_contains_developer_name(self, sample_issue, sample_profile):
        extracted = extract(sample_issue)
        signals = {"final_score": 0.72, "s1_text": 0.5, "s2_past": 0.4,
                   "s3_component": 0.5, "s4_file": 0.4, "s5_recency": 0.8, "s6_workload": 0.2}
        result = explain(extracted, sample_profile, signals)
        assert "priya_dev" in result["summary"]

    def test_final_score_passed_through(self, sample_issue, sample_profile):
        extracted = extract(sample_issue)
        signals = {"final_score": 0.77, "s1_text": 0.5, "s2_past": 0.4,
                   "s3_component": 0.5, "s4_file": 0.4, "s5_recency": 0.8, "s6_workload": 0.2}
        result = explain(extracted, sample_profile, signals)
        assert result["final_score"] == pytest.approx(0.77)

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
