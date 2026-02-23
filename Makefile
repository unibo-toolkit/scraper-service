.DEFAULT_GOAL := help

DB_URL ?= postgresql://unibo_user:unibo_pass@localhost:5432/unibo_toolkit?sslmode=disable

MIGRATIONS_DIR ?= ../databases/migrations

## Development

.PHONY: setup
setup: ## First-time setup (install deps, setup .env, clone databases repo)
	@echo "==> Installing dependencies..."
	poetry install
	@echo "\n==> Setting up .env..."
	@test -f .env || cp .env.example .env
	@echo "\n==> Cloning databases repo (if not exists)..."
	@if [ ! -d "../databases" ]; then \
		cd .. && git clone https://github.com/unibo-toolkit/databases.git; \
	else \
		echo "databases repo already exists"; \
	fi
	@echo "\n[OK] Setup complete! Next steps:"
	@echo "  1. Edit .env with your settings"
	@echo "  2. Run: make dev-up"
	@echo "  3. Run: make migrate-up"
	@echo "  4. Run: make run"

.PHONY: run
run: ## Run scraper service locally
	poetry run python -m app

## Docker Compose - dev

.PHONY: dev-up
dev-up: ## Start dev services (postgres + redis)
	docker compose -f docker-compose.dev.yaml up -d postgres redis
	@echo "Waiting for PostgreSQL to be ready..."
	@until docker compose -f docker-compose.dev.yaml exec postgres pg_isready -U unibo_user > /dev/null 2>&1; do sleep 1; done
	@echo "[OK] PostgreSQL is ready!"
	@echo "[OK] Redis is ready!"
	@echo "\nNext: run 'make migrate-up' to apply migrations"

.PHONY: dev-down
dev-down: ## Stop dev services
	docker compose -f docker-compose.dev.yaml down

.PHONY: dev-clean
dev-clean: ## Stop dev services and remove volumes
	docker compose -f docker-compose.dev.yaml down -v
	@echo "[WARNING]  All data removed!"

## Database Migrations

.PHONY: migrate-up
migrate-up: ## Apply all pending migrations
	@if [ ! -d "$(MIGRATIONS_DIR)" ]; then \
		echo "[ERROR] Error: $(MIGRATIONS_DIR) not found!"; \
		echo "Run 'make setup' first to clone databases repo"; \
		exit 1; \
	fi
	migrate -path $(MIGRATIONS_DIR) -database "$(DB_URL)" up
	@echo "[OK] Migrations applied!"

.PHONY: migrate-down
migrate-down: ## Rollback last migration
	migrate -path $(MIGRATIONS_DIR) -database "$(DB_URL)" down 1

.PHONY: migrate-reset
migrate-reset: ## Rollback all migrations
	migrate -path $(MIGRATIONS_DIR) -database "$(DB_URL)" down

.PHONY: migrate-version
migrate-version: ## Show current migration version
	migrate -path $(MIGRATIONS_DIR) -database "$(DB_URL)" version

## Model Generation

.PHONY: models-sync
models-sync: ## Generate SQLAlchemy models from database schema
	@echo "==> Generating models from database..."
	@mkdir -p app/models
	poetry run sqlacodegen postgresql://unibo_user:unibo_pass@localhost:5432/unibo_toolkit \
		--outfile app/models/generated.py \
		--generator declarative
	@echo "[OK] Models generated in app/models/generated.py"
	@echo "\nNext: Review changes with 'git diff app/models/generated.py'"

.PHONY: models-check
models-check: ## Check if models are in sync with database
	@echo "==> Checking model synchronization..."
	@poetry run sqlacodegen postgresql://unibo_user:unibo_pass@localhost:5432/unibo_toolkit \
		--generator declarative > /tmp/models_check.py
	@if diff -q app/models/generated.py /tmp/models_check.py > /dev/null 2>&1; then \
		echo "[OK] Models are in sync with database!"; \
	else \
		echo "[WARNING] Models are OUT OF SYNC with database!"; \
		echo "Run 'make models-sync' to update models"; \
		exit 1; \
	fi
	@rm -f /tmp/models_check.py

## Helpers

.PHONY: install-migrate
install-migrate: ## Install golang-migrate tool
	@echo "Installing golang-migrate..."
	@if command -v brew >/dev/null 2>&1; then \
		brew install golang-migrate; \
	elif [ "$$(uname)" = "Linux" ]; then \
		curl -L https://github.com/golang-migrate/migrate/releases/download/v4.17.0/migrate.linux-amd64.tar.gz | tar xvz; \
		sudo mv migrate /usr/local/bin/; \
	else \
		echo "Please install golang-migrate manually: https://github.com/golang-migrate/migrate"; \
		exit 1; \
	fi
	@echo "[OK] golang-migrate installed!"

.PHONY: clean
clean: ## Clean up cache and temp files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov .coverage
	@echo "[OK] Cleaned up cache files"

.PHONY: help
help: ## Show this help message
	@echo "Scraper Service - Development Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make setup          # First time setup"
	@echo "  2. make dev-up         # Start postgres + redis"
	@echo "  3. make migrate-up     # Apply migrations"
	@echo "  4. make run            # Run service"
