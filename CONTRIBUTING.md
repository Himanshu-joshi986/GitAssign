# Contributing to GitAssign

This guide covers the local workflow,
conventions, and review checklist.

## Development setup

```bash
git clone <repository-url>
cd GitAssign
cp .env.example .env

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.db.init_db
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

The full stack can also run with Docker:

```bash
docker compose up --build
```

## Branch and commit conventions

- Branch from `main` using `feat/<topic>`, `fix/<topic>`, `docs/<topic>`, or
  `chore/<topic>`.
- Use [Conventional Commits](https://www.conventionalcommits.org/):
  `feat: add workload-aware batch preview`, `fix(ingestion): handle empty labels`.
- Keep commits focused and explain *why* in the body when the change is not
  obvious.

## Code guidelines

- **Backend:** Python 3.11, 4-space indentation, type hints where practical.
  Keep scoring logic deterministic and free of network calls.
- **Frontend:** TypeScript with strict mode. Prefer RTK Query hooks over manual
  `fetch` calls.
- **Configuration:** never hard-code secrets. Add new settings to
  `.env.example` and the README configuration table.
- **Secrets and keys:** never commit `GITHUB_TOKEN`, `GEMINI_API_KEY`, or any
  credential — keep them in your local `.env` (gitignored) and only ever copy
  the placeholder entries into `.env.example`.
- **Paths:** resolve data, docs, and config paths relative to the `backend/`
  directory so local runs and the Docker image behave the same way.

## Tests

Run the backend suite before opening a pull request:

```bash
cd backend
pytest -v
```

Build the frontend to catch TypeScript errors:

```bash
cd frontend
npm run build
```

Add or update tests for every behavior change. API tests live in
`backend/tests/test_api.py`; scoring and profile tests live in
`backend/tests/test_core.py`; AI pipeline cache/fallback tests live in
`backend/tests/test_ai_pipeline.py`. The whole suite must run offline —
tests monkeypatch the LLM client and never need a real `GEMINI_API_KEY`.

## Pull request checklist

- [ ] The change is scoped to one logical purpose.
- [ ] Backend tests pass (`pytest`).
- [ ] Frontend builds (`npm run build`).
- [ ] New configuration is documented in `.env.example` and `README.md`.
- [ ] No secrets, local databases, or generated cache files are committed.
- [ ] The README or `docs/` is updated when behavior or workflows change.

## Reporting bugs

Open an issue with:

1. What you expected to happen.
2. What actually happened, including logs or screenshots.
3. Reproduction steps and your environment (OS, Docker or local, Python/Node
   versions).

Do not include GitHub tokens or other credentials in issue reports.
