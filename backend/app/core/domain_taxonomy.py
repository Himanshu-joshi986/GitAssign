"""
Domain taxonomy: shared vocabulary for issue classifications and developer
profiles, plus deterministic keyword heuristics used when the LLM is
disabled or fails.

The taxonomy lives in `backend/config/domains.json` so the LLM prompt, the
heuristic fallbacks, and the domain-match signal all agree on names.
"""
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "domains.json"

_MAX_DOMAINS_ISSUE = 3
_MAX_DOMAINS_PROFILE = 4

# Fallback taxonomy when config/domains.json is missing or unreadable.
_FALLBACK_DOMAINS = [
    {"name": "backend", "description": "server logic, services, business rules"},
    {"name": "frontend", "description": "UI, components, client state, styling"},
    {"name": "api", "description": "REST/GraphQL endpoints, contracts, SDKs"},
    {"name": "database", "description": "schemas, queries, migrations, persistence"},
    {"name": "auth", "description": "authentication, authorization, sessions, permissions"},
    {"name": "security", "description": "vulnerabilities, crypto, input validation, CVEs"},
    {"name": "infrastructure", "description": "Docker, Kubernetes, deployment, cloud"},
    {"name": "ci-cd", "description": "pipelines, release automation, build tooling"},
    {"name": "testing", "description": "test suites, fixtures, QA automation"},
    {"name": "docs", "description": "documentation, guides, examples"},
    {"name": "performance", "description": "latency, memory, profiling, optimization"},
    {"name": "data-ml", "description": "data processing, analytics, ML, statistics"},
    {"name": "mobile", "description": "Android, iOS, React Native, Flutter"},
    {"name": "networking", "description": "HTTP clients, sockets, protocols, proxies"},
    {"name": "developer-tools", "description": "CLI, linting, formatting, editor tooling"},
]

# Common aliases -> canonical taxonomy names.
_ALIASES = {
    "backend": "backend",
    "back-end": "backend",
    "server": "backend",
    "backend/api": "backend",
    "api": "api",
    "rest": "api",
    "graphql": "api",
    "frontend": "frontend",
    "front-end": "frontend",
    "ui": "frontend",
    "client": "frontend",
    "web": "frontend",
    "database": "database",
    "db": "database",
    "persistence": "database",
    "storage": "database",
    "auth": "auth",
    "authentication": "auth",
    "authorization": "auth",
    "permissions": "auth",
    "login": "auth",
    "security": "security",
    "vulnerability": "security",
    "crypto": "security",
    "infrastructure": "infrastructure",
    "devops": "infrastructure",
    "deployment": "infrastructure",
    "docker": "infrastructure",
    "kubernetes": "infrastructure",
    "cloud": "infrastructure",
    "ci-cd": "ci-cd",
    "ci": "ci-cd",
    "cd": "ci-cd",
    "ci/cd": "ci-cd",
    "pipelines": "ci-cd",
    "build": "ci-cd",
    "testing": "testing",
    "test": "testing",
    "qa": "testing",
    "docs": "docs",
    "documentation": "docs",
    "performance": "performance",
    "optimization": "performance",
    "latency": "performance",
    "memory": "performance",
    "data-ml": "data-ml",
    "ml": "data-ml",
    "data": "data-ml",
    "ai": "data-ml",
    "analytics": "data-ml",
    "mobile": "mobile",
    "android": "mobile",
    "ios": "mobile",
    "flutter": "mobile",
    "react-native": "mobile",
    "networking": "networking",
    "network": "networking",
    "http": "networking",
    "sockets": "networking",
    "developer-tools": "developer-tools",
    "developer tools": "developer-tools",
    "cli": "developer-tools",
    "tooling": "developer-tools",
    "linting": "developer-tools",
}

_domains_cache: list[dict] | None = None


