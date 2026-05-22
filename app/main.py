from fastapi import FastAPI

from app.api.v1.chat import router as chat_router
from app.api.v1.health import router as health_router

from app.middleware.request_logging import RequestLogMiddleware

app = FastAPI(
    title="Enterprise AI Gateway",
    version="1.0.0"
)

app.add_middleware(
    RequestLogMiddleware
)

app.include_router(
    health_router,
    prefix="/api/v1"
)

app.include_router(
    chat_router,
    prefix="/api/v1"
)