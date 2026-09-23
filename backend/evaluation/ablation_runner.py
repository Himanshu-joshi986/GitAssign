"""
Ablation experiment runner — configs A through E.
Runs replay harness with progressively more signals enabled.
Results are saved to docs/results.md
"""
import json, os
from pathlib import Path
from evaluation.replay_harness import run_replay

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent


def _default_results_path() -> str:
    """Prefer project-root/docs (local) or /app/docs (Docker mount)."""
    backend_docs = _BACKEND_DIR / "docs" / "results.md"
    project_docs = _PROJECT_ROOT / "docs" / "results.md"
    if (_BACKEND_DIR / "docs").is_dir():
        return str(backend_docs)
    return str(project_docs)


CONFIGS = {
    "A": {
        "name": "Text similarity only",
        "weights": {
            "w1_text_similarity":       1.0,
            "w2_past_issue_similarity": 0.0,
            "w3_component_overlap":     0.0,
            "w4_file_affinity":         0.0,
            "w5_recency":               0.0,
            "w6_workload_penalty":      0.0,
        }
    },
    "B": {
        "name": "A + component overlap",
        "weights": {
            "w1_text_similarity":       0.6,
            "w2_past_issue_similarity": 0.0,
            "w3_component_overlap":     0.4,
            "w4_file_affinity":         0.0,
            "w5_recency":               0.0,
            "w6_workload_penalty":      0.0,
        }
    },
    "C": {
        "name": "B + file affinity",
        "weights": {
            "w1_text_similarity":       0.45,
            "w2_past_issue_similarity": 0.0,
            "w3_component_overlap":     0.30,
            "w4_file_affinity":         0.25,
            "w5_recency":               0.0,
            "w6_workload_penalty":      0.0,
        }
    },
    "D": {
        "name": "C + recency",
        "weights": {
            "w1_text_similarity":       0.40,
            "w2_past_issue_similarity": 0.0,
            "w3_component_overlap":     0.25,
            "w4_file_affinity":         0.25,
            "w5_recency":               0.10,
            "w6_workload_penalty":      0.0,
        }
    },
    "E": {
        "name": "Full model (all 6 signals)",
        "weights": {
            "w1_text_similarity":       0.35,
            "w2_past_issue_similarity": 0.25,
            "w3_component_overlap":     0.15,
            "w4_file_affinity":         0.15,
            "w5_recency":               0.05,
            "w6_workload_penalty":      0.05,
        }
    },
}


def run_ablation(
    repo: str,
    train_before: str = "2010-01-01",
    test_after:   str = "2010-01-01",
    max_issues:   int = 300,
    configs:      list = None,
    save_path:    str = None,
) -> dict:
    """
    Run all ablation configs and save results.
    configs: subset of ["A","B","C","D","E"] — None means all
    """
    save_path = save_path or _default_results_path()
    to_run = configs or list(CONFIGS.keys())
    all_results = {}

    for key in to_run:
        cfg = CONFIGS[key]
        print(f"\n{'='*50}")
        print(f"[ablation] Config {key}: {cfg['name']}")
        print(f"{'='*50}")
        results = run_replay(
            repo=repo,
            train_before=train_before,
            test_after=test_after,
            max_test_issues=max_issues,
            signals_config=cfg["weights"],
        )
        results["config"] = key
        results["config_name"] = cfg["name"]
        all_results[key] = results

    _save_results(all_results, repo, save_path)
    return all_results


def _save_results(results: dict, repo: str, path: str):
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    lines = [
        f"# GitAssign — Ablation Results",
        f"",
        f"**Repository:** `{repo}`",
        f"",
        f"| Config | Signals | Top-1 (%) | Top-3 (%) | Top-5 (%) | MRR | N |",
        f"|--------|---------|-----------|-----------|-----------|-----|---|",
    ]
    for key, r in results.items():
        lines.append(
            f"| {key} | {r.get('config_name','')} "
            f"| {r['top1']} | {r['top3']} | {r['top5']} | {r['mrr']} | {r['n']} |"
        )
    lines += ["", "## Raw JSON", "```json", json.dumps(results, indent=2), "```"]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n[ablation] Results saved to {path}")


def get_latest_results(path: str = None) -> dict:
    """Read back the latest ablation results from disk."""
    path = path or _default_results_path()
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        content = f.read()
    start = content.find("```json") + 7
    end   = content.find("```", start)
    if start > 7 and end > start:
        try:
            return json.loads(content[start:end].strip())
        except Exception:
            pass
    return {}


if __name__ == "__main__":
    import sys
    repo  = sys.argv[1] if len(sys.argv) > 1 else "eclipse/jdt"
    train = sys.argv[2] if len(sys.argv) > 2 else "2010-01-01"
    test  = sys.argv[3] if len(sys.argv) > 3 else "2010-01-01"
    run_ablation(repo, train_before=train, test_after=test, max_issues=200)
