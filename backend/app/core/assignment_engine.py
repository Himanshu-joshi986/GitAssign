"""
Workload-aware greedy batch assignment + single-issue recommendations.

Recommendations are enriched with the AI layer before ranking:
    - `ensure_classified` attaches a (usually cached) LLM/heuristic
      classification to the issue.
    - `ensure_domain_profiles` builds any missing developer domain profiles
      on demand (capped so the request can't time out; uncapped builds
      happen in the pipeline/analyze run).
The domain_match signal then runs inside scoring_engine via s7.
"""
import json
from datetime import datetime, timezone

from app.core.scoring_engine import get_engine
from app.core.priority_mapper import prioritise_batch
from app.core.profile_builder import load_profiles
from app.core.issue_extractor import extract
from app.core.explanation_engine import explain

# On-demand profile build cap for synchronous UI requests; missed profiles
# contribute 0 to the domain signal and are picked up by the next run.
_ENSURE_PROFILE_CAP = 10


def _enrich(repo: str, issues: list, profiles: list, max_issues: int = None) -> list:
    """
    Attach `classification` to each issue dict and `domains_json` to each
    profile copy. Mutates and returns the inputs.
    """
    from app.core.issue_classifier import ensure_classified
    from app.core.domain_profiler import ensure_domain_profiles, load_domain_profiles

    usernames = [p["username"] for p in profiles]
    if usernames:
        ensure_domain_profiles(repo, usernames=usernames, cap=_ENSURE_PROFILE_CAP)
    domain_map = load_domain_profiles(repo)

    count = 0
    for issue in issues:
        if max_issues is not None and count >= max_issues:
            break
        count += 1
        try:
            issue["classification"] = ensure_classified(repo, issue)
        except Exception as exc:
            print(f"[enrich] classification failed for #{issue.get('number')}: {exc}")
            issue["classification"] = {}

    for profile in profiles:
        joined = domain_map.get(profile["username"])
        if joined:
            profile["domains_json"] = json.dumps(joined.get("domains", []))
    return issues


def _persist_recommendations(repo: str, issue_num: int, ranking: list, top_k: int = 5):
    """Cheap audit trail in the previously unused recommendations table."""
    conn = None
    try:
        from app.db.init_db import get_conn
        now = datetime.now(timezone.utc).isoformat()
        conn = get_conn()
        for i, signals in enumerate(ranking[:top_k]):
            conn.execute(
                """
                INSERT INTO recommendations
                    (repo, issue_num, developer, score, rank, signals_json, created_at)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    repo,
                    issue_num,
                    signals.get("developer"),
                    signals.get("final_score", 0),
                    i + 1,
                    json.dumps(signals),
                    now,
                ),
            )
        conn.commit()
    except Exception as exc:
        print(f"[recommendations] persist failed for #{issue_num}: {exc}")
    finally:
        if conn is not None:
            conn.close()


def _strip_internal(profile: dict, keys=("resolved_text", "resolved_issues_json", "evidence_json")) -> dict:
    return {k: v for k, v in profile.items() if k not in keys}


def _dev_domain_info(profile: dict) -> dict:
    try:
        domains = json.loads(profile.get("domains_json") or "[]")
    except Exception:
        domains = []
    return {"domains": domains, "domain_summary": ", ".join(d.get("name", "") for d in domains[:3])}


def _issue_classification(issue: dict) -> dict:
    classification = issue.get("classification") or {}
    return {
        "kind": classification.get("kind", "chore"),
        "domains": classification.get("domains", []),
        "difficulty": classification.get("difficulty", 3),
        "severity": classification.get("severity", "medium"),
        "summary": classification.get("summary", ""),
        "required_skills": classification.get("required_skills", []),
        "confidence": classification.get("confidence", 0.0),
        "model": classification.get("model", ""),
    }


def assign_batch(issues: list, repo: str, capacity: int = 3) -> list:
    """
    Assign a batch of issues to developers, highest priority first.

    issues:   list of raw issue dicts from DB
    repo:     repository slug
    capacity: max concurrent high-priority issues per developer

    Returns list of assignment dicts.
    """
    # Load profiles and fit engine
    profiles = load_profiles(repo)
    if not profiles:
        return [{"issue_num": i.get("number"), "error": "No developer profiles found"} for i in issues]

    engineered = [dict(p) for p in profiles]
    enriched_issues = [dict(i) for i in issues]
    _enrich(repo, enriched_issues, engineered)

    engine = get_engine()
    engine.fit(repo, engineered)

    # Extract and prioritise
    extracted = [extract(i) for i in enriched_issues]
    for i, e in enumerate(extracted):
        e["classification"] = enriched_issues[i].get("classification", {})
    prioritised = prioritise_batch(extracted)

    # Track developer loads
    dev_load = {p["username"]: p.get("open_issue_count", 0) for p in engineered}

    assignments = []
    for issue in prioritised:
        ranking = engine.rank(issue, engineered)

        assigned_dev = None
        assigned_signals = None

        for candidate in ranking:
            dev = candidate["developer"]
            if dev_load.get(dev, 0) < capacity:
                assigned_dev = dev
                assigned_signals = candidate
                dev_load[dev] = dev_load.get(dev, 0) + 1
                break

        # Fallback: assign to best even if over capacity
        if assigned_dev is None and ranking:
            assigned_dev = ranking[0]["developer"]
            assigned_signals = ranking[0]

        # Find profile for explanation
        profile = next((p for p in engineered if p["username"] == assigned_dev), {})
        explanation = explain(issue, profile, assigned_signals or {}) if assigned_signals else {}

        assignments.append({
            "issue_num":    issue.get("number"),
            "issue_title":  issue.get("title", ""),
            "priority_tier": issue.get("priority", {}).get("tier", "Medium"),
            "classification": _issue_classification(issue),
            "assigned_to":  assigned_dev,
            "score":        assigned_signals.get("final_score", 0) if assigned_signals else 0,
            "current_load": dev_load.get(assigned_dev, 0),
            "at_capacity":  dev_load.get(assigned_dev, 0) >= capacity,
            "explanation":  explanation,
            "top3":         ranking[:3],
        })

    return assignments


def get_single_recommendation(issue_dict: dict, repo: str, top_k: int = 5) -> list:
    """
    Get top-K developer recommendations for a single issue.
    Returns ranked list with explanations and the issue classification.
    """
    profiles = load_profiles(repo)
    if not profiles:
        return []

    engineered = [dict(p) for p in profiles]
    enriched_issues = _enrich(repo, [dict(issue_dict)], engineered)
    issue = enriched_issues[0]

    engine = get_engine()
    engine.fit(repo, engineered)

    extracted = extract(issue)
    extracted["classification"] = issue.get("classification", {})
    ranking = engine.rank(extracted, engineered)[:top_k]

    _persist_recommendations(repo, extracted.get("number"), ranking, top_k=top_k)

    results = []
    for signals in ranking:
        profile = next((p for p in engineered if p["username"] == signals["developer"]), {})
        exp = explain(extracted, profile, signals)
        results.append({
            **signals,
            **_dev_domain_info(profile),
            "explanation": exp,
        })

    return results
