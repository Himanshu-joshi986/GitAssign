"""
Rule-based issue priority mapper.
Returns Critical / High / Medium / Low tier + score + contributing factors.
"""
import json

CRITICAL_LABELS  = {"p0", "blocker", "critical", "crash", "regression", "security"}
HIGH_LABELS      = {"bug", "high", "data-loss", "data loss", "p1", "major"}
LOW_LABELS       = {"enhancement", "feature", "question", "help wanted",
                    "good first issue", "documentation", "docs", "low", "minor"}

CRITICAL_KEYWORDS = ["crash", "data loss", "data corruption", "security", "cve",
                     "deadlock", "hang", "freeze", "regression", "exploit",
                     "remote code", "injection", "privilege escalation"]
HIGH_KEYWORDS     = ["p1", "major", "error", "exception", "null pointer", "stack overflow",
                     "memory leak", "broken", "not working", "fails"]
LOW_KEYWORDS      = ["enhancement", "question", "feature request", "typo",
                     "documentation", "docs", "improve", "suggestion"]

def map_priority(issue: dict) -> dict:
    """
    issue: output of issue_extractor.extract() or raw issue dict
    Returns: {"tier": str, "score": float, "factors": list}
    """
    text   = (issue.get('text') or
              f"{issue.get('title', '')} {issue.get('body') or ''}").lower()
    labels = issue.get("labels_lower", issue.get("labels", []))
    if isinstance(labels, str):
        try:
            labels = [l.lower() for l in json.loads(labels)]
        except Exception:
            labels = []
    labels_set = set(l.lower() for l in labels)

    score   = 0.0
    factors = []

    # Label-based rules
    if labels_set & CRITICAL_LABELS:
        score += 4.0
        factors.append(f"Critical label: {labels_set & CRITICAL_LABELS}")
    elif labels_set & HIGH_LABELS:
        score += 2.0
        factors.append(f"High-priority label: {labels_set & HIGH_LABELS}")
    elif labels_set & LOW_LABELS:
        score -= 1.0
        factors.append(f"Low-priority label: {labels_set & LOW_LABELS}")

    # Keyword-based rules
    for kw in CRITICAL_KEYWORDS:
        if kw in text:
            score += 2.0
            factors.append(f"Critical keyword: '{kw}'")
            break

    for kw in HIGH_KEYWORDS:
        if kw in text:
            score += 0.5
            factors.append(f"High-priority keyword: '{kw}'")
            break

    for kw in LOW_KEYWORDS:
        if kw in text:
            score -= 0.5
            factors.append(f"Low-priority keyword: '{kw}'")
            break

    # Steps to reproduce → higher confidence
    if any(p in text for p in ["steps to reproduce", "to reproduce", "reproduction"]):
        score += 0.5
        factors.append("Steps to reproduce provided")

    # Security terms → boost
    if any(k in text for k in ["cve-", "nvd", "advisory", "vulnerability"]):
        score += 3.0
        factors.append("Security advisory / CVE reference")

    # Determine tier
    if score >= 5.0:
        tier = "Critical"
    elif score >= 2.0:
        tier = "High"
    elif score >= 0.0:
        tier = "Medium"
    else:
        tier = "Low"

    return {
        "tier":    tier,
        "score":   round(score, 2),
        "factors": factors,
        "color":   {"Critical": "red", "High": "orange",
                    "Medium": "yellow", "Low": "green"}[tier]
    }

def prioritise_batch(issues: list) -> list:
    """Priority-sort a list of issues. Returns list with 'priority' key added."""
    result = []
    for issue in issues:
        p = map_priority(issue)
        issue_copy = dict(issue)
        issue_copy["priority"] = p
        result.append(issue_copy)
    return sorted(result, key=lambda x: x["priority"]["score"], reverse=True)
