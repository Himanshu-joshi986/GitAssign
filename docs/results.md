# GitAssign — Ablation Results

**Repository:** `Himanshu-joshi986/Test`

| Config | Signals | Top-1 (%) | Top-3 (%) | Top-5 (%) | MRR | N |
|--------|---------|-----------|-----------|-----------|-----|---|
| A | Text similarity only | 0 | 0 | 0 | 0 | 0 |
| B | A + component overlap | 0 | 0 | 0 | 0 | 0 |
| C | B + file affinity | 0 | 0 | 0 | 0 | 0 |
| D | C + recency | 0 | 0 | 0 | 0 | 0 |
| E | Full model (all 6 signals) | 0 | 0 | 0 | 0 | 0 |

## Raw JSON
```json
{
  "A": {
    "top1": 0,
    "top3": 0,
    "top5": 0,
    "mrr": 0,
    "n": 0,
    "config": "A",
    "config_name": "Text similarity only"
  },
  "B": {
    "top1": 0,
    "top3": 0,
    "top5": 0,
    "mrr": 0,
    "n": 0,
    "config": "B",
    "config_name": "A + component overlap"
  },
  "C": {
    "top1": 0,
    "top3": 0,
    "top5": 0,
    "mrr": 0,
    "n": 0,
    "config": "C",
    "config_name": "B + file affinity"
  },
  "D": {
    "top1": 0,
    "top3": 0,
    "top5": 0,
    "mrr": 0,
    "n": 0,
    "config": "D",
    "config_name": "C + recency"
  },
  "E": {
    "top1": 0,
    "top3": 0,
    "top5": 0,
    "mrr": 0,
    "n": 0,
    "config": "E",
    "config_name": "Full model (all 6 signals)"
  }
}
```