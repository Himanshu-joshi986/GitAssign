"""
Load fetched GitHub data from cache into the database.
"""
import json
from datetime import datetime
from db.init_db import get_conn

def upsert_issues(repo: str, issues: list):
    conn = get_conn()
    inserted = 0
    for i in issues:
        labels = json.dumps([l["name"] for l in i.get("labels", [])])
        try:
            conn.execute("""
                INSERT INTO issues (repo, number, title, body, labels, state, created_at, closed_at, author, assignees_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(repo, number) DO UPDATE SET
                        state=excluded.state, closed_at=excluded.closed_at, labels=excluded.labels,
                        assignees_json=excluded.assignees_json
            """, (
                repo,
                i["number"],
                i.get("title", ""),
                i.get("body", "") or "",
                labels,
                i.get("state", ""),
                i.get("created_at", ""),
                i.get("closed_at", ""),
                i.get("user", {}).get("login", "") if i.get("user") else "",
                json.dumps([a.get("login", "") for a in i.get("assignees", []) if a.get("login")])
            ))
            inserted += 1
        except Exception as e:
            print(f"  [warn] issue {i.get('number')}: {e}")
    conn.commit()
    conn.close()
    print(f"  [db] upserted {inserted} issues for {repo}")

def upsert_repository_developers(repo: str, contributors: list):
    conn = get_conn()
    for contributor in contributors:
        username = contributor.get("login", "")
        if not username:
            continue
        conn.execute("""
            INSERT INTO repository_developers (repo, username, display_name, account_type)
            VALUES (?,?,?,?)
            ON CONFLICT(repo, username) DO UPDATE SET
                display_name=excluded.display_name, account_type=excluded.account_type
        """, (repo, username, contributor.get("name") or username, contributor.get("type", "User")))
        conn.execute("INSERT OR IGNORE INTO developers (username, display_name) VALUES (?,?)",
                     (username, contributor.get("name") or username))
    conn.commit()
    conn.close()

def upsert_pull_requests(repo: str, prs: list):
    conn = get_conn()
    inserted = 0
    for pr in prs:
        merged_by = None
        if pr.get("merged_by"):
            merged_by = pr["merged_by"].get("login")
        try:
            conn.execute("""
                INSERT INTO pull_requests (repo, number, title, body, merged_at, merged_by, state)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(repo, number) DO UPDATE SET
                    merged_at=excluded.merged_at, merged_by=excluded.merged_by
            """, (
                repo, pr["number"],
                pr.get("title", ""),
                pr.get("body", "") or "",
                pr.get("merged_at", ""),
                merged_by,
                pr.get("state", "")
            ))
            inserted += 1
        except Exception as e:
            print(f"  [warn] PR {pr.get('number')}: {e}")
    conn.commit()
    conn.close()
    print(f"  [db] upserted {inserted} PRs for {repo}")

def upsert_commits(repo: str, commits: list):
    conn = get_conn()
    inserted = 0
    for c in commits:
        sha = c.get("sha", "")
        author = ""
        if c.get("author"):
            author = c["author"].get("login", "")
        elif c.get("commit", {}).get("author"):
            author = c["commit"]["author"].get("name", "")
        msg = c.get("commit", {}).get("message", "")
        date = c.get("commit", {}).get("author", {}).get("date", "")
        try:
            conn.execute("""
                INSERT INTO commits (sha, repo, author, message, files_json, created_at)
                VALUES (?,?,?,?,?,?)
                    ON CONFLICT(sha) DO UPDATE SET
                        author=excluded.author, message=excluded.message,
                        files_json=excluded.files_json, created_at=excluded.created_at
                """, (sha, repo, author, msg,
                      json.dumps([f.get("filename") for f in c.get("files", []) if f.get("filename")]), date))
            inserted += 1
        except Exception as e:
            print(f"  [warn] commit {sha[:7]}: {e}")
    conn.commit()
    conn.close()
    print(f"  [db] upserted {inserted} commits for {repo}")

def upsert_developer(username: str, display_name: str = ""):
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO developers (username, display_name)
        VALUES (?,?)
    """, (username, display_name or username))
    conn.commit()
    conn.close()

def load_repo(repo: str):
    """Load all cached data for a repo into the database."""
    from ingestion.github_fetcher import fetch_issues, fetch_pull_requests, fetch_commits
    print(f"[load] ingesting {repo}")
    issues = fetch_issues(repo)
    prs = fetch_pull_requests(repo)
    commits = fetch_commits(repo)
    upsert_issues(repo, issues)
    upsert_pull_requests(repo, prs)
    upsert_commits(repo, commits)
    print(f"[load] done — {len(issues)} issues, {len(prs)} PRs, {len(commits)} commits")

if __name__ == "__main__":
    import sys
    repo = sys.argv[1] if len(sys.argv) > 1 else "pallets/click"
    load_repo(repo)
