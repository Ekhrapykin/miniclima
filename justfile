# miniClima EBC10 — task runner
# https://just.systems

set dotenv-load

port          := env_var_or_default("EBC10_PORT", "/dev/ttyACM0")
api_port      := env_var_or_default("API_PORT", "8000")
frontend_port := env_var_or_default("FRONTEND_PORT", "3000")
cors_origins  := env_var_or_default("CORS_ORIGINS", "http://localhost:3000")
api_url       := env_var_or_default("NEXT_PUBLIC_API_URL", "http://localhost:8000")

# List available recipes
default:
    @just --list

# Sync all workspace packages
sync:
    uv sync

# Run the FastAPI dev server (hot-reload)
api:
    uv run --no-sync --package miniclima-api uvicorn api.main:app --reload --host 0.0.0.0 --port {{api_port}}

# Build API Docker image
docker-build-api:
    docker build -t miniclima-api .

# Build frontend Docker image (bakes in NEXT_PUBLIC_API_URL at build time)
docker-build-frontend:
    docker build -t miniclima-frontend \
        --build-arg NEXT_PUBLIC_API_URL={{api_url}} \
        frontend/

# Run API container (requires serial device)
docker-api:
    docker run -d \
        --device={{port}}:{{port}} \
        -p {{api_port}}:8000 \
        -e EBC10_PORT={{port}} \
        -e CORS_ORIGINS={{cors_origins}} \
        --name ebc10-api \
        miniclima-api

# Run frontend container
docker-frontend:
    docker run -d \
        -p {{frontend_port}}:3000 \
        --name ebc10-frontend \
        miniclima-frontend

# Build both images
docker-build: docker-build-api docker-build-frontend

# Start full stack (API + frontend + Prometheus + Grafana)
docker-up:
    docker compose up -d

# Stop full stack
docker-down:
    docker compose down

docker-restart: docker-down docker-build docker-up
    docker compose ps

# Show running containers
docker-ps:
    docker compose ps

# Follow logs (optionally pass a service name: just docker-logs api)
docker-logs service="":
    docker compose logs -f {{service}}

# Run the EBC10 CLI — e.g. just cli status, just cli set-sp 55
cli *args:
    uv run --no-sync ebc10 --port {{port}} {{args}}

# Quick device status
status:
    uv run --no-sync ebc10 --port {{port}} status

# Passive logger — streams device pushes to CSV (default: ebc10_log.csv)
logger output="ebc10_log.csv":
    uv run --no-sync python tools/logger.py --port {{port}} --output {{output}}

# Protocol relay sniffer (Windows dev tool — edit TOOL_PORT/DEVICE_PORT in tools/relay.py first)
relay:
    uv run --no-sync python tools/relay.py

# Frontend dev server (Next.js)
frontend-dev:
    cd frontend && npm run dev -- --port {{frontend_port}}

# Build frontend for production
frontend-build:
    cd frontend && npm run build

# Lint frontend
frontend-lint:
    cd frontend && npm run lint

# rsync project to ben (excludes .venv, __pycache__, uv.lock)
deploy:
    rsync -av --exclude .venv --exclude __pycache__ --exclude '*.pyc' --exclude uv.lock \
        ./ ben:/home/khrap/miniclima/

# Run uv sync on ben
sync-ben:
    ssh ben "cd /home/khrap/miniclima && uv sync"

# Deploy + sync ben in one shot
push: deploy sync-ben
