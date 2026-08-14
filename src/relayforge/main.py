from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from relayforge.api.middleware import RequestContextMiddleware
from relayforge.api.routes import auth, health, workflows
from relayforge.config import Settings, get_settings
from relayforge.errors import RelayForgeError
from relayforge.execution.engine import WorkflowEngine
from relayforge.execution.executors import DefaultStepExecutor
from relayforge.infra.db.session import Database
from relayforge.infra.queue.idempotency import RedisExecutionIdempotencyStore
from relayforge.logging import configure_logging
from relayforge.security.ssrf import SSRFGuard
from relayforge.security.tokens import TokenService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = Database(settings)
        token_service = TokenService(
            secret=settings.jwt_secret,
            access_ttl_seconds=settings.access_token_ttl_seconds,
            refresh_ttl_seconds=settings.refresh_token_ttl_seconds,
        )
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        ssrf_guard = SSRFGuard(
            block_private_networks=settings.block_private_networks,
            allowed_hosts=settings.allowed_http_hosts,
        )
        engine = WorkflowEngine(
            executor=DefaultStepExecutor(
                ssrf_guard=ssrf_guard,
                max_response_bytes=settings.max_http_response_bytes,
            ),
            idempotency_store=RedisExecutionIdempotencyStore(redis),
        )
        app.state.settings = settings
        app.state.database = database
        app.state.token_service = token_service
        app.state.redis = redis
        app.state.workflow_engine = engine
        logger.info("application started", extra={"environment": settings.environment})
        try:
            yield
        finally:
            await redis.aclose()
            await database.close()
            logger.info("application stopped")

    app = FastAPI(
        title="RelayForge",
        version="0.1.0",
        description="Secure API-first workflow orchestration service.",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    app.include_router(auth.router, prefix="/v1")
    app.include_router(workflows.router, prefix="/v1")

    @app.exception_handler(RelayForgeError)
    async def relayforge_error_handler(request: Request, exc: RelayForgeError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": str(exc),
                    "request_id": request_id,
                }
            },
        )

    return app


app = create_app()
