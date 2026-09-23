"""
Build and store per-developer expertise profiles from repository history.
"""
import json, re
from datetime import datetime, timezone
from db.init_db import get_conn


def _normalise_date(s: str) -> str:
    """
    Best-effort conversion of various date formats to an ISO 8601 string
    compatible with datetime.fromisoformat() (for recency_score).
    Handles:
      - "2001-10-18 11:51:14 -0400"  (bughub space-separated offset)
      - "2001-10-18T11:51:14"         (ISO w/o tz)
      - "2001-10-18T11:51:14Z"       (ISO Z)
      - "2001-10-18"                     (date only)
    Returns normalised ISO string or "" on failure.
    """
    if not s:
        return ""
    s = s.strip()

    # Already ISO compatible — try parse first
    for candidate in (s, s.replace("Z", "+00:00")):
        try:
            datetime.fromisoformat(candidate)
            return candidate
        except Exception:
            pass

    # "YYYY-MM-DD HH:MM:SS +NNNN" → replace " +" / " -" with "+" / "-" and pad offset
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})\s*([+-]\d{2}):?(\d{2})?$", s)
    if m:
        date, time, sign, mins = m.groups()
        mins = mins if mins else "00"
        try:
            iso = f"{date}T{time}{sign}{mins[:2]}:{mins[-2:]}"
            datetime.fromisoformat(iso)
            return iso
        except Exception:
            pass

    # Same pattern but offset without colon: "+0400"
    m2 = re.match(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})\s*([+-]\d{2})(\d{2})$", s)
    if m2:
        date, time, sign_hh, mm = m2.groups()
        try:
            iso = f"{date}T{time}{sign_hh}:{mm}"
            datetime.fromisoformat(iso)
            return iso
        except Exception:
            pass

    # Date only
    m3 = re.match(r"^(\d{4}-\d{2}-\d{2})$", s)
    if m3:
        return s + "T00:00:00+00:00"

    # Last resort: strptime with common formats
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            continue

    return ""


def build_profiles(repo: str, cutoff_date: str = None):
    """
    Build profiles for all developers in a repo.
    cutoff_date: ISO string — only use data before this date (for replay evaluation).
    """
    conn = get_conn()

    # Include repository contributors with no history so new repos still have candidates.
    resolvers = conn.execute("""
        SELECT resolver AS username FROM issue_pr_links
        WHERE repo=? AND resolver IS NOT NULL AND resolver != ''
        UNION
        SELECT username FROM repository_developers WHERE repo=?
    """, (repo, repo)).fetchall()

    profiles = {}
    for row in resolvers:
        dev = row["username"]
        profile = _build_single(conn, repo, dev, cutoff_date)
        if profile:
            profiles[dev] = profile
            _save_profile(conn, repo, dev, profile)

    conn.commit()
    conn.close()
    print(f"[profiles] built {len(profiles)} profiles for {repo}")
    return profiles

def _build_single(conn, repo: str, developer: str, cutoff_date: str = None) -> dict:
    """Build a single developer profile."""

    # Date filter clause
    date_filter = ""
    date_params_issues = [repo, developer]
    date_params_commits = [repo, developer]
    if cutoff_date:
        date_filter_issues = " AND i.closed_at < ?"
        date_filter_commits = " AND c.created_at < ?"
        date_params_issues.append(cutoff_date)
        date_params_commits.append(cutoff_date)
    else:
        date_filter_issues = ""
        date_filter_commits = ""

    # Get resolved issues
    resolved = conn.execute(f"""
        SELECT i.title, i.body, i.labels, i.closed_at
        FROM issues i
        JOIN issue_pr_links l ON l.repo=i.repo AND l.issue_num=i.number
        WHERE i.repo=? AND l.resolver=? AND i.state='closed' {date_filter_issues}
        ORDER BY i.closed_at DESC
    """, date_params_issues).fetchall()

    if not resolved and cutoff_date:
        return None

    # Aggregate resolved issue text
    resolved_texts_list = []
    for r in resolved:
        issue_text = f"{r['title'] or ''} {r['body'] or ''}"
        if issue_text.strip():
            resolved_texts_list.append(issue_text)

    resolved_text = " ".join(resolved_texts_list)[:50000]

    # Individual issue texts for past_issue_similarity signal
    resolved_issues_json = json.dumps(resolved_texts_list[:100])

    # Aggregate component/label counts
    components = {}
    for r in resolved:
        try:
            labels = json.loads(r["labels"] or "[]")
        except Exception:
            labels = []
        for l in labels:
            components[l.lower()] = components.get(l.lower(), 0) + 1

    # Get commits and file changes
    commits_data = conn.execute(f"""
        SELECT files_json, created_at FROM commits
        WHERE repo=? AND author=? {date_filter_commits}
        ORDER BY created_at DESC LIMIT 500
    """, date_params_commits).fetchall()

    files = {}
    last_active = None
    for c in commits_data:
        c_date_raw = c["created_at"] or ""
        c_date = _normalise_date(c_date_raw) if c_date_raw else ""
        if c_date and (last_active is None or c_date > last_active):
            last_active = c_date
        try:
            file_list = json.loads(c["files_json"] or "[]")
            for f in file_list:
                files[f] = files.get(f, 0) + 1
        except Exception:
            pass

    # Bughub / datasets without commits: fall back to latest resolved closed_at
    if not last_active:
        for r in resolved:
            closed_raw = (r["closed_at"] or "").strip()
            if not closed_raw:
                continue
            # Try to normalise bughub-style date (with space-separated timezone offset)
            # to ISO 8601 so recency_score can parse it.
            closed_iso = _normalise_date(closed_raw)
            if closed_iso and (last_active is None or closed_iso > last_active):
                last_active = closed_iso

    # Current open issue count
    open_count = 0
    open_issues = conn.execute(
        "SELECT assignees_json FROM issues WHERE repo=? AND state='open'", (repo,)
    ).fetchall()
    for issue in open_issues:
        try:
            if developer in json.loads(issue["assignees_json"] or "[]"):
                open_count += 1
        except Exception:
            pass

    return {
        "username":         developer,
        "repo":             repo,
        "files_json":       json.dumps(files),
        "components_json":  json.dumps(components),
        "resolved_text":    resolved_text,
        "resolved_issues_json": resolved_issues_json,
        "last_active":      last_active or "",
        "open_issue_count": open_count,
        "resolved_count":   len(resolved),
    }

def _save_profile(conn, repo: str, developer: str, profile: dict):
    conn.execute("""
        INSERT INTO developer_profiles
            (username, repo, files_json, components_json, resolved_text,
             resolved_issues_json, last_active, open_issue_count, resolved_count, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(username, repo) DO UPDATE SET
            files_json=excluded.files_json,
            components_json=excluded.components_json,
            resolved_text=excluded.resolved_text,
            resolved_issues_json=excluded.resolved_issues_json,
            last_active=excluded.last_active,
            open_issue_count=excluded.open_issue_count,
            resolved_count=excluded.resolved_count,
            updated_at=excluded.updated_at
    """, (
        developer, repo,
        profile["files_json"], profile["components_json"],
        profile["resolved_text"], profile["resolved_issues_json"],
        profile["last_active"], profile["open_issue_count"], profile["resolved_count"],
        datetime.now(timezone.utc).isoformat()
    ))

def load_profiles(repo: str) -> list:
    """Load all stored profiles for a repo."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM developer_profiles WHERE repo=?", (repo,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def load_profile(repo: str, username: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM developer_profiles WHERE repo=? AND username=?",
        (repo, username)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
