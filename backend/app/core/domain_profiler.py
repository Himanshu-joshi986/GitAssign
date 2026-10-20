"""
Cached LLM domain profiles for contributors.

 Builds a Gemini-backed expertise profile per developer from their repo
history (resolved issues, commit messages, touched files, authored merged
PRs), cached in `developer_domains` keyed by (repo, username).

Cache rules (the strict "once only" contract):
    - Row exists + force=False -> reuse it (zero LLM calls), regardless of
      `evidence_hash`; the hash is stored only for audit / future opt-in
      refresh.
    - force=True -> rebuild (all users, or one user when a username is given).
    - LLM disabled or failed -> deterministic heuristic profile, cached like
      any other row.

No new dependencies: everything runs off SQLite + the existing requests
client in app.core.llm_client.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

from app.core import llm_client
from app.core.domain_taxonomy import (
    _canonical,
    heuristic_domains,
    heuristic_kind,
    load_domains,
)
from app.db.init_db import get_conn

DOMAIN_PROMPT_VERSION = "v1"

_BATCH_SIZE = 5          # developers per LLM call
_MAX_FILES_IN_HASH = 20

ALLOWED_KINDS = ("bug", "feature", "docs", "test", "refactor", "performance", "security", "chore")

_MAX_PROFILES_PER_RUN_ENV = "LLM_MAX_PROFILES_PER_RUN"
_MAX_PROFILES_PER_RUN_DEFAULT = 100

_SYSTEM_PROMPT = (
    "You build evidence-based developer expertise profiles. Return ONLY valid JSON."
)


# ── Evidence gathering (SQL only, no extra GitHub calls) ──────────────────────

def collect_evidence(repo: str, username: str) -> dict:
    """Collect everything we already ingested about a developer in one repo."""
    conn = get_conn()

    resolved_rows = conn.execute(
        """
        SELECT i.number, i.title, i.body, i.labels, i.closed_at
        FROM issues i
        JOIN issue_pr_links l ON l.repo=i.repo AND l.issue_num=i.number
        WHERE i.repo=? AND l.resolver=? AND i.state='closed'
          AND (i.state_reason IS NULL OR i.state_reason != 'not_planned')
        ORDER BY i.closed_at DESC
        LIMIT 20
        """,
        (repo, username),
    ).fetchall()

    resolved_list = [
        {
            "number": r["number"],
            "title": r["title"] or "",
            "labels": _loads(r["labels"], []),
            "body": (r["body"] or "")[:300],
        }
        for r in resolved_rows
    ]

    resolved_count = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM issues i
        JOIN issue_pr_links l ON l.repo=i.repo AND l.issue_num=i.number
        WHERE i.repo=? AND l.resolver=? AND i.state='closed'
          AND (i.state_reason IS NULL OR i.state_reason != 'not_planned')
        """,
        (repo, username),
    ).fetchone()["c"]

    commit_rows = conn.execute(
        """
        SELECT message FROM commits
        WHERE repo=? AND author=?
        ORDER BY created_at DESC
        LIMIT 30
        """,
        (repo, username),
    ).fetchall()
    commit_count = conn.execute(
        "SELECT COUNT(*) AS c FROM commits WHERE repo=? AND author=?",
        (repo, username),
    ).fetchone()["c"]

    commit_messages = [(r["message"] or "").strip()[:200] for r in commit_rows if (r["message"] or "").strip()]

    pr_rows = conn.execute(
        """
        SELECT title FROM pull_requests
        WHERE repo=? AND author=? AND merged_at IS NOT NULL
        ORDER BY merged_at DESC
        LIMIT 15
        """,
        (repo, username),
    ).fetchall()
    pr_titles = [r["title"] or "" for r in pr_rows if (r["title"] or "").strip()]

    file_counts: dict[str, int] = {}
    for row in conn.execute(
        "SELECT files_json FROM commits WHERE repo=? AND author=? ORDER BY created_at DESC LIMIT 200",
        (repo, username),
    ).fetchall():
        try:
            files = json.loads(row["files_json"] or "[]")
        except (TypeError, ValueError):
            files = []
        for f in files:
            if f:
                file_counts[f] = file_counts.get(f, 0) + 1

    conn.close()

    top_files = [f for f, _ in sorted(file_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20]]

    return {
        "username": username,
        "resolved_issues": resolved_list,
        "commit_messages": commit_messages,
        "top_files": top_files,
        "pr_titles": pr_titles,
        "resolved_count": resolved_count,
        "commit_count": commit_count,
    }


def has_history(evidence: dict) -> bool:
    """A real candidate has at least one commit or one resolved issue."""
    return bool(evidence.get("resolved_count") or evidence.get("commit_count"))


def _loads(raw, default):
    try:
        return json.loads(raw) if raw else default
    except (TypeError, ValueError):
        return default


