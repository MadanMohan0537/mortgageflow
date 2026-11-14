"""MortgageFlow FastAPI application entrypoint."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from mangum import Mangum

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, correlation_id_var, get_logger
from app.schemas.common import HealthResponse

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s (%s)", settings.app_name, settings.app_env)
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Cloud-based mortgage application processing & validation system. "
        "Educational simulation only — synthetic data, demo rules, not credit decisions."
    ),
    lifespan=lifespan,
)
register_exception_handlers(app)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    header_name = settings.correlation_header
    correlation_id = request.headers.get(header_name) or str(uuid.uuid4())
    token = correlation_id_var.set(correlation_id)
    try:
        response: Response = await call_next(request)
    finally:
        correlation_id_var.reset(token)
    response.headers[header_name] = correlation_id
    return response


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, env=settings.app_env)


app.include_router(api_router, prefix=settings.api_prefix)

# AWS Lambda adapter (API Gateway HTTP API / REST)
handler = Mangum(app, lifespan="off")