def load_domains() -> list[dict]:
    """Cached read of config/domains.json; falls back to the built-in list."""
    global _domains_cache
    if _domains_cache is not None:
        return _domains_cache
    domains = list(_FALLBACK_DOMAINS)
    try:
        raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        parsed = [
            {"name": str(d["name"]).strip().lower(), "description": str(d.get("description", ""))}
            for d in raw.get("domains", [])
            if isinstance(d, dict) and d.get("name")
        ]
        if parsed:
            domains = parsed
    except (OSError, ValueError, KeyError, TypeError):
        pass
    _domains_cache = domains
    return _domains_cache


def domain_names() -> set[str]:
    return {d["name"] for d in load_domains()}


def _canonical(raw: str) -> str | None:
    """Map a raw name or alias to a canonical taxonomy name, or None."""
    name = str(raw).strip().lower()
    if not name:
        return None
    if name in domain_names():
        return name
    return _ALIASES.get(name)


def normalise_domains(raw, max_domains: int = None, default_confidence: float = 0.5) -> list[dict]:
    """
    Normalise a raw domain list into [{"name": canonical, "confidence": 0..1}].

    Accepts strings or {"name": ..., "confidence"/"weight": ...} objects.
    Unknown names are dropped, duplicates merged (max confidence kept),
    capped at `max_domains`, and confidences clamped to [0, 1].
    """
    if max_domains is None:
        max_domains = _MAX_DOMAINS_ISSUE
    merged: dict[str, float] = {}
    for item in raw or []:
        if isinstance(item, str):
            name, value = item, default_confidence
        elif isinstance(item, dict):
            name, value = item.get("name"), item.get("confidence", item.get("weight"))
        else:
            continue
        canonical = _canonical(name) if name else None
        if not canonical:
            continue
        try:
            conf = float(value)
        except (TypeError, ValueError):
            conf = default_confidence
        conf = min(max(conf, 0.0), 1.0)
        merged[canonical] = max(merged.get(canonical, 0.0), conf)

    ranked = sorted(merged.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"name": name, "confidence": round(conf, 4)} for name, conf in ranked[:max_domains]]


def domains_to_weights(domains) -> dict[str, float]:
    """Convert a normalised domain list into {"name": weight} summing to ~1."""
    normalised = normalise_domains(domains, max_domains=_MAX_DOMAINS_PROFILE)
    total = sum(d["confidence"] for d in normalised)
    if total <= 0:
        return {}
    return {d["name"]: round(d["confidence"] / total, 4) for d in normalised}


def domain_match(issue_domains, dev_domains) -> float:
    """
    Fraction of the issue's domains covered by the developer's domain weights.

    issue_domains: [{"name": "backend"}, ...] or ["backend"]
    dev_domains:   {"backend": 0.6, "database": 0.4} (or a normalised list)
    """
    names = []
    for item in issue_domains or []:
        name = item.get("name") if isinstance(item, dict) else item
        canonical = _canonical(name) if name else None
        if canonical and canonical not in names:
            names.append(canonical)
    if not names:
        return 0.0

    if isinstance(dev_domains, dict):
        weights = {str(k).strip().lower(): float(v or 0) for k, v in dev_domains.items()}
    else:
        weights = domains_to_weights(dev_domains)

    return sum(min(weights.get(name, 0.0), 1.0) for name in names) / len(names)


# ── Deterministic heuristics (LLM fallback) ───────────────────────────────────

# Ordered (keyword/path fragment, domain) pairs; first 3 matches win.
_KEYWORD_DOMAIN_MAP = [
    (".tsx", "frontend"),
    (".jsx", "frontend"),
    (".css", "frontend"),
    (".scss", "frontend"),
    (".vue", "frontend"),
    ("docker", "infrastructure"),
    ("k8s", "infrastructure"),
    ("kubernetes", "infrastructure"),
    ("deploy", "infrastructure"),
    ("sql", "database"),
    ("migration", "database"),
    ("database", "database"),
    ("schema", "database"),
    ("auth", "auth"),
    ("login", "auth"),
    ("token", "auth"),
    ("oauth", "auth"),
    ("cve", "security"),
    ("security", "security"),
    ("vulnerab", "security"),
    (".github/workflows", "ci-cd"),
    ("workflow", "ci-cd"),
    ("ci", "ci-cd"),
    ("build", "ci-cd"),
    ("test", "testing"),
    ("pytest", "testing"),
    ("jest", "testing"),
    ("readme", "docs"),
    ("docs", "docs"),
    ("documentation", "docs"),
    ("typo", "docs"),
    ("slow", "performance"),
    ("memory", "performance"),
    ("leak", "performance"),
    ("performance", "performance"),
    ("android", "mobile"),
    ("ios", "mobile"),
    ("flutter", "mobile"),
]