def evidence_hash(evidence: dict) -> str:
    canonical = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
    parts = "|".join([llm_client.model_name(), DOMAIN_PROMPT_VERSION, canonical])
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


# ── Prompts ───────────────────────────────────────────────────────────────────

def _evidence_block(evidence: dict) -> str:
    lines = [f"Developer: {evidence['username']}"]

    issues = evidence.get("resolved_issues") or []
    if issues:
        lines.append("Resolved issues (recent first):")
        for i in issues:
            lines.append(f"  - #{i['number']}: {i['title']} [labels: {', '.join(i['labels']) if i['labels'] else 'none'}]")
    else:
        lines.append("Resolved issues: (none)")

    messages = evidence.get("commit_messages") or []
    if messages:
        lines.append("Commit messages:")
        for m in messages:
            lines.append(f"  - {m}")
    else:
        lines.append("Commit messages: (none)")

    top_files = evidence.get("top_files") or []
    lines.append(f"Most-touched files: {', '.join(top_files) if top_files else '(none)'}")

    prs = evidence.get("pr_titles") or []
    if prs:
        lines.append("Authored merged PRs:")
        for t in prs:
            lines.append(f"  - {t}")

    return "\n".join(lines)


def _build_profiles_prompt(evidences: list[dict]) -> str:
    """One prompt for 1..N developers. For N==1 it is a single profile call."""
    domains_line = "; ".join(f"{d['name']}: {d['description']}" for d in load_domains())
    multiple = len(evidences) > 1
    blocks = "\n\n".join(_evidence_block(e) for e in evidences)

    return (
        f"Allowed domains: {domains_line}\n"
        "Evidence:\n"
        f"{blocks}\n"
        "\n"
        + (
            "Return a profile for EACH developer:\n"
            '{"profiles": [{"username": "...", "domains": [...], "preferred_kinds": [...], "summary": "..."}]}\n'
            if multiple
            else
            '{"domains": [{"name": "<allowed>", "weight": 0.0-1.0, "evidence": "short reason"}],\n'
            ' "preferred_kinds": ["bug", "feature"],\n'
            ' "summary": "one sentence, max 200 chars"}\n'
        )
        + "Rules: 1-4 domains, weights sum to 1.0, only allowed names, "
          "base every domain on the evidence above."
    )


# ── Validation / heuristic fallback ──────────────────────────────────────────

def _validate_profile(raw: dict, username: str) -> dict | None:
    """Coerce an LLM response into the canonical profile shape."""
    if not isinstance(raw, dict):
        return None

    items: dict[str, tuple[float, str]] = {}
    for item in raw.get("domains") or []:
        if isinstance(item, dict):
            name = item.get("name")
            try:
                weight = float(item.get("weight", item.get("confidence", 0.5)))
            except (TypeError, ValueError):
                weight = 0.5
            ev = str(item.get("evidence") or "")[:200]
        elif isinstance(item, str):
            name, weight, ev = item, 0.5, ""
        else:
            continue
        canonical = _canonical(name) if name else None
        if not canonical:
            continue
        weight = min(max(weight, 0.0), 1.0)
        if canonical not in items or weight > items[canonical][0]:
            items[canonical] = (weight, ev)

    ranked = sorted(items.items(), key=lambda kv: (-kv[1][0], kv[0]))[:4]
    if not ranked:
        return None
    total = sum(w for _, (w, _) in ranked)
    domains = [
        {
            "name": name,
            "weight": round((w / total) if total > 0 else (1.0 / len(ranked)), 4),
            "evidence": ev,
        }
        for name, (w, ev) in ranked
    ]

    kinds = []
    for k in raw.get("preferred_kinds") or []:
        k = str(k).strip().lower()
        if k in ALLOWED_KINDS and k not in kinds:
            kinds.append(k)
    kinds = kinds[:5]

    summary = " ".join(str(raw.get("summary") or "").split())[:300]

    return {
        "domains": domains,
        "preferred_kinds": kinds,
        "summary": summary,
        "model": llm_client.model_name(),
    }


