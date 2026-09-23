import sqlite3
import os
from pathlib import Path

# backend/ directory (parent of db/)
_BACKEND_DIR = Path(__file__).resolve().parent.parent
# project root (parent of backend/) — exists in local monorepo; absent in flat Docker image
_PROJECT_ROOT = _BACKEND_DIR.parent


def _resolve_path(env_key: str, default_rel: str) -> str:
    """
    Resolve a path from env or default.
    Relative paths are resolved against the backend dir (Docker WORKDIR=/app),
    falling back to project-root when that layout exists locally.
    """
    raw = os.environ.get(env_key, default_rel)
    p = Path(raw)
    if p.is_absolute():
        return str(p)

    # Prefer project-root/<rel> when that directory exists (local monorepo)
    project_candidate = (_PROJECT_ROOT / p).resolve()
    backend_candidate = (_BACKEND_DIR / p).resolve()

    # If env explicitly set, prefer backend-relative (matches Docker mounts at /app/data)
    if env_key in os.environ:
        return str(backend_candidate)

    # Default: use project data/ if present, else backend/data/
    if project_candidate.parent.exists() or (project_candidate.parent.name == "data" and (_PROJECT_ROOT / "data").exists()):
        return str(project_candidate)
    return str(backend_candidate)


DB_PATH = _resolve_path("DB_PATH", "data/gitassign.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    conn = get_conn()
    with open(schema_path, encoding="utf-8") as f:
        conn.executescript(f.read())
    # Migrations: add columns that may be missing from older DBs
    _migrate_add_column(conn, "developer_profiles", "resolved_issues_json", "TEXT")
    _migrate_add_column(conn, "issues", "assignees_json", "TEXT DEFAULT '[]'")
    conn.commit()
    conn.close()
    print(f"[DB] Initialised at {DB_PATH}")


def _migrate_add_column(conn, table: str, column: str, definition: str):
    """Safely add a column if it doesn't exist (SQLite has no IF NOT EXISTS for ADD COLUMN)."""
    try:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            print(f"[DB] Migrated: added {table}.{column}")
    except Exception as e:
        print(f"[DB] Migration warning for {table}.{column}: {e}")


if __name__ == "__main__":
    init_db()
