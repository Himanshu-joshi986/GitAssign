"""
Local AI layer for evidence retrieval.

This layer is intentionally provider-free: it uses the existing scikit-learn
stack to retrieve semantically similar historical issues. Deterministic
scoring remains authoritative; this layer only adds evidence and context.
"""
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def retrieve_issue_evidence(issue: dict, profile: dict, top_k: int = 3) -> list[dict]:
    """Return the most similar historical issues for one developer profile."""
    try:
        evidence = json.loads(profile.get("evidence_json") or "[]")
    except (TypeError, json.JSONDecodeError):
        evidence = []

    if not evidence:
        return []

    query = str(issue.get("text") or "").strip()
    documents = [str(item.get("text") or "").strip() for item in evidence]
    valid = [(item, text) for item, text in zip(evidence, documents) if text]
    if not query or not valid:
        return []

    try:
        vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
        matrix = vectorizer.fit_transform([query] + [text for _, text in valid])
        scores = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
    except ValueError:
        return []

    ranked = sorted(
        zip((item for item, _ in valid), scores),
        key=lambda pair: (-float(pair[1]), int(pair[0].get("issue_num", 0))),
    )
    return [
        {
            "issue_num": item.get("issue_num"),
            "title": item.get("title", ""),
            "closed_at": item.get("closed_at", ""),
            "similarity": round(float(score), 4),
        }
        for item, score in ranked[:max(0, top_k)]
    ]


def build_ai_context(issue: dict, profile: dict, top_k: int = 3) -> dict:
    """Build deterministic AI-layer context for a recommendation."""
    evidence = retrieve_issue_evidence(issue, profile, top_k=top_k)
    return {
        "enabled": True,
        "provider": "local-tfidf",
        "evidence": evidence,
        "evidence_count": len(evidence),
    }
