FROM python:3.13-slim

WORKDIR /app

# RUN apt-get update

COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project

COPY . .

RUN uv sync --frozen

ENV DEBUG=True \
    APP_NAME=pet-uk4wa

CMD ["uv", "run", "uvicorn", \
    "--host", "0.0.0.0", \
    "--port", "8000",\
    "--app-dir", "src", \
    "pet.main:app"]