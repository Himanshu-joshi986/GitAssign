"""
Parse a raw issue into a structured record for scoring.
"""
import re, json

SEVERITY_KEYWORDS = ["crash", "data-loss", "data loss", "p0", "blocker",
                     "critical", "regression", "security", "cve", "exploit",
                     "deadlock", "hang", "freeze", "corruption", "segfault"]

LOW_PRIORITY_KEYWORDS = ["enhancement", "feature request", "question",
                          "help wanted", "good first issue", "documentation", "docs"]

FILE_PATTERN = re.compile(r'[\w/.\-]+\.(?:py|js|ts|java|go|rb|c|cpp|h|rs|kt|swift|cs|php)\b')

def extract(issue: dict) -> dict:
    """
    Input:  raw issue row from DB (dict with title, body, labels, etc.)
    Output: structured issue dict ready for scoring
    """
    title  = (issue.get("title") or "").lower()
    body   = (issue.get("body") or "").lower()
    text   = f"{title} {body}"

    # Parse labels
    raw_labels = issue.get("labels", "[]")
    if isinstance(raw_labels, str):
        try:
            labels = json.loads(raw_labels)
        except Exception:
            labels = []
    else:
        labels = raw_labels
    labels_lower = [l.lower() for l in labels]

    # Severity keywords present
    severity_hits = [kw for kw in SEVERITY_KEYWORDS if kw in text or kw in labels_lower]
    low_hits      = [kw for kw in LOW_PRIORITY_KEYWORDS if kw in text or kw in labels_lower]

    # File paths mentioned in body
    mentioned_files = list(set(FILE_PATTERN.findall(body)))

    # Components — anything in labels that isn't a severity marker
    components = [l for l in labels_lower
                  if l not in SEVERITY_KEYWORDS and l not in LOW_PRIORITY_KEYWORDS]

    clean_body = issue.get("body") or ""
    return {
        "id":                  issue.get("id"),
        "repo":                issue.get("repo"),
        "number":              issue.get("number"),
        "title":               issue.get("title", ""),
        "text":                f"{issue.get('title', '')} {clean_body}",
        "labels":              labels,
        "labels_lower":        labels_lower,
        "severity_keywords":   severity_hits,
        "low_priority_keywords": low_hits,
        "mentioned_files":     mentioned_files,
        "components":          components,
        "created_at":          issue.get("created_at", ""),
    }