def _heuristic_profile(evidence: dict) -> dict:
    """Deterministic domain weights scored from the evidence itself."""
    scores: dict[str, float] = {}

    def _add(domains: list[dict], weight: float):
        for d in domains:
            scores[d["name"]] = scores.get(d["name"], 0.0) + weight

    for iss in evidence.get("resolved_issues") or []:
        _add(heuristic_domains(iss.get("title", ""), iss.get("body", ""), iss.get("labels") or []), 1.0)
    for msg in evidence.get("commit_messages") or []:
        _add(heuristic_domains(msg, "", []), 1.0)
    for title in evidence.get("pr_titles") or []:
        _add(heuristic_domains(title, "", []), 1.0)
    for f in evidence.get("top_files") or []:
        _add(heuristic_domains("", "", [], [f]), 2.0)

    if not scores:
        scores = {"backend": 1.0}

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
    total = sum(w for _, w in ranked)
    domains = [
        {
            "name": name,
            "weight": round(w / total, 4) if total > 0 else round(1.0 / len(ranked), 4),
            "evidence": "derived from their resolved issues, commits, and files",
        }
        for name, w in ranked
    ]

    kind_counts: dict[str, int] = {}
    for iss in evidence.get("resolved_issues") or []:
        kind = heuristic_kind(iss.get("title", ""), iss.get("body", ""), iss.get("labels") or [])
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    preferred_kinds = [k for k, _ in sorted(kind_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:2]]

    top_names = ", ".join(d["name"] for d in domains[:2])
    summary = (
        f"Derived from {evidence['resolved_count']} resolved issues and "
        f"{evidence['commit_count']} commits — strongest in {top_names}."
    )

    return {
        "domains": domains,
        "preferred_kinds": preferred_kinds,
        "summary": summary[:300],
        "model": "heuristic",
    }


# ── Persistence ──────────────────────────────────────────────────────────────

def _upsert(repo: str, username: str, profile: dict, ev_hash: str):
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO developer_domains
            (repo, username, domains_json, preferred_kinds_json, summary,
             evidence_hash, model, built_at)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(repo, username) DO UPDATE SET
            domains_json=excluded.domains_json,
            preferred_kinds_json=excluded.preferred_kinds_json,
            summary=excluded.summary,
            evidence_hash=excluded.evidence_hash,
            model=excluded.model,
            built_at=excluded.built_at
        """,
        (
            repo,
            username,
            json.dumps(profile["domains"]),
            json.dumps(profile["preferred_kinds"]),
            profile["summary"],
            ev_hash,
            profile["model"],
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def _fetch_cached(repo: str, username: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM developer_domains WHERE repo=? AND username=?",
        (repo, username),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _row_to_profile(row: dict) -> dict:
    return {
        "domains": _loads(row.get("domains_json"), []),
        "preferred_kinds": _loads(row.get("preferred_kinds_json"), []),
        "summary": row.get("summary") or "",
        "evidence_hash": row.get("evidence_hash") or "",
        "model": row.get("model") or "",
        "built_at": row.get("built_at") or "",
    }


# ── Candidates ───────────────────────────────────────────────────────────────

def _candidate_usernames(conn, repo: str) -> list[str]:
    """Contributors with real previous history (same filter as profile_builder)."""
    rows = conn.execute(
        """
        SELECT username FROM repository_developers
        WHERE repo=? AND contributions > 0
        UNION
        SELECT resolver FROM issue_pr_links WHERE repo=? AND resolver IS NOT NULL AND resolver != ''
        UNION
        SELECT author FROM commits WHERE repo=? AND author != ''
        """,
        (repo, repo, repo),
    ).fetchall()
    return [r["username"] for r in rows]


def _max_profiles() -> int:
    try:
        return max(int(os.environ.get(_MAX_PROFILES_PER_RUN_ENV, str(_MAX_PROFILES_PER_RUN_DEFAULT)) or 0), 0)
    except ValueError:
        return _MAX_PROFILES_PER_RUN_DEFAULT


# ── Public API ───────────────────────────────────────────────────────────────

def load_domain_profiles(repo: str) -> dict[str, dict]:
    """Load all cached domain profiles for a repo, keyed by username."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM developer_domains WHERE repo=?", (repo,)
    ).fetchall()
    conn.close()
    return {r["username"]: _row_to_profile(dict(r)) for r in rows}


def build_domain_profile(repo: str, username: str, force: bool = False) -> dict | None:
    """
    Build (or reuse) the domain profile for one developer.

    Returns None when the developer has no commit / resolved-issue history —
    they are never a real candidate.
    """
    evidence = collect_evidence(repo, username)
    if not has_history(evidence):
        return None

    cached = _fetch_cached(repo, username)
    if cached and not force:
        return _row_to_profile(cached)

    ev_hash = evidence_hash(evidence)

    profile = None
    if llm_client.is_enabled():
        raw = llm_client.generate_json(
            _build_profiles_prompt([evidence]), system=_SYSTEM_PROMPT
        )
        if raw is not None:
            profile = _validate_profile(raw, username)

    if profile is None:
        profile = _heuristic_profile(evidence)

    _upsert(repo, username, profile, ev_hash)
    return profile


