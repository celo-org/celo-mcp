.PHONY: help install test lint format type-check build clean release-patch release-minor release-major

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync --all-extras

test: ## Run tests
	uv run pytest tests/ -v

lint: ## Run linting checks
	uv run ruff check .
	uv run black --check .

format: ## Format code
	uv run ruff check . --fix
	uv run black .

type-check: ## Run type checking
	uv run mypy src/

build: ## Build the package
	uv build

clean: ## Clean build artifacts
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

check: lint type-check test ## Run all checks (lint, type-check, test)

release-patch: ## Create a patch release (0.1.0 → 0.1.1)
	python scripts/release.py patch

release-minor: ## Create a minor release (0.1.0 → 0.2.0)
	python scripts/release.py minor

release-major: ## Create a major release (0.1.0 → 1.0.0)
	python scripts/release.py major

release-dry-run: ## Show what a patch release would do (dry run)
	python scripts/release.py patch --dry-run

version: ## Show current version
	python scripts/release.py current

dev-setup: install ## Set up development environment
	@echo "Development environment set up successfully!"
	@echo "Run 'make help' to see available commands." 