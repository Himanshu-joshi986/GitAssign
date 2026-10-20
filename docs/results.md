# GitAssign — Ablation Results

**Repository:** `pallets/click`

| Config | Signals | Top-1 (%) | Top-3 (%) | Top-5 (%) | MRR | N |
|--------|---------|-----------|-----------|-----------|-----|---|
| A | Text similarity only | 80.0 | 80.0 | 80.0 | 0.8 | 10 |
| B | A + component overlap | 80.0 | 80.0 | 80.0 | 0.8 | 10 |
| C | B + file affinity | 80.0 | 80.0 | 80.0 | 0.8 | 10 |
| D | C + recency | 80.0 | 80.0 | 80.0 | 0.8 | 10 |
| E | Full model (all 6 signals) | 80.0 | 80.0 | 80.0 | 0.8 | 10 |

## Raw JSON
```json
{
  "A": {
    "top1": 80.0,
    "top3": 80.0,
    "top5": 80.0,
    "mrr": 0.8,
    "n": 10,
    "repo": "pallets/click",
    "config": "A",
    "config_name": "Text similarity only"
  },
  "B": {
    "top1": 80.0,
    "top3": 80.0,
    "top5": 80.0,
    "mrr": 0.8,
    "n": 10,
    "repo": "pallets/click",
    "config": "B",
    "config_name": "A + component overlap"
  },
  "C": {
    "top1": 80.0,
    "top3": 80.0,
    "top5": 80.0,
    "mrr": 0.8,
    "n": 10,
    "repo": "pallets/click",
    "config": "C",
    "config_name": "B + file affinity"
  },
  "D": {
    "top1": 80.0,
    "top3": 80.0,
    "top5": 80.0,
    "mrr": 0.8,
    "n": 10,
    "repo": "pallets/click",
    "config": "D",
    "config_name": "C + recency"
  },
  "E": {
    "top1": 80.0,
    "top3": 80.0,
    "top5": 80.0,
    "mrr": 0.8,
    "n": 10,
    "repo": "pallets/click",
    "config": "E",
    "config_name": "Full model (all 6 signals)"
  }
}
```