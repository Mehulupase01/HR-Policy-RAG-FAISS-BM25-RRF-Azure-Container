# Repository Guidelines

## Project Structure & Module Organisation

- `backend/` — Python Azure Functions app: RAG agent, blob client, ingestion pipeline, API endpoints.
- `frontend/` — Client application (Next.js recommended). Treat `app/page.tsx` as the main entry.
- `database/` — Database setup, migrations, and deployment scripts.
- `planning/` — Standardised workflow artifacts: vision, backlog, architecture, sprint & implementation plans.
- `qdrant/` — Local vector DB management scripts and persistent data.
- `docs/` — Architecture docs, deployment tiers, branching strategy.
- `sample_docs/` — Test documents for ingestion pipeline development.

**Rule:** Update `planning/` artifacts *before* touching code. Keep generated assets in their directories and never commit transient data.

## Build, Test, and Development Commands

```bash
# One-time setup
make setup

# Run linters
make lint

# Auto-format
make format

# Run tests
make test          # all tests
make test-unit     # unit only
make test-integration  # integration only (requires Azure resources)

# Backend local server
cd backend && ./run.sh start

# Qdrant local
./qdrant/run.sh start
```

## Coding Style & Naming Conventions

- **Python:** Black (120 chars), isort (black profile), flake8, mypy.
- **Naming:** `snake_case` for modules/functions/variables, `PascalCase` for classes.
- **TypeScript/React (frontend):** PascalCase for components, camelCase for hooks/utilities.
- Run `make lint` before every commit. Pre-commit hooks enforce this automatically.

## Testing Guidelines

- Unit tests: `backend/tests/unit/` — fast, no external dependencies.
- Integration tests: `backend/tests/integration/` — marked with `@pytest.mark.integration`.
- Frontend: Jest + React Testing Library, colocated as `*.test.tsx`.
- Aim for meaningful coverage on business logic (agent, ingestion, validation).

## Commit & Pull Request Guidelines

- Prefix commits: `type(scope): description` (see `docs/branching-strategy.md`).
- Each PR must include: problem statement, solution notes, test evidence, screenshots for UI.
- Never merge without updating `planning/` artifacts if scope changed.
- Never merge without passing CI (lint + unit tests).

---

## AI Agent Collaboration

### Git Workflow with AI Assistants

When working with AI coding assistants (Gemini, Claude, GitHub Copilot, etc.):

**Branch model:** `dev - {Monday ticket}` → PR to `dev` → PR to `main`. See `docs/branching-strategy.md`.

**Commit strategy:**
- AI commits logical chunks of work as tasks are completed.
- Significant changes: AI shows commit message and asks for approval before committing.
- Minor updates (typos, formatting, docs): AI commits directly and notifies.
- All commits follow conventional commit format: `type(scope): description`.
- AI always works on a feature branch named after the Monday ticket, never directly on `dev` or `main`.

**Example:**
```bash
git checkout dev && git pull origin dev
git checkout -b "dev - Exact verbeteren"
# ... work ...
git add backend/ingestion/
git commit -m "feat(exact): implement document chunking with overlap"
git push origin "dev - Exact verbeteren"
# Then open PR → dev
```

### File Access & Environment

- AI can access all repository files except those in `.gitignore`.
- AI works within Python virtual environments: assumes `source .venv/bin/activate`.
- AI has access to `.env.example` files to understand configuration but **never** actual secrets.
- Local services (Qdrant, database) are started via their respective `run.sh` scripts.

### Development Approach

- AI follows the phased plan in `planning/plan.md`.
- AI updates `planning/` artifacts before making code changes.
- AI runs tests (`make test`) before committing.
- AI creates `.env.example` entries when new environment variables are introduced.

### Communication Style

- AI asks for clarification when requirements are ambiguous.
- AI notifies about blocking issues or missing dependencies immediately.
- AI provides commit previews for review before significant changes.
- AI documents trade-offs and design decisions in code comments or planning docs.
