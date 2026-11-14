import json
import logging
import os
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mangum import Mangum
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api import DB, router

logger = logging.getLogger("mortgageflow")
logger.setLevel(logging.INFO)
cloud = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
app = FastAPI(
    title="MortgageFlow",
    version="1.0.0",
    description="Synthetic mortgage processing and example rules for educational use.",
    docs_url=None if cloud else "/docs",
    redoc_url=None if cloud else "/redoc",
    openapi_url=None if cloud else "/openapi.json",
)
app.include_router(router)


def error(request: Request, status: int, message: str, *, fields=None, headers=None):
    code = {
        400: "BAD_REQUEST",
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "INVALID_INPUT",
        500: "INTERNAL_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }.get(status, "HTTP_ERROR")
    return JSONResponse(
        status_code=status,
        headers=headers,
        content={
            "code": code,
            "message": message,
            "correlation_id": request.state.correlation_id,
            "fields": fields or [],
        },
    )


@app.middleware("http")
async def trace(request: Request, call_next):
    request.state.correlation_id = str(uuid4())
    start = perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "unexpected_failure correlation_id=%s type=%s",
            request.state.correlation_id,
            type(exc).__name__,
        )
        response = error(request, 500, "An unexpected error occurred")
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    response.headers["Cache-Control"] = "no-store"
    route = request.scope.get("route")
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "route": getattr(route, "path", "unmatched"),
                "method": request.method,
                "status": response.status_code,
                "correlation_id": request.state.correlation_id,
                "duration_ms": round((perf_counter() - start) * 1000, 2),
            }
        )
    )
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return error(request, exc.status_code, str(exc.detail), headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    fields = [
        {"field": ".".join(map(str, item["loc"])), "type": item["type"]} for item in exc.errors()
    ]
    return error(request, 422, "Request validation failed", fields=fields)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logger.error(
        "database_failure correlation_id=%s type=%s",
        request.state.correlation_id,
        type(exc).__name__,
    )
    return error(request, 503, "Database operation failed")


@app.get("/health", tags=["operations"])
def health():
    return {"status": "ok"}


@app.get("/ready", tags=["operations"])
def ready(db: DB):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


handler = Mangum(app, lifespan="off")
