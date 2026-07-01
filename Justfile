default:
    @just --list

# ─── App (Expo) ──────────────────────────────────────────────
app-install:
    cd app && npm install
app-dev:
    cd app && npm run dev:sim
app-web:
    cd app && npm run web
app-lint:
    cd app && npm run lint
app-typecheck:
    cd app && npx tsc --noEmit
app-codegen:
    cd app && npm run codegen          # orval ← backend OpenAPI

# ─── Backend (Litestar) ──────────────────────────────────────
install:
    cd backend && uv sync --dev
dev-backend:
    cd backend && uv run litestar --app app.index:app run -r -d -p 8000
dev-worker:
    cd backend && uv run litestar --app app.index:app workers run
test:
    cd backend && uv run pytest -v
lint-backend:
    cd backend && uv run ruff check --fix . && uv run ruff format .
check-backend:
    cd backend && uv run basedpyright
docker-build:
    cd backend && docker build -t pear-api:local .

# ─── Database (local docker) ─────────────────────────────────
db-start:
    cd backend && docker compose -f docker-compose.dev.yml up -d
db-stop:
    cd backend && docker compose -f docker-compose.dev.yml down
db-upgrade:
    cd backend && uv run alembic upgrade head
db-migrate +msg:
    cd backend && uv run alembic revision --autogenerate -m "{{msg}}"
    cd backend && uv run ruff check --fix alembic/versions/ && uv run ruff format alembic/versions/
db-downgrade:
    cd backend && uv run alembic downgrade -1
db-psql:
    psql postgresql://postgres:postgres@localhost:5432/pear

# ─── Combined dev ────────────────────────────────────────────
dev:
    #!/usr/bin/env bash
    trap 'kill 0' EXIT
    (cd backend && uv run litestar --app app.index:app run -r -d -p 8000) &
    (cd backend && uv run litestar --app app.index:app workers run) &
    (cd app && npm run dev:sim) &
    wait

# ─── Infra ───────────────────────────────────────────────────
tf-init:
    cd infra && ./scripts/tf-init.sh
tf-plan:
    cd infra && terraform plan
tf-apply:
    cd infra && terraform apply
prod-ssh *ARGS:
    ./scripts/prod-ssh.sh {{ARGS}}      # SSM shell on the box
