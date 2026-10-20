# GitAssign — Ablation Results

No evaluation has been run yet.

After loading a dataset (for example Eclipse JDT) and building developer
profiles, run the ablation study from the dashboard (**Metrics → Run
Ablation**) or from the CLI:

```bash
docker compose exec backend python -m app.evaluation.ablation_runner \
    eclipse/jdt 2009-01-01 2010-01-01 200
```

Results are written back to this file and shown in the Metrics tab.
