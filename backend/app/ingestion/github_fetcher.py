"""
GitHub REST API fetcher with rate-limit handling and local JSON cache.
"""
import os, json, time, base64, hashlib, requests
from pathlib import Path

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent


def _resolve_cache_dir() -> str:
    raw = os.environ.get("CACHE_DIR", "data/cache")
    p = Path(raw)
    if p.is_absolute():
        return str(p)
    if "CACHE_DIR" in os.environ:
        return str((_BACKEND_DIR / p).resolve())
    project_cache = _PROJECT_ROOT / p
    if (_PROJECT_ROOT / "data").exists():
        return str(project_cache.resolve())
    return str((_BACKEND_DIR / p).resolve())


CACHE_DIR = _resolve_cache_dir()
BASE_URL = "https://api.github.com"

def _headers():
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h

def _cache_path(repo: str, kind: str, page: int = 0) -> Path:
    safe = repo.replace("/", "__")
    p = Path(CACHE_DIR) / safe / kind
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{page}.json"

def _get(url: str, params: dict = None):
    """GET with rate-limit backoff."""
    for attempt in range(5):
        r = requests.get(url, headers=_headers(), params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 403:
            reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - time.time(), 1)
            print(f"  [rate-limit] sleeping {wait:.0f}s")
            time.sleep(wait)
            continue
        if r.status_code == 404:
            return None
        time.sleep(2 ** attempt)
    return None

def fetch_issues(repo: str, state: str = "closed", max_pages: int = 30, force_refresh: bool = False):
    """Fetch issues for a repo, optionally refreshing cached pages."""
    all_items = []
    for page in range(1, max_pages + 1):
        cp = _cache_path(repo, f"issues_{state}", page)
        if cp.exists() and not force_refresh:
            data = json.loads(cp.read_text())
        else:
            url = f"{BASE_URL}/repos/{repo}/issues"
            data = _get(url, {"state": state, "per_page": 100, "page": page, "filter": "all"})
            if not data:
                break
            cp.write_text(json.dumps(data))
        if not data:
            break
        # Filter out PRs (GitHub API returns PRs under issues endpoint too)
        issues = [i for i in data if "pull_request" not in i]
        all_items.extend(issues)
        print(f"  [issues] {repo} page {page}: {len(issues)} issues")
        if len(data) < 100:
            break
    return all_items

def fetch_contributors(repo: str, max_pages: int = 10, force_refresh: bool = False):
    """Fetch repository contributors so new repositories have real candidates."""
    all_items = []
    for page in range(1, max_pages + 1):
        cp = _cache_path(repo, "contributors", page)
        if cp.exists() and not force_refresh:
            data = json.loads(cp.read_text())
        else:
            data = _get(f"{BASE_URL}/repos/{repo}/contributors", {
                "per_page": 100, "page": page, "anon": "false"
            })
            if not data:
                break
            cp.write_text(json.dumps(data))
        if not data:
            break
        all_items.extend(data)
        if len(data) < 100:
            break
    return [c for c in all_items if c.get("login") and c.get("type") != "Bot"]

def fetch_source_files(repo: str, max_files: int = 25):
    """Fetch small source files for the demo BUG-marker scanner."""
    repo_info = _get(f"{BASE_URL}/repos/{repo}")
    if not repo_info or not repo_info.get("default_branch"):
        return []
    branch = repo_info["default_branch"]
    tree = _get(f"{BASE_URL}/repos/{repo}/git/trees/{branch}", {"recursive": "1"})
    if not tree or tree.get("truncated"):
        return []
    extensions = (".py", ".js", ".ts", ".tsx", ".java", ".go", ".rb", ".php")
    paths = [
        item["path"] for item in tree.get("tree", [])
        if item.get("type") == "blob"
        and item.get("size", 0) <= 500_000
        and item.get("path", "").lower().endswith(extensions)
    ][:max_files]
    files = []
    for path in paths:
        cache_name = hashlib.sha1(path.encode()).hexdigest()
        cache_path = _cache_path(repo, "source_files", 0).parent / f"{cache_name}.json"
        if cache_path.exists():
            data = json.loads(cache_path.read_text())
        else:
            data = _get(f"{BASE_URL}/repos/{repo}/contents/{path}", {"ref": branch})
            if data:
                cache_path.write_text(json.dumps(data))
        if not data or data.get("encoding") != "base64" or not data.get("content"):
            continue
        try:
            content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        except Exception:
            continue
        files.append({"path": path, "content": content})
    return files

