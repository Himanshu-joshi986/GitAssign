"""
Historical replay harness — no future data leaks.

For each test issue:
  1. Build developer profiles using ONLY data before issue.created_at
  2. Run scoring engine on the issue
  3. Check if actual resolver appears in top-1, top-3, top-5
  4. Compute MRR = mean(1 / rank)
"""
import json
from datetime import datetime
from db.init_db import get_conn
from core.issue_extractor import extract
from core.profile_builder import build_profiles, load_profiles
from core.scoring_engine import ScoringEngine

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

    # Get test issues — closed after test_after with a known resolver
    test_issues = conn.execute("""
        SELECT i.*, l.resolver
        FROM issues i
        JOIN issue_pr_links l ON l.repo=i.repo AND l.issue_num=i.number
        WHERE i.repo=? AND i.state='closed'
          AND i.closed_at > ?
          AND l.resolver IS NOT NULL AND l.resolver != ''
        ORDER BY i.closed_at ASC
        LIMIT ?
    """, (repo, test_after, max_test_issues)).fetchall()
    conn.close()

    if not test_issues:
        print(f"[replay] No test issues found for {repo} after {test_after}")
        return {"top1": 0, "top3": 0, "top5": 0, "mrr": 0, "n": 0}

    print(f"[replay] {len(test_issues)} test issues for {repo}")

    engine = ScoringEngine()
    if signals_config:
        engine.weights.update(signals_config)

    hits1 = hits3 = hits5 = 0
    reciprocal_ranks = []

    # Track cache stats
    cache_hits = 0
    cache_misses = 0

    for idx, row in enumerate(test_issues):
        issue  = dict(row)
        actual = issue.pop("resolver")
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
        ranking   = engine.rank(extracted, profiles)
        ranked_devs = [r["developer"] for r in ranking]

        rank = None
        for i, dev in enumerate(ranked_devs, start=1):
            if dev == actual:
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
            print(f"  [{idx+1}/{len(test_issues)}] running top-5: {hits5/(idx+1)*100:.1f}%  (cache: {cache_hits}h/{cache_misses}m)")

    n = len(test_issues)
    results = {
        "top1": round(hits1 / n * 100, 2),
        "top3": round(hits3 / n * 100, 2),
        "top5": round(hits5 / n * 100, 2),
        "mrr":  round(sum(reciprocal_ranks) / n, 4),
        "n":    n,
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

    profiles = build_profiles(repo, cutoff_date=cutoff_date)
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
