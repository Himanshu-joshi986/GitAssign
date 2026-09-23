CREATE TABLE IF NOT EXISTS issues (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    repo        TEXT NOT NULL,
    number      INTEGER NOT NULL,
    title       TEXT,
    body        TEXT,
    labels      TEXT,  -- JSON array
    state       TEXT,
    created_at  TEXT,
    closed_at   TEXT,
    author      TEXT,
    assignees_json TEXT DEFAULT '[]',
    UNIQUE(repo, number)
);

CREATE TABLE IF NOT EXISTS pull_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    repo        TEXT NOT NULL,
    number      INTEGER NOT NULL,
    title       TEXT,
    body        TEXT,
    merged_at   TEXT,
    merged_by   TEXT,
    state       TEXT,
    UNIQUE(repo, number)
);

CREATE TABLE IF NOT EXISTS commits (
    sha         TEXT PRIMARY KEY,
    repo        TEXT NOT NULL,
    author      TEXT,
    message     TEXT,
    files_json  TEXT,  -- JSON array of file paths
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS issue_pr_links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    repo        TEXT NOT NULL,
    issue_num   INTEGER NOT NULL,
    pr_num      INTEGER NOT NULL,
    link_type   TEXT,  -- closes/fixes/resolves/ref
    resolver    TEXT,  -- developer username who merged
    UNIQUE(repo, issue_num, pr_num)
);

CREATE TABLE IF NOT EXISTS developers (
    username    TEXT PRIMARY KEY,
    display_name TEXT
);

CREATE TABLE IF NOT EXISTS repository_developers (
    repo        TEXT NOT NULL,
    username    TEXT NOT NULL,
    display_name TEXT,
    account_type TEXT DEFAULT 'User',
    PRIMARY KEY (repo, username)
);

CREATE TABLE IF NOT EXISTS developer_profiles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    username            TEXT NOT NULL,
    repo                TEXT NOT NULL,
    files_json          TEXT,  -- {"path": count}
    components_json     TEXT,  -- {"label": count}
    resolved_text       TEXT,  -- concatenated resolved issue text
    resolved_issues_json TEXT, -- JSON array of individual resolved issue texts
    last_active         TEXT,
    open_issue_count    INTEGER DEFAULT 0,
    resolved_count      INTEGER DEFAULT 0,
    updated_at          TEXT,
    UNIQUE(username, repo)
);

CREATE TABLE IF NOT EXISTS issue_priority (
    issue_id    INTEGER,
    repo        TEXT,
    issue_num   INTEGER,
    tier        TEXT,   -- Critical/High/Medium/Low
    score       REAL,
    factors_json TEXT,
    PRIMARY KEY (repo, issue_num)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo            TEXT NOT NULL,
    issue_num       INTEGER NOT NULL,
    developer       TEXT NOT NULL,
    score           REAL,
    rank            INTEGER,
    signals_json    TEXT,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo            TEXT NOT NULL,
    issue_num       INTEGER NOT NULL,
    developer       TEXT,
    status          TEXT NOT NULL,
    github_response TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(repo, issue_num, developer, created_at)
);

CREATE INDEX IF NOT EXISTS idx_issues_repo_state_created
    ON issues(repo, state, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_issues_repo_number
    ON issues(repo, number);
