from starlette.middleware.base import BaseHTTPMiddleware
import time
from app.core.logging import logger

class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            process_time=process_time
        )
        return response