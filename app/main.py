"""
backend/app/main.py
====================
FastAPI 入口

Swagger UI 地址：http://localhost:8000/docs

测试用 Token（Header: Authorization: Bearer <token>）：
  token-manager   → 店长狮（merchant / manager）
  token-cs        → 客服汪（merchant / cs）
  token-customer  → 买家猫（customer）
  token-guest     → 游客

任务 2.3 测试场景：
  Case 1: 用 token-customer  调用 POST /products/{id}/price → 403 权限拒绝
  Case 2: 用 token-cs        调用 POST /products/{id}/price → 403 职位不足
  Case 3: 用 token-manager   调用 POST /products/{id}/price → 200 成功
  Case 4: 用 token-cs        调用 POST /orders/{id}/status  → 200 成功
  Case 5: 用 token-customer  调用 POST /orders/{id}/status（他人订单） → 403
"""

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import Optional

from app.models import User, UserRole, SubRole, create_tables, engine, get_session
from app import services


# ──────────────────────────────────────────────────────────────
# 应用实例
# ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Sentinel E-Com Agent API",
    description="哨兵电商智能中台 — 权限感知型业务 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_tables()
    print("✅ 数据库表已就绪")


# ──────────────────────────────────────────────────────────────
# 模拟 JWT：Token → User 上下文
# 真实项目替换为 python-jose 解码
# ──────────────────────────────────────────────────────────────

_FAKE_TOKEN_MAP = {
    "token-manager":  {"username": "lion_manager"},
    "token-cs":       {"username": "wang_cs"},
    "token-customer": {"username": "mao_customer"},
    "token-guest":    None,   # 游客无账号
}

_GUEST_USER = User(
    id=0,
    username="guest",
    role=UserRole.GUEST,
    sub_role=None,
)


def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    """
    Depends 注入：从 Authorization Header 解析当前用户

    格式：Authorization: Bearer token-manager
    """
    token = (authorization or "").replace("Bearer ", "").strip()

    if token not in _FAKE_TOKEN_MAP:
        # 未知 token → 当游客处理（不直接 401，让业务层决定是否拒绝）
        return _GUEST_USER

    user_info = _FAKE_TOKEN_MAP[token]
    if user_info is None:
        return _GUEST_USER

    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.username == user_info["username"])
        ).first()
        if not user:
            raise HTTPException(404, detail=f"用户 {user_info['username']} 不存在，请先运行 init_db.py")
        return user


# ──────────────────────────────────────────────────────────────
# Request / Response Schema
# ──────────────────────────────────────────────────────────────

class UpdateStatusRequest(BaseModel):
    new_status: str

    class Config:
        json_schema_extra = {
            "example": {"new_status": "已取消"}
        }


class UpdatePriceRequest(BaseModel):
    new_price: float

    class Config:
        json_schema_extra = {
            "example": {"new_price": 259.0}
        }


# ──────────────────────────────────────────────────────────────
# 路由
# ──────────────────────────────────────────────────────────────

@app.get("/", tags=["健康检查"])
def health():
    return {"status": "ok", "service": "Sentinel E-Com Agent API"}


@app.get("/me", tags=["身份信息"], summary="查看当前 Token 对应的用户信息")
def whoami(current_user: User = Depends(get_current_user)):
    """
    调试用接口：确认当前 Token 解析出的用户身份
    """
    return {
        "id":       current_user.id,
        "username": current_user.username,
        "role":     current_user.role.value,
        "sub_role": current_user.sub_role.value if current_user.sub_role else None,
    }


@app.get("/orders/{order_id}", tags=["订单管理"], summary="查询订单详情")
def get_order(
    order_id:     int,
    current_user: User = Depends(get_current_user),
):
    """
    权限说明：
    - merchant：可查任意订单
    - customer：只能查自己的订单
    - guest：返回 401
    """
    result = services.get_order(order_id, current_user)
    if not result["success"]:
        status = 401 if result.get("code") == "UNAUTHORIZED" else 403
        raise HTTPException(status_code=status, detail=result["message"])
    return result


@app.post("/orders/{order_id}/status", tags=["订单管理"], summary="修改订单状态")
def update_order_status(
    order_id:     int,
    body:         UpdateStatusRequest,
    current_user: User = Depends(get_current_user),
):
    """
    权限矩阵：
    - **merchant（任意职位）**：可改所有订单的任意合法状态
    - **customer**：只能取消自己名下的订单
    - **guest**：401 未登录

    状态机：待发货 → 已发货 / 已取消 | 已发货 → 已签收（终态不可再改）

    ### 测试场景
    - `Case 2`：用 `token-cs` 取消订单 1 → 应成功（客服可改单）
    - `Case 5`：用 `token-customer` 改他人订单 → 403 无权修改
    """
    result = services.update_order_status(order_id, body.new_status, current_user)
    if not result["success"]:
        code = result.get("code", "")
        status = 401 if code == "UNAUTHORIZED" else 422 if code == "INVALID_INPUT" else 403
        raise HTTPException(status_code=status, detail=result["message"])
    return result


@app.post("/products/{product_id}/price", tags=["商品管理"], summary="修改商品售价")
def modify_product_price(
    product_id:   int,
    body:         UpdatePriceRequest,
    current_user: User = Depends(get_current_user),
):
    """
    权限规则（双重校验）：
    - ① `role` 必须是 `merchant`
    - ② `sub_role` 必须是 `manager` 或 `operator`（客服 cs 也不行）

    ### 测试场景（任务 2.3）
    | Token            | 角色       | 预期结果 |
    |-----------------|-----------|---------|
    | `token-customer` | 买家猫     | 403 权限拒绝 |
    | `token-cs`       | 客服汪     | 403 职位不足 |
    | `token-manager`  | 店长狮     | 200 成功 |
    """
    result = services.modify_product_price(product_id, body.new_price, current_user)
    if not result["success"]:
        code = result.get("code", "")
        status = 422 if code == "INVALID_INPUT" else 403
        raise HTTPException(status_code=status, detail=result["message"])
    return result
