# pet

## Launch(only with Docker Desktop)

```sh
uv sync
docker compose up -d --build
```

## Run Tests

### Without Docker Desktop

```sh
uv sync
uv run pytest -m "not integration"
```

### With Docker Desktop

```sh
uv sync
uv run pytest
```
