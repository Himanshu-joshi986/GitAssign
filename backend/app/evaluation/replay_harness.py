"""
Historical replay harness — no future data leaks.

For each test issue:
  1. Build developer profiles using ONLY data before issue.created_at
  2. Run scoring engine on the issue
  3. Check whether any evidence-backed resolver appears in top-1, top-3, top-5
  4. Compute MRR = mean(1 / rank)

Issues can be linked to several pull requests, so every linked PR author is
considered a relevant resolver. Ranking quality is measured only when at least
one relevant resolver has pre-issue history; candidate coverage is reported
separately so cold-start issues do not masquerade as ranking failures.
"""
import json
from datetime import datetime
from app.db.init_db import get_conn
from app.core.issue_extractor import extract
from app.core.profile_builder import build_profiles, load_profiles
from app.core.scoring_engine import ScoringEngine

# In-memory cache for profiles at specific cutoff dates
# Key: (repo, cutoff_date) -> list of profile dicts
_PROFILE_CACHE: dict = {}


def run_replay(
    repo: str,
    train_before: str = "2010-01-01",
    test_after:   str = "2010-01-01",
    max_test_issues: int = 500,
    signals_config: dict = None,
) -> dict:
    """
    repo:             GitHub/bughub repo slug
    train_before:     build profiles from data before this date
    test_after:       test on issues closed after this date
    max_test_issues:  cap for speed
    signals_config:   override which signals are active (ablation)

    Returns: {"top1": float, "top3": float, "top5": float, "mrr": float, "n": int}
    """
    # Clear cache at start of each run
    _PROFILE_CACHE.clear()

    conn = get_conn()

    # Fetch linked issues and aggregate all PR authors as relevant outcomes.
    # A join without aggregation duplicated issues with multiple linked PRs and
    # arbitrarily treated one author as the sole correct answer.
    rows = conn.execute("""
        SELECT i.*, l.resolver
        FROM issues i
        JOIN issue_pr_links l ON l.repo=i.repo AND l.issue_num=i.number
        WHERE i.repo=? AND i.state='closed'
          AND i.closed_at > ?
          AND i.created_at >= ?
          AND (i.state_reason IS NULL OR i.state_reason != 'not_planned')
          AND l.resolver IS NOT NULL AND l.resolver != ''
        ORDER BY i.closed_at ASC
    """, (repo, test_after, train_before)).fetchall()
    conn.close()

    grouped = {}
    for row in rows:
        issue = dict(row)
        resolver = issue.pop("resolver")
        number = issue["number"]
        if number not in grouped:
            grouped[number] = {"issue": issue, "resolvers": set()}
        if resolver:
            grouped[number]["resolvers"].add(resolver)
    test_issues = list(grouped.values())[:max_test_issues]

    if not test_issues:
        print(f"[replay] No test issues found for {repo} after {test_after}")
        return {
            "top1": 0, "top3": 0, "top5": 0, "mrr": 0, "n": 0,
            "test_issues": 0, "eligible_issues": 0,
            "candidate_coverage": 0, "excluded_no_candidate": 0,
            "unavailable_signals": ["workload", "historical_domain_profile"],
            "repo": repo,
        }

    print(f"[replay] {len(test_issues)} test issues for {repo}")

    engine = ScoringEngine()
    if signals_config:
        engine.weights.update(signals_config)
    # The database stores current assignees, not assignment event history, so
    # historical workload cannot be reconstructed without future leakage.
    engine.weights["w6_workload_penalty"] = 0.0

    hits1 = hits3 = hits5 = 0
    reciprocal_ranks = []
    eligible_issues = 0
    covered_issues = 0

    # Track cache stats
    cache_hits = 0
    cache_misses = 0

    for idx, item in enumerate(test_issues):
        issue = item["issue"]
        actual = item["resolvers"]
        cutoff = issue.get("created_at", train_before)

        # Build profiles using only data before this issue was created (with caching)
        profiles, from_cache = _get_profiles_at_cutoff(repo, cutoff)
        if from_cache:
            cache_hits += 1
        else:
            cache_misses += 1
        if not profiles:
            continue

        engine.fit(repo, profiles)

        extracted = extract(issue)
        # Recency must be evaluated as it was known when the issue appeared,
        # not relative to the machine's current date.
        extracted["evaluation_as_of"] = cutoff
        ranking   = engine.rank(extracted, profiles)
        ranked_devs = [r["developer"] for r in ranking]

        # Only assess ranking when the replay has evidence for at least one
        # ground-truth resolver. Keep this distinct from model coverage.
        relevant_candidates = actual.intersection(ranked_devs)
        if not relevant_candidates:
            continue
        eligible_issues += 1
        covered_issues += 1

        rank = None
        for i, dev in enumerate(ranked_devs, start=1):
            if dev in actual:
                rank = i
                break

        if rank is not None:
            if rank == 1:   hits1 += 1
            if rank <= 3:   hits3 += 1
            if rank <= 5:   hits5 += 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

        if (idx + 1) % 50 == 0:
            running = hits5 / eligible_issues * 100 if eligible_issues else 0
            print(f"  [{idx+1}/{len(test_issues)}] eligible Top-5: {running:.1f}%  (cache: {cache_hits}h/{cache_misses}m)")

    n = eligible_issues
    test_n = len(test_issues)
    results = {
        "top1": round(hits1 / n * 100, 2) if n else 0,
        "top3": round(hits3 / n * 100, 2) if n else 0,
        "top5": round(hits5 / n * 100, 2) if n else 0,
        "mrr":  round(sum(reciprocal_ranks) / n, 4) if n else 0,
        "n":    n,
        "test_issues": test_n,
        "eligible_issues": n,
        "candidate_coverage": round(covered_issues / test_n * 100, 2) if test_n else 0,
        "excluded_no_candidate": test_n - n,
        "unavailable_signals": ["workload", "historical_domain_profile"],
        "repo": repo,
    }
    print(f"\n[replay] Results for {repo}:")
    print(f"  Top-1: {results['top1']}%  Top-3: {results['top3']}%  Top-5: {results['top5']}%  MRR: {results['mrr']}")
    print(f"  Profile cache: {cache_hits} hits, {cache_misses} misses")
    return results


def _get_profiles_at_cutoff(repo: str, cutoff_date: str) -> tuple:
    """Build (or retrieve from cache) developer profiles using only data before cutoff.
    Returns (profiles_list, was_cached)
    """
    cache_key = (repo, cutoff_date)
    if cache_key in _PROFILE_CACHE:
        return _PROFILE_CACHE[cache_key], True

    profiles = build_profiles(repo, cutoff_date=cutoff_date, persist=False)
    profile_list = list(profiles.values()) if profiles else []
    _PROFILE_CACHE[cache_key] = profile_list
    return profile_list, False

if __name__ == "__main__":
    import sys
    repo  = sys.argv[1] if len(sys.argv) > 1 else "eclipse/jdt"
    train = sys.argv[2] if len(sys.argv) > 2 else "2010-01-01"
    test  = sys.argv[3] if len(sys.argv) > 3 else "2010-01-01"
    results = run_replay(repo, train_before=train, test_after=test, max_test_issues=200)
    print(json.dumps(results, indent=2))
