"""
Links resolved issues to the developer who closed them.
Three strategies: PR body keywords, GitHub timeline, commit messages.
"""
import re
import json
from db.init_db import get_conn

CLOSE_PATTERNS = re.compile(
    r'(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*#(\d+)',
    re.IGNORECASE
)

def _extract_issue_refs(text: str) -> list:
    if not text:
        return []
    return [int(m) for m in CLOSE_PATTERNS.findall(text)]

def link_via_pr_bodies(repo: str):
    """Strategy 1 — scan PR body text for 'Closes #X'."""
    conn = get_conn()
    prs = conn.execute(
        "SELECT number, body, merged_by, merged_at FROM pull_requests WHERE repo=? AND merged_at IS NOT NULL",
        (repo,)
    ).fetchall()
    linked = 0
    for pr in prs:
        refs = _extract_issue_refs(pr["body"] or "")
        for issue_num in refs:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO issue_pr_links (repo, issue_num, pr_num, link_type, resolver)
                    VALUES (?,?,?,?,?)
                """, (repo, issue_num, pr["number"], "body_keyword", pr["merged_by"]))
                if pr["merged_by"]:
                    conn.execute(
                        "INSERT OR IGNORE INTO developers (username, display_name) VALUES (?,?)",
                        (pr["merged_by"], pr["merged_by"])
                    )
                linked += 1
            except Exception:
                pass
    conn.commit()
    conn.close()
    print(f"  [linker] strategy 1 (PR body): {linked} links for {repo}")
    return linked

def link_via_timeline(repo: str, max_issues: int = 200):
    """Strategy 2 — GitHub timeline events."""
    from ingestion.github_fetcher import fetch_issue_timeline
    conn = get_conn()
    issues = conn.execute(
        "SELECT number FROM issues WHERE repo=? AND state='closed' LIMIT ?",
        (repo, max_issues)
    ).fetchall()
    linked = 0
    for row in issues:
        num = row["number"]
        timeline = fetch_issue_timeline(repo, num)
        for event in (timeline or []):
            if event.get("event") == "closed" and event.get("actor"):
                actor = event["actor"]["login"]
                # Find linked PR if any
                pr_num = None
                if event.get("commit_id"):
                    # Find PR that contains this commit
                    pr_row = conn.execute(
                        "SELECT number FROM pull_requests WHERE repo=? AND merged_by=? LIMIT 1",
                        (repo, actor)
                    ).fetchone()
                    if pr_row:
                        pr_num = pr_row["number"]
                if pr_num:
                    try:
                        conn.execute("""
                            INSERT OR IGNORE INTO issue_pr_links (repo, issue_num, pr_num, link_type, resolver)
                            VALUES (?,?,?,?,?)
                        """, (repo, num, pr_num, "timeline", actor))
                        conn.execute(
                            "INSERT OR IGNORE INTO developers (username, display_name) VALUES (?,?)",
                            (actor, actor)
                        )
                        linked += 1
                    except Exception:
                        pass
    conn.commit()
    conn.close()
    print(f"  [linker] strategy 2 (timeline): {linked} links for {repo}")
    return linked

def link_via_commit_messages(repo: str):
    """Strategy 3 — scan commit messages for issue refs."""
    conn = get_conn()
    commits = conn.execute(
        "SELECT sha, author, message, created_at FROM commits WHERE repo=?",
        (repo,)
    ).fetchall()
    linked = 0
    for c in commits:
        refs = _extract_issue_refs(c["message"] or "")
        for issue_num in refs:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO issue_pr_links (repo, issue_num, pr_num, link_type, resolver)
                    VALUES (?,?,?,?,?)
                """, (repo, issue_num, 0, "commit_message", c["author"]))
                if c["author"]:
                    conn.execute(
                        "INSERT OR IGNORE INTO developers (username, display_name) VALUES (?,?)",
                        (c["author"], c["author"])
                    )
                linked += 1
            except Exception:
                pass
    conn.commit()
    conn.close()
    print(f"  [linker] strategy 3 (commits): {linked} links for {repo}")
    return linked

def run_all_strategies(repo: str):
    total = 0
    total += link_via_pr_bodies(repo)
    total += link_via_commit_messages(repo)
    print(f"  [linker] total links for {repo}: {total}")
    return total

def get_resolver(repo: str, issue_num: int) -> str | None:
    """Get the developer who resolved an issue."""
    conn = get_conn()
    row = conn.execute(
        "SELECT resolver FROM issue_pr_links WHERE repo=? AND issue_num=? AND resolver IS NOT NULL LIMIT 1",
        (repo, issue_num)
    ).fetchone()
    conn.close()
    return row["resolver"] if row else None

if __name__ == "__main__":
    import sys
    repo = sys.argv[1] if len(sys.argv) > 1 else "pallets/click"
    run_all_strategies(repo)
