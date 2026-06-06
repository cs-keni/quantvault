.PHONY: dev test lint fmt migrate seed

# Run the full stack (backend, frontend, db, redis, celery-worker) via Docker Compose.
dev:
	docker compose up --build

# Run backend tests against the test database.
test:
	cd backend && .venv/bin/pytest

# Lint + type-check the backend.
lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/mypy app

# Auto-format + auto-fix the backend.
fmt:
	cd backend && .venv/bin/ruff format . && .venv/bin/ruff check --fix .

# Apply pending Alembic migrations.
migrate:
	cd backend && .venv/bin/alembic upgrade head

# Seed the dev database with a demo user + demo portfolio.
seed:
	cd backend && .venv/bin/python -m app.scripts.seed
