# Runtime data

This directory holds generated state only. Its contents are **not committed to
Git** (see `.gitignore`).

| Path | Description |
| --- | --- |
| `gitassign.db` | SQLite database created on first startup |
| `gitassign.db-wal` / `-shm` | SQLite write-ahead log files |
| `cache/` | Raw GitHub API responses, cached per repository |

Both locations can be overridden with `DB_PATH` and `CACHE_DIR`. When running
with Docker Compose, this directory is mounted at `/app/data`.

Datasets are stored separately in [`../datasets`](../datasets/README.md).

To reset all local state, stop the stack and remove the generated files:

```bash
docker compose down
rm -rf data/gitassign.db data/gitassign.db-wal data/gitassign.db-shm data/cache
```
