"""
backend/app/models.py
=====================
三张核心表：User / Product / Order
核心设计：User 表的双层权限字段 (role + sub_role) 是后续
         Supervisor Agent 做权限拦截的物理依据。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel, create_engine, Session, select


# ──────────────────────────────────────────────────────────────
# 枚举：精确表达业务权限层级
# ──────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    """顶层身份：决定用户属于哪个大类"""
    MERCHANT = "merchant"   # 商家侧（含店长/运营/客服）
    CUSTOMER = "customer"   # 买家侧
    GUEST    = "guest"      # 未登录游客


class SubRole(str, Enum):
    """商家内部职位：细化权限粒度（仅 merchant 有值）"""
    MANAGER  = "manager"    # 店长：最高权限，可改价/看底价
    OPERATOR = "operator"   # 运营：可改价，不可看底价
    CS       = "cs"         # 客服：只能改单状态，不能改价


class OrderStatus(str, Enum):
    """订单状态机——状态转移规则在 services.py 里校验"""
    PENDING   = "待发货"
    SHIPPED   = "已发货"
    DELIVERED = "已签收"
    CANCELLED = "已取消"


# ──────────────────────────────────────────────────────────────
# User 表
# ──────────────────────────────────────────────────────────────

class User(SQLModel, table=True):
    """
    双层权限字段设计：
      role     = 大门（merchant / customer / guest）
      sub_role = 内门（仅 merchant 内部有，决定精细权限）

    例：客服汪 → role=merchant, sub_role=cs
        买家猫 → role=customer, sub_role=None
    """
    id:         Optional[int] = Field(default=None, primary_key=True)
    username:   str           = Field(unique=True, index=True, description="登录名/展示名")
    role:       UserRole      = Field(default=UserRole.GUEST, description="顶层身份")
    sub_role:   Optional[SubRole] = Field(
        default=None,
        description="商家内部职位，非商家为 null"
    )
    created_at: datetime      = Field(default_factory=datetime.utcnow)

    # 反向关联（查某用户的所有订单用）
    orders: list["Order"] = Relationship(back_populates="buyer")


# ──────────────────────────────────────────────────────────────
# Product 表
# ──────────────────────────────────────────────────────────────

class Product(SQLModel, table=True):
    """
    cost_price（进货底价）是敏感字段：
    - 仅 sub_role in [manager, operator] 可查
    - RAG 知识库的 internal_guide.md 同理
    """
    id:         Optional[int] = Field(default=None, primary_key=True)
    name:       str           = Field(index=True)
    price:      float         = Field(description="对外售价")
    cost_price: float         = Field(description="进货底价（敏感，不对 CS/买家暴露）")
    stock:      int           = Field(default=0)
    category:   str           = Field(default="通用", description="商品类目，用于退货规则匹配")

    orders: list["Order"] = Relationship(back_populates="product")


# ──────────────────────────────────────────────────────────────
# Order 表
# ──────────────────────────────────────────────────────────────

class Order(SQLModel, table=True):
    """
    user_id → 买家归属（services.py 里校验"自己只能改自己的单"）
    buyer_phone → 存原始号码，返回前在 services.py 做正则脱敏
    """
    id:           Optional[int]      = Field(default=None, primary_key=True)
    user_id:      int                = Field(foreign_key="user.id", description="买家 user.id")
    product_id:   int                = Field(foreign_key="product.id")
    amount:       int                = Field(default=1, description="购买数量")
    total_price:  float              = Field(description="成交总价")
    status:       OrderStatus        = Field(default=OrderStatus.PENDING)
    buyer_phone:  Optional[str]      = Field(default=None, description="买家手机号（原始，输出前脱敏）")
    created_at:   datetime           = Field(default_factory=datetime.utcnow)
    updated_at:   datetime           = Field(default_factory=datetime.utcnow)

    buyer:   Optional[User]    = Relationship(back_populates="orders")
    product: Optional[Product] = Relationship(back_populates="orders")


# ──────────────────────────────────────────────────────────────
# 数据库引擎（模块级单例）
# ──────────────────────────────────────────────────────────────

DATABASE_URL = "sqlite:///./sentinel.db"
engine = create_engine(DATABASE_URL, echo=False)


def create_tables() -> None:
    """建表（幂等：表已存在则跳过）"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI Depends 注入用"""
    with Session(engine) as session:
        yield session
