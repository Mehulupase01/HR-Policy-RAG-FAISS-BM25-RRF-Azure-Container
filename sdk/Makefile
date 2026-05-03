.PHONY: help setup lint format test test-unit test-integration pre-commit clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Set up local development environment
	python3.11 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip
	. .venv/bin/activate && pip install -r backend/requirements.txt
	. .venv/bin/activate && pip install -r requirements-dev.txt
	. .venv/bin/activate && pre-commit install
	@echo "✅ Dev environment ready. Run: source .venv/bin/activate"

lint: ## Run linters (black check, isort check, flake8, mypy)
	black --check backend/
	isort --check-only backend/
	flake8 backend/ --max-line-length=120 --extend-ignore=E203,W503
	mypy backend/ --ignore-missing-imports

format: ## Auto-format code with black and isort
	black backend/
	isort backend/

test: ## Run all tests
	cd backend && python -m pytest tests/ -v

test-unit: ## Run unit tests only
	cd backend && python -m pytest tests/unit -v

test-integration: ## Run integration tests only (requires Azure resources)
	cd backend && python -m pytest tests/integration -v -m integration

pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/ coverage.xml