def assign_issue(repo: str, issue_num: int, username: str):
    """Assign one issue on GitHub and return its response or an error."""
    url = f"{BASE_URL}/repos/{repo}/issues/{issue_num}/assignees"
    try:
        response = requests.post(
            url, headers=_headers(), json={"assignees": [username]}, timeout=30
        )
    except requests.RequestException as exc:
        return {"ok": False, "status_code": 0, "error": str(exc)}
    if response.status_code in (200, 201):
        return {"ok": True, "status_code": response.status_code, "data": response.json()}
    try:
        detail = response.json()
    except ValueError:
        detail = response.text[:500]
    return {"ok": False, "status_code": response.status_code, "error": detail}

def comment_issue(repo: str, issue_num: int, body: str):
    """Post a GitHub issue comment, which notifies mentioned developers."""
    url = f"{BASE_URL}/repos/{repo}/issues/{issue_num}/comments"
    try:
        response = requests.post(url, headers=_headers(), json={"body": body}, timeout=30)
    except requests.RequestException as exc:
        return {"ok": False, "status_code": 0, "error": str(exc)}
    if response.status_code == 201:
        return {"ok": True, "status_code": response.status_code, "data": response.json()}
    try:
        detail = response.json()
    except ValueError:
        detail = response.text[:500]
    return {"ok": False, "status_code": response.status_code, "error": detail}

def fetch_pull_requests(repo: str, state: str = "closed", max_pages: int = 30):
    all_items = []
    for page in range(1, max_pages + 1):
        cp = _cache_path(repo, f"prs_{state}", page)
        if cp.exists():
            data = json.loads(cp.read_text())
        else:
            url = f"{BASE_URL}/repos/{repo}/pulls"
            data = _get(url, {"state": state, "per_page": 100, "page": page})
            if not data:
                break
            cp.write_text(json.dumps(data))
        if not data:
            break
        all_items.extend(data)
        print(f"  [prs] {repo} page {page}: {len(data)} PRs")
        if len(data) < 100:
            break
    return all_items

def fetch_commits(repo: str, max_pages: int = 20):
    all_items = []
    for page in range(1, max_pages + 1):
        cp = _cache_path(repo, "commits", page)
        if cp.exists():
            data = json.loads(cp.read_text())
        else:
            url = f"{BASE_URL}/repos/{repo}/commits"
            data = _get(url, {"per_page": 100, "page": page})
            if not data:
                break
            cp.write_text(json.dumps(data))
        if not data:
            break
        all_items.extend(data)
        print(f"  [commits] {repo} page {page}: {len(data)} commits")
        if len(data) < 100:
            break
    detail_limit = max(int(os.environ.get("MAX_COMMIT_DETAILS", "200")), 0)
    for commit in all_items[:detail_limit]:
        if "files" not in commit and commit.get("sha"):
            detail = fetch_commit_detail(repo, commit["sha"])
            if detail:
                commit["files"] = detail.get("files", [])
    return all_items

def fetch_commit_detail(repo: str, sha: str):
    """Fetch and cache one commit detail response, including changed files."""
    cp = _cache_path(repo, "commit_details", sha)
    if cp.exists():
        return json.loads(cp.read_text())
    data = _get(f"{BASE_URL}/repos/{repo}/commits/{sha}")
    if data:
        cp.write_text(json.dumps(data))
    return data

def fetch_issue_timeline(repo: str, issue_num: int):
    cp = _cache_path(repo, "timeline") / f"{issue_num}.json"
    if cp.exists():
        return json.loads(cp.read_text())
    url = f"{BASE_URL}/repos/{repo}/issues/{issue_num}/timeline"
    data = _get(url, {"per_page": 100})
    if data is not None:
        cp.write_text(json.dumps(data))
    return data or []

if __name__ == "__main__":
    import sys
    repo = sys.argv[1] if len(sys.argv) > 1 else "pallets/click"
    print(f"Fetching {repo}...")
    issues = fetch_issues(repo, max_pages=3)
    prs = fetch_pull_requests(repo, max_pages=3)
    commits = fetch_commits(repo, max_pages=3)
    print(f"Done: {len(issues)} issues, {len(prs)} PRs, {len(commits)} commits")
