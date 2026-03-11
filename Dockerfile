FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md /app/

RUN uv sync --frozen --no-install-project

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

RUN uv sync --frozen

ENV DEBUG=False \
    APP_NAME=pet-uk4wa

EXPOSE 8000

CMD ["uv", "run", "uvicorn" \
    ,"--port", "8000" \
    ,"--host", "0.0.0.0" \
    ,"pet.main:create_app"]