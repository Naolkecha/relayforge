FROM python:3.12-slim AS builder
WORKDIR /build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --prefix=/install .

FROM python:3.12-slim AS runtime
RUN groupadd --system relayforge && useradd --system --gid relayforge --home /app relayforge
WORKDIR /app
COPY --from=builder /install /usr/local
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
USER relayforge
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)" || exit 1
CMD ["uvicorn", "relayforge.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
