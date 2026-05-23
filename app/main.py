from fastapi import FastAPI
from app.api.v1.chat import router as chat_router
from app.api.v1.health import router as health_router
from app.middleware.request_logging import RequestLogMiddleware
from app.core.exceptions import AppException
from app.core.exception_handler import app_exception_handler, global_exception_handler
from contextlib import asynccontextmanager

# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("System startup tasks...")
    yield
    print("System shutdown tasks...")

app = FastAPI(
    title="Enterprise AI Gateway",
    version="1.0.0",
    lifespan=lifespan
)

# 注册全局中间件
app.add_middleware(RequestLogMiddleware)

# 注册全局异常处理
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# 注册路由
app.include_router(health_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")