_BACKEND_EXT = (".py", ".go", ".java", ".rb", ".php", ".cs", ".kt", ".rs")
_FRONTEND_EXT = (".js", ".ts", ".tsx", ".jsx", ".vue", ".css", ".scss", ".html")


def heuristic_domains(title: str, body: str = "", labels=None, files=None) -> list[dict]:
    """Keyword/path-based domain guess; returns normalised issue domains."""
    text = " ".join(
        [
            str(title or ""),
            str(body or ""),
            " ".join(str(l) for l in (labels or [])),
            " ".join(str(f) for f in (files or [])),
        ]
    ).lower()

    matched: list[str] = []
    for fragment, domain in _KEYWORD_DOMAIN_MAP:
        if fragment in text and domain not in matched:
            matched.append(domain)
        if len(matched) >= _MAX_DOMAINS_ISSUE:
            break

    if not matched:
        has_backend_file = any(str(f).lower().endswith(_BACKEND_EXT) for f in (files or []))
        has_frontend_file = any(str(f).lower().endswith(_FRONTEND_EXT) for f in (files or []))
        if has_backend_file:
            matched = ["backend"]
        elif has_frontend_file:
            matched = ["frontend"]
        else:
            matched = ["backend"]

    return [{"name": name, "confidence": 0.5} for name in matched[:_MAX_DOMAINS_ISSUE]]


_KIND_RULES = [
    (("security", "cve", "vulnerab", "xss", "injection"), "security"),
    (("perf", "slow", "memory", "leak", "latency"), "performance"),
    (("bug", "crash", "error", "broken", "regression", "exception"), "bug"),
    (("feature", "enhancement", "request", "add support"), "feature"),
    (("docs", "docstring", "typo", "readme"), "docs"),
    (("test", "pytest", "coverage", "flaky"), "test"),
    (("refactor", "cleanup", "restructure"), "refactor"),
]


def heuristic_kind(title: str, body: str = "", labels=None) -> str:
    """Keyword-based issue kind; defaults to chore."""
    text = " ".join(
        [str(title or ""), str(body or ""), " ".join(str(l) for l in (labels or []))]
    ).lower()
    for keywords, kind in _KIND_RULES:
        if any(k in text for k in keywords):
            return kind
    return "chore"


def heuristic_classification(title: str, body: str = "", labels=None, files=None) -> dict:
    """
    Deterministic fallback classification with the same shape as the LLM output.

    Always returns taxonomy-valid domains; never raises.
    """
    kind = heuristic_kind(title, body, labels)
    domains = heuristic_domains(title, body, labels, files)

    severity = "medium"
    label_text = " ".join(str(l).lower() for l in (labels or []))
    text = f"{title or ''} {body or ''}".lower()
    if any(k in label_text or k in text for k in ("critical", "blocker", "p0")):
        severity = "critical"
    elif any(k in label_text or k in text for k in ("high", "crash", "data-loss", "data loss")):
        severity = "high"
    elif any(k in label_text or k in text for k in ("low", "minor", "cosmetic")):
        severity = "low"

    summary = " ".join(str(title or "").split())[:300]

    return {
        "kind": kind,
        "domains": domains,
        "difficulty": 3,
        "severity": severity,
        "summary": summary,
        "required_skills": [],
        "confidence": 0.4,
        "model": "heuristic",
    }
