FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /app
RUN pip install --no-cache-dir uv==0.9.5
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN useradd --uid 10001 --create-home soc
ENV PATH="/app/.venv/bin:$PATH"
USER soc
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM base AS runner
COPY knowledge ./knowledge
COPY fixtures/events/training ./fixtures/events/training

FROM base AS seed
COPY knowledge ./knowledge
COPY fixtures ./fixtures
CMD ["python", "-m", "app.scenarios.seed"]

FROM seed AS test
USER root
ENV UV_HTTP_TIMEOUT=120
RUN uv sync --frozen
COPY tests ./tests
USER soc
CMD ["python", "-m", "pytest", "tests/test_database.py", "tests/test_auth.py", "tests/test_scenarios.py", "tests/test_runs.py", "tests/test_investigation_pipeline.py", "-q", "-p", "no:cacheprovider"]

# Default external build must be the API, never the test/fixture image.
FROM base AS api
