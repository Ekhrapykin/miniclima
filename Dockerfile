FROM python:3.13-slim

# Install uv (pip wheel works on all platforms including ARM)
RUN pip install --no-cache-dir uv

WORKDIR /app

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    UV_NO_CACHE=1

# Copy only the workspace files needed for the API and its ebc10 dependency
COPY pyproject.toml uv.lock ./
COPY packages/ebc10 packages/ebc10/
COPY apps/api apps/api/

# Install miniclima-api + ebc10 (fastapi, uvicorn, pyserial) — no dev deps
RUN uv sync --frozen --package miniclima-api --no-dev

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
