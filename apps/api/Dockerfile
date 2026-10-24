FROM ghcr.io/astral-sh/uv:0.11.16 AS uv

FROM python:3.15.0-slim-bookworm AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /srv/api
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.15.0-slim-bookworm
RUN useradd --system --uid 10001 --home-dir /srv/api api
WORKDIR /srv/api
COPY --from=build /srv/api/.venv /srv/api/.venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
ENV PATH="/srv/api/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*"]
