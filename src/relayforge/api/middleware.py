from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import Request, Response
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)
REQUEST_COUNT = Counter(
    "relayforge_http_requests_total",
    "HTTP requests processed",
    ["method", "path", "status"],
)
REQUEST_DURATION = Histogram(
    "relayforge_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"],
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))[:128]
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            elapsed = time.perf_counter() - started
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            REQUEST_COUNT.labels(request.method, path, str(status_code)).inc()
            REQUEST_DURATION.labels(request.method, path).observe(elapsed)
            logger.info(
                "http request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round(elapsed * 1000, 2),
                },
            )
