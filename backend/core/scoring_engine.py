"""
Six-signal deterministic scoring engine.
All weights come from config/weights.json — no model training.
"""
import json, os, math
from datetime import datetime, timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def _resolve_weights_path() -> str:
    raw = os.environ.get("WEIGHTS_PATH", "config/weights.json")
    if os.path.isabs(raw) and os.path.exists(raw):
        return raw
    backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(backend, raw if not os.path.isabs(raw) else os.path.basename(raw))
    if os.path.exists(candidate):
        return candidate
    if os.path.exists(raw):
        return raw
    return candidate

CONFIG_PATH = _resolve_weights_path()

DEFAULT_WEIGHTS = {
    "w1_text_similarity": 0.35,
    "w2_past_issue_similarity": 0.25,
    "w3_component_overlap": 0.15,
    "w4_file_affinity": 0.15,
    "w5_recency": 0.05,
    "w6_workload_penalty": 0.05,
    "capacity_limit": 3
}

def load_weights() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return DEFAULT_WEIGHTS

# --- Individual signal functions ---

def text_similarity(issue_text: str, developer_resolved_text: str, vectorizer=None) -> float:
    """TF-IDF cosine similarity between issue text and developer's resolved issue corpus."""
    if not issue_text.strip() or not developer_resolved_text.strip():
        return 0.0
    try:
        docs = [issue_text, developer_resolved_text]
        if vectorizer is not None and hasattr(vectorizer, "vocabulary_") and vectorizer.vocabulary_ is not None:
            # Use pre-fitted corpus vectorizer (transform only — no leak / re-fit)
            matrix = vectorizer.transform(docs)
        else:
            vec = vectorizer or TfidfVectorizer(max_features=5000, stop_words="english")
            matrix = vec.fit_transform(docs)
        sim = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
        return float(sim)
    except Exception:
        return 0.0

def past_issue_similarity(issue_text: str, past_issues: list) -> float:
    """Average cosine similarity between this issue and each of developer's past resolved issues."""
    if not past_issues or not issue_text.strip():
        return 0.0
    scores = []
    for past in past_issues[:50]:  # cap at 50
        if past.strip():
            scores.append(text_similarity(issue_text, past))
    return float(np.mean(scores)) if scores else 0.0

def component_overlap(issue_components: list, dev_components: dict) -> float:
    """Fraction of issue's components in which developer has activity."""
    if not issue_components:
        return 0.0
    hits = sum(1 for c in issue_components if c in dev_components)
    return hits / len(issue_components)

def file_affinity(mentioned_files: list, dev_files: dict) -> float:
    """Normalised developer commit frequency on files mentioned in the issue."""
    if not mentioned_files or not dev_files:
        return 0.0
    total_commits = sum(dev_files.values()) or 1
    hits = sum(dev_files.get(f, 0) for f in mentioned_files)
    # Normalise by total so it is in [0, 1]
    return min(hits / total_commits, 1.0)

def recency_score(last_active: str, half_life_days: int = 60) -> float:
    """Exponential decay: 1.0 if active today, 0.5 after half_life_days, etc."""
    if not last_active:
        return 0.0
    try:
        last = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_ago = (now - last).days
        return math.exp(-days_ago / half_life_days)
    except Exception:
        return 0.0

def workload_penalty(open_issue_count: int, capacity: int = 3) -> float:
    """Returns a penalty value. 0 if under capacity, scales up beyond capacity."""
    return min(open_issue_count / max(capacity, 1), 1.0)

# --- Main scoring function ---

class ScoringEngine:
    def __init__(self):
        self.weights = load_weights()
        self._vectorizers = {}  # repo -> fitted TfidfVectorizer

    def fit(self, repo: str, profiles: list):
        """Pre-fit TF-IDF on all developer corpora for faster scoring."""
        texts = [p.get("resolved_text", "").strip() for p in profiles]
        texts = [text for text in texts if text]
        if not texts:
            self._vectorizers.pop(repo, None)
            return
        vec = TfidfVectorizer(max_features=5000, stop_words="english")
        try:
            vec.fit(texts)
        except ValueError:
            self._vectorizers.pop(repo, None)
            return
        self._vectorizers[repo] = vec

    def score(self, issue: dict, profile: dict) -> dict:
        """
        Returns a dict of individual signal values and the combined score.
        issue: output of core.issue_extractor.extract()
        profile: dict from developer_profiles table
        """
        w = self.weights
        vec = self._vectorizers.get(issue.get("repo"))

        # Parse profile JSON fields
        dev_files = json.loads(profile.get("files_json") or "{}")
        dev_components = json.loads(profile.get("components_json") or "{}")
        try:
            past_issue_list = json.loads(profile.get("resolved_issues_json") or "[]")
        except Exception:
            past_issue_list = []
        # Backward compat: if no individual issues stored, use the concatenated corpus as a single entry
        if not past_issue_list and profile.get("resolved_text", "").strip():
            past_issue_list = [profile["resolved_text"]]

        s1 = text_similarity(
            issue["text"],
            profile.get("resolved_text", ""),
            vectorizer=vec
        )
        s2 = past_issue_similarity(issue["text"], past_issue_list)
        s3 = component_overlap(issue.get("components", []), dev_components)
        s4 = file_affinity(issue.get("mentioned_files", []), dev_files)
        s5 = recency_score(profile.get("last_active", ""))
        s6 = workload_penalty(
            profile.get("open_issue_count", 0),
            capacity=w.get("capacity_limit", 3)
        )

        combined = (
            w["w1_text_similarity"]       * s1 +
            w["w2_past_issue_similarity"] * s2 +
            w["w3_component_overlap"]     * s3 +
            w["w4_file_affinity"]         * s4 +
            w["w5_recency"]               * s5 -
            w["w6_workload_penalty"]      * s6
        )

        return {
            "developer":    profile["username"],
            "final_score":  round(float(combined), 4),
            "s1_text":      round(s1, 4),
            "s2_past":      round(s2, 4),
            "s3_component": round(s3, 4),
            "s4_file":      round(s4, 4),
            "s5_recency":   round(s5, 4),
            "s6_workload":  round(s6, 4),
        }

    def rank(self, issue: dict, profiles: list) -> list:
        """Return profiles ranked by score, best first."""
        scored = [self.score(issue, p) for p in profiles]
        return sorted(scored, key=lambda x: x["final_score"], reverse=True)

# Singleton
_engine = None

def get_engine() -> ScoringEngine:
    global _engine
    if _engine is None:
        _engine = ScoringEngine()
    return _engine
