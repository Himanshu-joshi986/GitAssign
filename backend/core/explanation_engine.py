"""
Generate human-readable per-signal evidence for every recommendation.
"""
import json

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

    s1 = signals.get("s1_text", 0)
    s2 = signals.get("s2_past", 0)
    s3 = signals.get("s3_component", 0)
    s4 = signals.get("s4_file", 0)
    s5 = signals.get("s5_recency", 0)
    s6 = signals.get("s6_workload", 0)

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

    return {
        "developer":    dev,
        "final_score":  signals.get("final_score", 0),
        "summary":      summary,
        "signals":      evidence,
        "open_issues":  profile.get("open_issue_count", 0),
        "resolved_total": resolved_count,
    }
