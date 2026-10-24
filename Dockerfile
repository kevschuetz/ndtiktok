FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first (cached layer), then the project itself (editable install,
# so the bind-mounted src/ is what runs).
COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --frozen --no-install-project --all-extras

COPY src/ ./src/
COPY tests/ ./tests/
RUN uv sync --frozen --all-extras

ENV NDC_DB=/data/ndc.db \
    NDC_CONFIG_DIR=/app/config

ENTRYPOINT ["uv", "run", "--no-sync", "ndc"]
