# GitAssign — Ablation Results

**Repository:** `microsoft/vscode`

| Config | Signals | Top-1 (%) | Top-3 (%) | Top-5 (%) | MRR | N |
|--------|---------|-----------|-----------|-----------|-----|---|
| A | Text similarity only | 8.33 | 11.67 | 13.33 | 0.1019 | 60 |
| B | A + component overlap | 10.0 | 13.33 | 13.33 | 0.1172 | 60 |
| C | B + file affinity | 10.0 | 13.33 | 13.33 | 0.1172 | 60 |
| D | C + recency | 10.0 | 11.67 | 13.33 | 0.1158 | 60 |
| E | Full model (all 6 signals) | 11.67 | 13.33 | 13.33 | 0.128 | 60 |

## Raw JSON
```json
{
  "A": {
    "top1": 8.33,
    "top3": 11.67,
    "top5": 13.33,
    "mrr": 0.1019,
    "n": 60,
    "repo": "microsoft/vscode",
    "config": "A",
    "config_name": "Text similarity only"
  },
  "B": {
    "top1": 10.0,
    "top3": 13.33,
    "top5": 13.33,
    "mrr": 0.1172,
    "n": 60,
    "repo": "microsoft/vscode",
    "config": "B",
    "config_name": "A + component overlap"
  },
  "C": {
    "top1": 10.0,
    "top3": 13.33,
    "top5": 13.33,
    "mrr": 0.1172,
    "n": 60,
    "repo": "microsoft/vscode",
    "config": "C",
    "config_name": "B + file affinity"
  },
  "D": {
    "top1": 10.0,
    "top3": 11.67,
    "top5": 13.33,
    "mrr": 0.1158,
    "n": 60,
    "repo": "microsoft/vscode",
    "config": "D",
    "config_name": "C + recency"
  },
  "E": {
    "top1": 11.67,
    "top3": 13.33,
    "top5": 13.33,
    "mrr": 0.128,
    "n": 60,
    "repo": "microsoft/vscode",
    "config": "E",
    "config_name": "Full model (all 6 signals)"
  }
}
```