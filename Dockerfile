FROM python:3.13-slim AS base

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md /app/

FROM base AS runtime-deps

RUN uv sync --frozen --no-install-project --no-dev

FROM runtime-deps AS runtime

COPY src/ src/

RUN uv sync --frozen --no-dev

ENV DEBUG=False \
    APP_NAME=pet-uk4wa

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn" \
    ,"--factory", "pet.main:create_app" \
    ,"--port", "8000" \
    ,"--host", "0.0.0.0"]

FROM base AS migrate-deps

RUN uv sync --frozen --no-install-project --group migration --no-dev

FROM migrate-deps AS migrate

COPY src/ src/

COPY alembic/ alembic/
COPY alembic.ini .

RUN uv sync --frozen --group migration --no-dev

CMD ["uv", "run", "--no-sync", "alembic", "upgrade", "head"]