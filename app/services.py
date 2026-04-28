"""
backend/app/services.py
========================
权限感知型业务函数层

这里的函数是 Agent "手"的前身：
  - 每个函数都接收 current_user 并在内部做权限校验
  - 校验逻辑独立于 Agent，直接在业务层拦截，形成双重防线
  - 返回统一的 dict 结构，方便 @tool 包装后 Agent 解析

手机号脱敏：返回前用正则把中间 4 位替换为 ****
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.models import (
    Order, OrderStatus,
    Product,
    User, UserRole, SubRole,
    engine,
)


# ──────────────────────────────────────────────────────────────
# 通用工具
# ──────────────────────────────────────────────────────────────

def mask_phone(phone: str | None) -> str:
    """
    手机号脱敏：13812345678 → 138****5678
    正则：捕获前3位和后4位，中间换成 ****
    """
    if not phone:
        return ""
    return re.sub(r"(\d{3})\d{4}(\d{4})", r"\1****\2", phone)


def _ok(data: Any, msg: str = "操作成功") -> dict:
    return {"success": True, "message": msg, "data": data}


def _err(msg: str, code: str = "FORBIDDEN") -> dict:
    return {"success": False, "message": msg, "code": code}


def _serialize_order(order: Order, mask: bool = True) -> dict:
    """把 ORM 对象转为可序列化 dict，顺便做脱敏"""
    return {
        "id":          order.id,
        "status":      order.status.value,
        "amount":      order.amount,
        "total_price": order.total_price,
        "buyer_phone": mask_phone(order.buyer_phone) if mask else order.buyer_phone,
        "created_at":  str(order.created_at),
        "updated_at":  str(order.updated_at),
    }


# ──────────────────────────────────────────────────────────────
# 任务 2.1：update_order_status
# ──────────────────────────────────────────────────────────────

# 合法的状态转移表（防止乱改状态机）
_VALID_TRANSITIONS: dict[OrderStatus, list[OrderStatus]] = {
    OrderStatus.PENDING:   [OrderStatus.SHIPPED,   OrderStatus.CANCELLED],
    OrderStatus.SHIPPED:   [OrderStatus.DELIVERED],
    OrderStatus.DELIVERED: [],            # 终态，不可再改
    OrderStatus.CANCELLED: [],            # 终态，不可再改
}

# 买家只能做这一个操作
_CUSTOMER_ALLOWED_STATUS = [OrderStatus.CANCELLED]


def update_order_status(
    order_id:    int,
    new_status:  str,
    current_user: User,
) -> dict:
    """
    修改订单状态。

    权限矩阵：
      merchant（任意 sub_role）→ 可修改所有订单，所有合法状态转移
      customer                  → 只能取消自己名下的订单
      guest                     → 拒绝，提示登录

    状态机校验：
      无论哪个角色，都不允许非法的状态跳转（如：已取消 → 已发货）

    脱敏：
      返回订单时，buyer_phone 中间 4 位替换为 ****
    """
    # ── 1. 解析目标状态 ──────────────────────────────────────
    try:
        target = OrderStatus(new_status)
    except ValueError:
        valid_vals = [s.value for s in OrderStatus]
        return _err(f"无效状态值「{new_status}」，合法值：{valid_vals}", "INVALID_INPUT")

    # ── 2. 游客拦截 ──────────────────────────────────────────
    if current_user.role == UserRole.GUEST:
        return _err("请先登录后再操作", "UNAUTHORIZED")

    with Session(engine) as session:
        order = session.get(Order, order_id)

        # ── 3. 订单存在性检查 ────────────────────────────────
        if not order:
            return _err(f"订单 {order_id} 不存在", "NOT_FOUND")

        # ── 4. 买家权限校验 ──────────────────────────────────
        if current_user.role == UserRole.CUSTOMER:
            # 4a. 归属校验：只能动自己的单
            if order.user_id != current_user.id:
                return _err("你无权修改他人订单", "FORBIDDEN")
            # 4b. 操作类型校验：只能取消
            if target not in _CUSTOMER_ALLOWED_STATUS:
                allowed = [s.value for s in _CUSTOMER_ALLOWED_STATUS]
                return _err(
                    f"买家只能将订单改为：{allowed}，无权执行「{new_status}」",
                    "FORBIDDEN",
                )

        # ── 5. 状态机合法性校验（商家也要遵守）──────────────
        allowed_next = _VALID_TRANSITIONS.get(order.status, [])
        if target not in allowed_next:
            current_val = order.status.value
            allowed_vals = [s.value for s in allowed_next] or ["无（终态）"]
            return _err(
                f"订单当前状态「{current_val}」不可转移到「{new_status}」，"
                f"可选操作：{allowed_vals}",
                "INVALID_TRANSITION",
            )

        # ── 6. 执行更新 ──────────────────────────────────────
        order.status     = target
        order.updated_at = datetime.utcnow()
        session.add(order)
        session.commit()
        session.refresh(order)

        return _ok(
            _serialize_order(order),
            f"订单 {order_id} 状态已更新为「{target.value}」",
        )


# ──────────────────────────────────────────────────────────────
# 任务 2.2：modify_product_price
# ──────────────────────────────────────────────────────────────

# 允许改价的 sub_role 白名单
_PRICE_ALLOWED_SUB_ROLES = {SubRole.MANAGER, SubRole.OPERATOR}


def modify_product_price(
    product_id:   int,
    new_price:    float,
    current_user: User,
) -> dict:
    """
    修改商品售价。

    权限规则（严格）：
      必须同时满足：
        ① role == merchant
        ② sub_role in [manager, operator]
      客服（cs）、买家、游客 → 一律拒绝

    业务校验：
      新价格必须 > 0，且不低于进货底价（防止亏本卖）
    """
    # ── 1. 角色大门：必须是商家 ──────────────────────────────
    if current_user.role != UserRole.MERCHANT:
        role_label = current_user.role.value
        return _err(
            f"权限不足：当前角色「{role_label}」无改价权限，仅商家可操作",
            "FORBIDDEN",
        )

    # ── 2. 职位内门：cs 也不行 ────────────────────────────────
    if current_user.sub_role not in _PRICE_ALLOWED_SUB_ROLES:
        sub_label = current_user.sub_role.value if current_user.sub_role else "无"
        allowed   = [r.value for r in _PRICE_ALLOWED_SUB_ROLES]
        return _err(
            f"权限不足：职位「{sub_label}」无改价权限，"
            f"请联系店长或运营（{allowed}）授权",
            "FORBIDDEN",
        )

    # ── 3. 价格合法性 ──────────────────────────────────────
    if new_price <= 0:
        return _err("价格必须大于 0", "INVALID_INPUT")

    with Session(engine) as session:
        product = session.get(Product, product_id)

        if not product:
            return _err(f"商品 {product_id} 不存在", "NOT_FOUND")

        # ── 4. 不能低于进货底价（防止亏本） ──────────────────
        if new_price < product.cost_price:
            return _err(
                f"新售价 ¥{new_price} 低于进货底价 ¥{product.cost_price}，"
                "修改被拒绝（请联系店长审批）",
                "PRICE_BELOW_COST",
            )

        old_price        = product.price
        product.price    = new_price
        session.add(product)
        session.commit()
        session.refresh(product)

        return _ok(
            {
                "product_id":   product.id,
                "product_name": product.name,
                "old_price":    old_price,
                "new_price":    product.price,
            },
            f"商品「{product.name}」售价已从 ¥{old_price} 更新为 ¥{new_price}",
        )


# ──────────────────────────────────────────────────────────────
# 查询类辅助函数（Agent Tools 后续会用）
# ──────────────────────────────────────────────────────────────

def get_order(order_id: int, current_user: User) -> dict:
    """
    查询单个订单详情。
    - merchant：可查所有订单
    - customer：只能查自己的
    - guest：拒绝
    """
    if current_user.role == UserRole.GUEST:
        return _err("请先登录", "UNAUTHORIZED")

    with Session(engine) as session:
        order = session.get(Order, order_id)
        if not order:
            return _err(f"订单 {order_id} 不存在", "NOT_FOUND")

        if current_user.role == UserRole.CUSTOMER and order.user_id != current_user.id:
            return _err("你无权查看他人订单", "FORBIDDEN")

        return _ok(_serialize_order(order))


def list_orders_by_user(user_id: int, current_user: User) -> dict:
    """列出某用户的所有订单（买家只能查自己的）"""
    if current_user.role == UserRole.GUEST:
        return _err("请先登录", "UNAUTHORIZED")
    if current_user.role == UserRole.CUSTOMER and current_user.id != user_id:
        return _err("你无权查看他人订单列表", "FORBIDDEN")

    with Session(engine) as session:
        orders = session.exec(select(Order).where(Order.user_id == user_id)).all()
        return _ok([_serialize_order(o) for o in orders])
