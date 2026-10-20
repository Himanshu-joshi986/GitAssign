"""
Generate human-readable per-signal evidence for every recommendation.
"""
import json
from app.core.ai_layer import build_ai_context

def explain(issue: dict, profile: dict, signals: dict) -> dict:
    """
    issue:   output of issue_extractor.extract()
    profile: developer profile dict
    signals: output of scoring_engine.score() — raw signal values
    """
    dev = profile["username"]
    resolved_count = profile.get("resolved_count", 0)

    dev_files = json.loads(profile.get("files_json") or "{}")
    dev_comps  = json.loads(profile.get("components_json") or "{}")

    matched_files = [f for f in issue.get("mentioned_files", []) if f in dev_files]
    matched_comps = [c for c in issue.get("components", []) if c in dev_comps]

    # AI-layer domain fit (Step 6): issue classification vs cached dev profile.
    classification = issue.get("classification") or {}
    try:
        dev_domain_list = json.loads(profile.get("domains_json") or "[]")
    except Exception:
        dev_domain_list = []
    issue_domain_list = classification.get("domains") or []
    issue_names = [d.get("name", "") if isinstance(d, dict) else d for d in issue_domain_list]
    dev_names = [d.get("name", "") if isinstance(d, dict) else d for d in dev_domain_list]
    matched_domains = [d for d in issue_names if d in dev_names]

    dev_domain_detail = ", ".join(
        f"{d.get('name', '')} ({d.get('weight', 0):.2f})" if isinstance(d, dict) else str(d)
        for d in dev_domain_list[:3]
    )

    s1 = signals.get("s1_text", 0)
    s2 = signals.get("s2_past", 0)
    s3 = signals.get("s3_component", 0)
    s4 = signals.get("s4_file", 0)
    s5 = signals.get("s5_recency", 0)
    s6 = signals.get("s6_workload", 0)
    s7 = signals.get("s7_domain", 0)

    def pct(v): return f"{v*100:.0f}%"

    evidence = {
        "text_similarity": {
            "value": s1,
            "label": f"Text match: {pct(s1)} similarity with past resolved issues",
            "detail": f"Issue text matches {pct(s1)} of {dev}'s historical issue vocabulary"
        },
        "past_issue_similarity": {
            "value": s2,
            "label": f"Historical similarity: {pct(s2)} avg match",
            "detail": f"{dev} has resolved {resolved_count} issues; {pct(s2)} avg similarity to this issue"
        },
        "component_overlap": {
            "value": s3,
            "label": (f"Component match: {len(matched_comps)} of {len(issue.get('components',[]))} components"
                      if issue.get("components") else "No component labels on this issue"),
            "detail": f"Matched components: {matched_comps}" if matched_comps else "No component overlap found"
        },
        "file_affinity": {
            "value": s4,
            "label": (f"File affinity: committed to {len(matched_files)} relevant file(s)"
                      if matched_files else "No file overlap detected"),
            "detail": (f"Files: {matched_files[:3]}" if matched_files else
                       f"{dev} has not committed to files mentioned in this issue")
        },
        "recency": {
            "value": s5,
            "label": f"Recency: {pct(s5)} activity score",
            "detail": f"Last active: {profile.get('last_active', 'unknown')}"
        },
        "workload": {
            "value": s6,
            "label": f"Workload: {profile.get('open_issue_count', 0)} open issue(s) currently assigned",
            "detail": ("No current assignments — fully available" if profile.get("open_issue_count", 0) == 0
                       else f"{dev} has {profile.get('open_issue_count', 0)} open issues — capacity penalty applied")
        },
        "domain": {
            "value": s7,
            "label": (f"Domain fit: {', '.join(matched_domains)}" if matched_domains
                      else (f"No domain overlap (dev: {dev_domain_detail})" if dev_domain_detail
                            else "No domain profile cached yet")),
            "detail": (f"Issue domains: {issue_names}; {dev}'s domains: {dev_domain_detail}"
                       if dev_domain_detail else
                       f"Issue domains: {issue_names}; {dev} has no cached AI domain profile")
        },
    }

    # Auto-generate summary sentence
    parts = []
    if resolved_count > 0:
        parts.append(f"resolved {resolved_count} issues in this repo")
    if matched_files:
        parts.append(f"committed to {len(matched_files)} relevant file(s)")
    if matched_comps:
        parts.append(f"active in {len(matched_comps)} matched component(s)")
    if not parts:
        parts.append("has general repository activity")

    summary = f"{dev} has {', '.join(parts)}."
    if matched_domains:
        summary += f" {dev.title()} is a strong match on domain(s): {', '.join(matched_domains)}."
    if classification.get("kind") and classification.get("model"):
        summary += f" This issue was classified by AI as a {classification['kind']} (model: {classification['model']})."

    return {
        "developer":    dev,
        "final_score":  signals.get("final_score", 0),
        "summary":      summary,
        "signals":      evidence,
        "matched_domains": matched_domains,
        "issue_domains": issue_names,
        "developer_domains": dev_names,
        "classification": {
            "kind": classification.get("kind", ""),
            "domains": issue_domain_list,
            "severity": classification.get("severity", ""),
            "difficulty": classification.get("difficulty", 0),
            "summary": classification.get("summary", ""),
            "model": classification.get("model", ""),
        },
        "open_issues":  profile.get("open_issue_count", 0),
        "resolved_total": resolved_count,
        "ai_context": build_ai_context(issue, profile),
    }
