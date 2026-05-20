# Minimal fake-linear image for the test stack.
FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY apps/fake-linear/pyproject.toml ./pyproject.toml
COPY apps/fake-linear/app ./app

ENV UV_LINK_MODE=copy

RUN uv sync --no-dev || uv sync

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
