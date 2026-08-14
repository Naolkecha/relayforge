# Integration tests

These tests intentionally require real PostgreSQL and Redis instances. The GitHub Actions `integration`
job provisions both services, applies Alembic migrations, then runs `pytest -m integration --no-cov`.

For local execution, start the dependencies with Docker Compose and point the test environment at a
dedicated test database. Never run destructive integration tests against production data.
