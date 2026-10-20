"""
Issue classification with a SQLite cache.

Classification is LLM-backed (Gemini via app.core.llm_client) and falls back
to deterministic heuristics when the LLM is disabled or fails. Results are
cached in `issue_classifications` keyed by (repo, issue_num) with an
`input_hash` so unchanged issues are never reclassified.

Cache rules:
    - Row exists + hash matches + force=False  -> reuse (zero LLM calls)
    - Cached model == "heuristic" + LLM enabled -> retry with the LLM
    - LLM failure -> heuristic fallback, NOT cached as a failure (the
      heuristic row is cached, but the next run retries the LLM)
"""
import hashlib
import json
import os
from datetime import datetime, timezone

from app.core import llm_client
from app.core.domain_taxonomy import (
    heuristic_classification,
    heuristic_domains,
    load_domains,
    normalise_domains,
)
from app.db.init_db import get_conn

CLASSIFIER_PROMPT_VERSION = "v1"

ALLOWED_KINDS = ("bug", "feature", "docs", "test", "refactor", "performance", "security", "chore")
ALLOWED_SEVERITIES = ("low", "medium", "high", "critical")

_SYSTEM_PROMPT = (
    "You are a senior open-source issue triage analyst. Return ONLY valid JSON."
)


def _labels_list(issue: dict) -> list[str]:
    """Normalise labels from a JSON string, name-dict list, or plain list."""
    labels = issue.get("labels") or []
    if isinstance(labels, str):
        try:
            labels = json.loads(labels)
        except (TypeError, ValueError):
            labels = [labels]
    names = []
    for label in labels:
        name = label.get("name", "") if isinstance(label, dict) else label
        name = str(name).strip()
        if name:
            names.append(name)
    return names


def _input_hash(repo: str, issue: dict, labels: list[str]) -> str:
    """Hash of everything that should trigger a reclassify when changed."""
    parts = "|".join(
        [
            llm_client.model_name(),
            CLASSIFIER_PROMPT_VERSION,
            repo,
            str(issue.get("number", "")),
            str(issue.get("title") or ""),
            str(issue.get("body") or "")[:4000],
            ",".join(sorted(labels)),
        ]
    )
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


def _build_prompt(repo: str, issue: dict, labels: list[str]) -> str:
    domains_line = "; ".join(f"{d['name']}: {d['description']}" for d in load_domains())
    body = str(issue.get("body") or "")[:4000]
    return (
        f"Allowed domains: {domains_line}\n"
        "Issue:\n"
        f"  repo: {repo}\n"
        f"  number: #{issue.get('number', '')}\n"
        f"  title: {issue.get('title') or ''}\n"
        f"  labels: {', '.join(labels) if labels else '(none)'}\n"
        f"  body: {body}\n"
        "\n"
        "Return:\n"
        "{\n"
        '  "kind": "bug|feature|docs|test|refactor|performance|security|chore",\n'
        '  "domains": [{"name": "<allowed domain>", "confidence": 0.0-1.0}],\n'
        '  "difficulty": 1-5,\n'
        '  "severity": "low|medium|high|critical",\n'
        '  "summary": "one sentence, max 200 chars",\n'
        '  "required_skills": ["short skill names"],\n'
        '  "confidence": 0.0-1.0\n'
        "}\n"
        "Rules: 1-3 domains, only from the allowed list."
    )


