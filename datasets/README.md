# Datasets

Place cleaned BugHub CSV files here before loading them into GitAssign. The
Eclipse JDT dataset is included for convenience; other datasets can be
downloaded from [logpai/bughub](https://github.com/logpai/bughub).

| Dataset | File | Repository slug |
| --- | --- | --- |
| Eclipse JDT | `eclipse_jdt.csv` | `eclipse/jdt` |
| Eclipse Platform | `eclipse_platform.csv` | `eclipse/platform` |
| Mozilla Firefox | `mozilla_firefox.csv` | `mozilla/firefox` |
| Mozilla Core | `mozilla_core.csv` | `mozilla/core` |
| Mozilla Thunderbird | `mozilla_thunderbird.csv` | `mozilla/thunderbird` |

> BugHub datasets are historical, so their issues are imported as **closed**.
> In the dashboard, select the **all** or **closed** state filter to see them.

## Load a dataset

With Docker Compose (this directory is mounted at `/app/datasets`):

```bash
docker compose exec backend python scripts/load_bughub.py \
    datasets/eclipse_jdt.csv eclipse/jdt
```

Without Docker, from `backend/`:

```bash
python scripts/load_bughub.py ../datasets/eclipse_jdt.csv eclipse/jdt
```

Then open the dashboard, enter `eclipse/jdt`, click **Load Repo Data**, and
build developer profiles from the **Developers** tab.
