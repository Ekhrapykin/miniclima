# miniClima EBC10 — task runner
# https://just.systems

set dotenv-load

port          := env_var_or_default("EBC10_PORT", "/dev/ttyACM0")
api_port      := env_var_or_default("API_PORT", "8000")
frontend_port := env_var_or_default("FRONTEND_PORT", "3000")

# List available recipes
default:
    @just --list

# Sync all workspace packages
sync:
    uv sync

# Run the FastAPI dev server (hot-reload)
api:
    uv run --no-sync --package miniclima-api uvicorn api.main:app --reload --host 0.0.0.0 --port {{api_port}}

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

# rsync project to bill (excludes .venv, __pycache__, uv.lock)
deploy:
    rsync -av --exclude .venv --exclude __pycache__ --exclude '*.pyc' --exclude uv.lock \
        ./ bill:/home/khrap/miniclima/

# Run uv sync on bill
sync-bill:
    ssh bill "cd /home/khrap/miniclima && uv sync"

# Deploy + sync bill in one shot
push: deploy sync-bill
