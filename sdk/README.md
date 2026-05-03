# RAG + Python SDK Template

Standardised GitHub repository template for Retrieval-Augmented Generation (RAG) projects built on Azure. Clone this repo to bootstrap new AI projects with consistent structure, tooling, and deployment patterns.

## Project Structure

```
.
├── backend/                 # Python Azure Functions — RAG agent, API, ingestion
│   ├── agent/               #   RAG agent core (retriever, embeddings, generator)
│   ├── blob_client/         #   Azure Blob Storage wrapper + validation
│   ├── ingestion/           #   Document parsing, chunking, embedding pipeline
│   ├── tests/               #   Unit & integration tests
│   ├── deploy.sh            #   One-command Azure deployment
│   ├── run.sh               #   Local dev helper (tests, func start)
│   ├── function_app.py      #   Azure Functions entry point
│   └── .env.example         #   Required environment variables
├── frontend/                # Client application (Next.js recommended)
├── database/                # Database setup, migrations, deployment scripts
├── qdrant/                  # Local Qdrant vector DB management
│   └── run.sh               #   Docker start/stop/status
├── planning/                # Project planning artifacts
│   ├── plan.md              #   Vision, backlog, sprint plan template
│   └── erd-template.md      #   Entity Relationship Diagram template
├── docs/                    # Documentation
│   ├── azure-deployment-tiers.md  # Dev / Staging / Prod resource specs
│   └── branching-strategy.md      # Git workflow & branch protection rules
├── sample_docs/             # Test documents for ingestion development
├── .github/                 # PR template, issue templates
├── AGENTS.md                # AI assistant collaboration guidelines
├── Makefile                 # Common commands (setup, lint, format, test)
├── pyproject.toml           # Python tooling config (black, isort, mypy, pytest)
├── .pre-commit-config.yaml  # Pre-commit hooks
└── requirements-dev.txt     # Dev tooling dependencies
```

## Quick Start

### 1. Clone & set up

```bash
# Clone the template (or use GitHub "Use this template" button)
git clone https://github.com/your-org/rag-python-sdk-template.git my-project
cd my-project

# Set up Python environment + pre-commit hooks
make setup
source .venv/bin/activate
```

### 2. Configure environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your Azure credentials
```

### 3. Start local services

```bash
# Start Qdrant (requires Docker)
./qdrant/run.sh start

# In another terminal — start the backend
cd backend && ./run.sh start
```

### 4. Run tests

```bash
make test-unit        # Fast, no external deps
make test-integration # Requires Azure resources
make lint             # Black, isort, flake8, mypy
```

## Development Workflow

| Command | Description |
|---------|-------------|
| `make setup` | Create venv, install deps, set up pre-commit hooks |
| `make lint` | Run all linters (black, isort, flake8, mypy) |
| `make format` | Auto-format code |
| `make test` | Run all tests |
| `make test-unit` | Run unit tests only |
| `make test-integration` | Run integration tests (requires Azure) |
| `make pre-commit` | Run pre-commit hooks on all files |
| `make clean` | Remove caches and build artifacts |

## Azure Deployment Tiers

Three standard tiers are defined in [`docs/azure-deployment-tiers.md`](docs/azure-deployment-tiers.md):

| Tier | Monthly Budget | Key Resources |
|------|---------------|---------------|
| **Development** | €50 – €150 | Consumption Functions, local Qdrant, Azurite |
| **Staging** | ≤ €150 | Consumption Functions, ACI Qdrant, App Service + PocketBase |
| **Production** | ≤ €250 | Consumption Functions, ACI Qdrant, PostgreSQL Flexible, Key Vault |

Deploy the backend with one command:

```bash
cd backend && ./deploy.sh
```

## Git Workflow

Full details in [`docs/branching-strategy.md`](docs/branching-strategy.md).

```
feature branch  ──PR──▶  dev  ──PR──▶  main
```

- **No direct pushes to `main` or `dev`** — all changes via pull requests.
- **Feature branches** are named after the **Monday ticket**: `dev - Exact verbeteren`.
- **Flow:** feature branch → PR to `dev` (squash-merge) → PR from `dev` to `main` (merge).
- **Commit format:** `type(scope): description` ([Conventional Commits](https://www.conventionalcommits.org/)).
- **Required CI checks:** `lint` + `test-unit` must pass before merge.

## Planning & Architecture

Before building, update the planning artifacts:

1. **Project plan** — [`planning/plan.md`](planning/plan.md): vision, backlog, sprint plan.
2. **Architecture & data model** — [`planning/erd-template.md`](planning/erd-template.md): system architecture, data flows, API contracts, vector store schema, database ERD, and environment variables. Fill this out *before* coding.

## AI Assistant Guidelines

See [`AGENTS.md`](AGENTS.md) for conventions when working with AI coding assistants (commit strategy, file access, development approach).

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11, Azure Functions v4 |
| **Vector DB** | Qdrant |
| **Embeddings** | Azure OpenAI (`text-embedding-ada-002` / `text-embedding-3-large`) |
| **LLM** | Azure OpenAI (`gpt-4o`, `gpt-4o-mini`) |
| **Storage** | Azure Blob Storage |
| **Frontend** | Next.js (recommended) |
| **Database** | PocketBase / PostgreSQL |
| **CI/CD** | GitHub Actions (recommended) |
| **Linting** | Black, isort, flake8, mypy, pre-commit |

## Using This Template

1. Click **"Use this template"** on GitHub (or clone manually).
2. Rename resource references in `backend/deploy.sh` (resource group, storage account, function app name).
3. Copy and fill in `backend/.env.example` → `backend/.env`.
4. Customise `planning/plan.md` with your project's vision and backlog.
5. Create your ERD in `planning/erd-template.md` before starting the build phase.
6. Set up branch protection rules on `main` per `docs/branching-strategy.md`.
7. Start building!

## License

_Add your license here._
