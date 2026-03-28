# miniClima EBC10 — task runner
# https://just.systems

set dotenv-load

port := env_var_or_default("EBC10_PORT", "/dev/ttyACM0")

# List available recipes
default:
    @just --list

# Sync all workspace packages
sync:
    uv sync

# Run the FastAPI dev server (hot-reload, 0.0.0.0:8000)
api:
    uv run --no-sync --package miniclima-api uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

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

# rsync project to bill (excludes .venv, __pycache__, uv.lock)
deploy:
    rsync -av --exclude .venv --exclude __pycache__ --exclude '*.pyc' --exclude uv.lock \
        ./ bill:/home/khrap/miniclima/

# Run uv sync on bill
sync-bill:
    ssh bill "cd /home/khrap/miniclima && uv sync"

# Deploy + sync bill in one shot
push: deploy sync-bill