def _validate(raw: dict, issue: dict, labels: list[str]) -> dict:
    """Coerce an LLM response into the canonical classification shape."""
    kind = str(raw.get("kind") or "").strip().lower()
    if kind not in ALLOWED_KINDS:
        kind = "chore"

    domains = normalise_domains(raw.get("domains"), max_domains=3)
    if not domains:
        domains = heuristic_domains_fallback(issue, labels)

    try:
        difficulty = int(raw.get("difficulty"))
    except (TypeError, ValueError):
        difficulty = 3
    difficulty = min(max(difficulty, 1), 5)

    severity = str(raw.get("severity") or "").strip().lower()
    if severity not in ALLOWED_SEVERITIES:
        severity = "medium"

    try:
        confidence = float(raw.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = min(max(confidence, 0.0), 1.0)

    skills = raw.get("required_skills") or []
    if not isinstance(skills, list):
        skills = [skills]
    skills = [str(s).strip() for s in skills if str(s).strip()][:10]

    return {
        "kind": kind,
        "domains": domains,
        "difficulty": difficulty,
        "severity": severity,
        "summary": " ".join(str(raw.get("summary") or "").split())[:300],
        "required_skills": skills,
        "confidence": round(confidence, 4),
        "model": llm_client.model_name(),
    }


def heuristic_domains_fallback(issue: dict, labels: list[str]) -> list[dict]:
    files = issue.get("files") if isinstance(issue.get("files"), list) else []
    return heuristic_domains(
        str(issue.get("title") or ""),
        str(issue.get("body") or ""),
        labels,
        files,
    )


def _heuristic(issue: dict, labels: list[str]) -> dict:
    files = issue.get("files") if isinstance(issue.get("files"), list) else []
    result = heuristic_classification(
        str(issue.get("title") or ""),
        str(issue.get("body") or ""),
        labels,
        files,
    )
    # Guarantee taxonomy-valid domains even if the heuristic config drifts.
    result["domains"] = normalise_domains(result.get("domains"), max_domains=3) or heuristic_domains_fallback(issue, labels)
    return result


def _upsert(repo: str, issue_num: int, classification: dict, input_hash: str):
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO issue_classifications
            (repo, issue_num, kind, domains_json, difficulty, severity, summary,
             required_skills_json, confidence, model, input_hash, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(repo, issue_num) DO UPDATE SET
            kind=excluded.kind,
            domains_json=excluded.domains_json,
            difficulty=excluded.difficulty,
            severity=excluded.severity,
            summary=excluded.summary,
            required_skills_json=excluded.required_skills_json,
            confidence=excluded.confidence,
            model=excluded.model,
            input_hash=excluded.input_hash,
            created_at=excluded.created_at
        """,
        (
            repo,
            issue_num,
            classification["kind"],
            json.dumps(classification["domains"]),
            classification["difficulty"],
            classification["severity"],
            classification["summary"],
            json.dumps(classification["required_skills"]),
            classification["confidence"],
            classification["model"],
            input_hash,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def _fetch_cached(repo: str, issue_num: int) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM issue_classifications WHERE repo=? AND issue_num=?",
        (repo, issue_num),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _row_to_classification(row: dict) -> dict:
    """Parse a cached DB row into the API-facing classification shape."""
    def _loads(raw, default):
        try:
            return json.loads(raw) if raw else default
        except (TypeError, ValueError):
            return default

    return {
        "kind": row.get("kind", "chore"),
        "domains": _loads(row.get("domains_json"), []),
        "difficulty": row.get("difficulty", 3),
        "severity": row.get("severity", "medium"),
        "summary": row.get("summary") or "",
        "required_skills": _loads(row.get("required_skills_json"), []),
        "confidence": row.get("confidence", 0.0),
        "model": row.get("model", "heuristic"),
    }


def classify_issue(repo: str, issue: dict, force: bool = False) -> dict:
    """
    Classify one issue, reusing the cache when possible.

    `issue` needs at least {"number", "title", "body", "labels"}.
    Returns the classification dict (with "model" set to the generator).
    """
    issue_num = int(issue.get("number") or 0)
    labels = _labels_list(issue)
    input_hash = _input_hash(repo, issue, labels)

    cached = _fetch_cached(repo, issue_num) if issue_num else None
    if cached and not force:
        hash_matches = cached.get("input_hash") == input_hash
        llm_retry = cached.get("model") == "heuristic" and llm_client.is_enabled()
        if hash_matches and not llm_retry:
            return _row_to_classification(cached)

    classification = None
    if llm_client.is_enabled():
        result = llm_client.generate_json(_build_prompt(repo, issue, labels), system=_SYSTEM_PROMPT)
        if result is not None:
            classification = _validate(result, issue, labels)

    if classification is None:
        classification = _heuristic(issue, labels)

    if issue_num:
        _upsert(repo, issue_num, classification, input_hash)
    return classification


def load_classifications(repo: str) -> dict[int, dict]:
    """Load all cached classifications for a repo, keyed by issue number."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM issue_classifications WHERE repo=?", (repo,)
    ).fetchall()
    conn.close()
    return {int(r["issue_num"]): _row_to_classification(dict(r)) for r in rows}


def ensure_classified(repo: str, issue: dict) -> dict:
    """On-demand classification for a single issue (used by the UI)."""
    issue_num = int(issue.get("number") or 0)
    labels = _labels_list(issue)
    input_hash = _input_hash(repo, issue, labels)

    cached = _fetch_cached(repo, issue_num) if issue_num else None
    if cached and cached.get("input_hash") == input_hash:
        if not (cached.get("model") == "heuristic" and llm_client.is_enabled()):
            return _row_to_classification(cached)

    return classify_issue(repo, issue, force=True)


def classify_open_issues(repo: str, force: bool = False, limit: int = None, progress=None) -> dict:
    """
    Classify every open issue in a repo, skipping cached results.

    limit: max issues to classify this run (None -> LLM_MAX_ISSUES_PER_RUN,
    0 -> no cap). progress: optional callable(str) for pipeline status.
    """
    if limit is None:
        limit = max(int(os.environ.get("LLM_MAX_ISSUES_PER_RUN", "50") or 0), 0)

    start_calls = llm_client.call_stats()["llm_calls"]

    conn = get_conn()
    rows = conn.execute(
        """
        SELECT number, title, body, labels, state, created_at
        FROM issues
        WHERE repo=? AND state='open'
        ORDER BY created_at DESC
        """,
        (repo,),
    ).fetchall()
    conn.close()

    classified = cached_count = failed = 0
    for row in rows:
        issue = dict(row)
        issue_num = int(issue["number"])
        labels = _labels_list(issue)
        input_hash = _input_hash(repo, issue, labels)

        cached = _fetch_cached(repo, issue_num)
        if cached and not force:
            hash_matches = cached.get("input_hash") == input_hash
            llm_retry = cached.get("model") == "heuristic" and llm_client.is_enabled()
            if hash_matches and not llm_retry:
                cached_count += 1
                continue

        if limit and classified >= limit:
            break

        if llm_client.is_enabled():
            result = llm_client.generate_json(_build_prompt(repo, issue, labels), system=_SYSTEM_PROMPT)
            if result is not None:
                _upsert(repo, issue_num, _validate(result, issue, labels), input_hash)
                classified += 1
            else:
                _upsert(repo, issue_num, _heuristic(issue, labels), input_hash)
                classified += 1
                failed += 1
        else:
            _upsert(repo, issue_num, _heuristic(issue, labels), input_hash)
            classified += 1

        done = classified + cached_count
        if progress and done % 10 == 0:
            progress(f"Classified {done}/{len(rows)} issues for {repo}")

    llm_calls = llm_client.call_stats()["llm_calls"] - start_calls
    print(
        f"[classifier] {repo}: classified={classified} cached={cached_count} "
        f"failed={failed} llm_calls={llm_calls}"
    )
    return {
        "classified": classified,
        "cached": cached_count,
        "failed": failed,
        "llm_calls": llm_calls,
    }
