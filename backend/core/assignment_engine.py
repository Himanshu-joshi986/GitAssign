"""
Workload-aware greedy batch assignment.
Assigns issues to developers respecting per-developer capacity limits.
"""
import json
from core.scoring_engine import get_engine
from core.priority_mapper import prioritise_batch
from core.profile_builder import load_profiles
from core.issue_extractor import extract
from core.explanation_engine import explain

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

    engine = get_engine()
    engine.fit(repo, profiles)

    # Extract and prioritise
    extracted = [extract(i) for i in issues]
    prioritised = prioritise_batch(extracted)

    # Track developer loads
    dev_load = {p["username"]: p.get("open_issue_count", 0) for p in profiles}

    assignments = []
    for issue in prioritised:
        ranking = engine.rank(issue, profiles)

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
        profile = next((p for p in profiles if p["username"] == assigned_dev), {})
        explanation = explain(issue, profile, assigned_signals or {}) if assigned_signals else {}

        assignments.append({
            "issue_num":    issue.get("number"),
            "issue_title":  issue.get("title", ""),
            "priority_tier": issue.get("priority", {}).get("tier", "Medium"),
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
    Returns ranked list with explanations.
    """
    profiles = load_profiles(repo)
    if not profiles:
        return []

    engine = get_engine()
    engine.fit(repo, profiles)

    extracted = extract(issue_dict)
    ranking = engine.rank(extracted, profiles)[:top_k]

    results = []
    for signals in ranking:
        profile = next((p for p in profiles if p["username"] == signals["developer"]), {})
        exp = explain(extracted, profile, signals)
        results.append({**signals, "explanation": exp})

    return results