def build_domain_profiles(repo: str, force: bool = False, limit: int = None, progress=None) -> dict:
    """
    Build domain profiles for every contributor with previous history.

    Skips any candidate that already has a row unless force=True. Batches
    up to _BATCH_SIZE developers per LLM call; batch members whose profile
    fails validation are retried once individually, then heuristic fallback.

    limit: max profiles to build this run (None -> LLM_MAX_PROFILES_PER_RUN,
    0 -> no cap). progress: optional callable(str) for pipeline status.
    """
    if limit is None:
        limit = _max_profiles()

    start_calls = llm_client.call_stats()["llm_calls"]

    conn = get_conn()
    candidates = _candidate_usernames(conn, repo)
    conn.close()

    cached_map = load_domain_profiles(repo)
    if force:
        pending = [c for c in candidates if c]
    else:
        pending = [c for c in candidates if c not in cached_map]
    if limit and len(pending) > limit:
        pending = pending[:limit]

    cached_n = sum(1 for c in candidates if not force and c in cached_map)
    built = heuristic_n = skipped = 0

    i = 0
    while i < len(pending):
        batch = pending[i : i + _BATCH_SIZE]
        i += _BATCH_SIZE

        # Collect evidence; drop candidates without any real history.
        evidences: dict[str, dict] = {}
        for user in batch:
            ev = collect_evidence(repo, user)
            if has_history(ev):
                evidences[user] = ev
            else:
                skipped += 1
        if not evidences:
            continue

        llm_profiles: dict[str, dict] = {}
        leftovers = []
        if llm_client.is_enabled():
            raw = llm_client.generate_json(
                _build_profiles_prompt(list(evidences.values())), system=_SYSTEM_PROMPT
            )
            parsed = raw.get("profiles") if isinstance(raw, dict) else None
            if isinstance(parsed, list):
                by_user = {
                    p.get("username"): p
                    for p in parsed
                    if isinstance(p, dict) and p.get("username")
                }
                for user in evidences:
                    profile = _validate_profile(by_user.get(user), user)
                    if profile:
                        llm_profiles[user] = profile
                    else:
                        leftovers.append(user)
            else:
                leftovers = list(evidences.keys())

            # Retrying individually before falling back to heuristics.
            for user in leftovers:
                raw_single = llm_client.generate_json(
                    _build_profiles_prompt([evidences[user]]), system=_SYSTEM_PROMPT
                )
                profile = _validate_profile(raw_single, user) if raw_single else None
                if profile:
                    llm_profiles[user] = profile
        else:
            leftovers = list(evidences.keys())

        for user, profile in llm_profiles.items():
            _upsert(repo, user, profile, evidence_hash(evidences[user]))
            built += 1

        for user in leftovers:
            if user in llm_profiles:
                continue  # covered above
            profile = _heuristic_profile(evidences[user])
            _upsert(repo, user, profile, evidence_hash(evidences[user]))
            heuristic_n += 1

        done = built + heuristic_n
        if progress and done % 10 == 0:
            progress(f"Built {done} domain profiles for {repo}")

    llm_calls = llm_client.call_stats()["llm_calls"] - start_calls
    print(
        f"[profiler] {repo}: built={built} cached={cached_n} heuristic={heuristic_n} "
        f"skipped={skipped} llm_calls={llm_calls}"
    )
    return {
        "built": built,
        "cached": cached_n,
        "heuristic": heuristic_n,
        "skipped": skipped,
        "llm_calls": llm_calls,
    }


def ensure_domain_profiles(repo: str, usernames: list[str] = None, cap: int = 10) -> dict:
    """
    On-demand build for the missing profiles among `usernames` (or all repo
    candidates). `cap` keeps a synchronous UI request from timing out; users
    beyond the cap keep contributing 0 to the domain signal until a later run.
    """
    if usernames is None:
        conn = get_conn()
        usernames = _candidate_usernames(conn, repo)
        conn.close()

    cached_map = load_domain_profiles(repo)
    seen = set()
    pending = []
    for u in usernames or []:
        if u and u not in seen:
            seen.add(u)
            if u not in cached_map:
                pending.append(u)
    if cap and len(pending) > cap:
        pending = pending[:cap]

    built = heuristic_n = skipped = 0
    start_calls = llm_client.call_stats()["llm_calls"]
    for u in pending:
        evidence = collect_evidence(repo, u)
        if not has_history(evidence):
            skipped += 1
            continue

        profile = None
        if llm_client.is_enabled():
            raw = llm_client.generate_json(
                _build_profiles_prompt([evidence]), system=_SYSTEM_PROMPT
            )
            if raw is not None:
                profile = _validate_profile(raw, u)
        if profile is None:
            profile = _heuristic_profile(evidence)
            heuristic_n += 1
        else:
            built += 1
        _upsert(repo, u, profile, evidence_hash(evidence))

    llm_calls = llm_client.call_stats()["llm_calls"] - start_calls
    return {
        "built": built,
        "cached": len([u for u in seen if u in cached_map]),
        "heuristic": heuristic_n,
        "skipped": skipped,
        "llm_calls": llm_calls,
    }
