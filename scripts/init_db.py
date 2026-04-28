"""
backend/scripts/init_db.py
===========================
初始化数据库：建表 + 插入三个典型测试角色 + 示例商品/订单

运行方式（从 backend/ 目录）：
    python scripts/init_db.py

三个测试角色：
    ① 店长狮 lion_manager  — merchant / manager  （最高权限）
    ② 客服汪 wang_cs       — merchant / cs       （改单不能改价）
    ③ 买家猫 mao_customer  — customer / None     （只看/取消自己的单）
"""

import sys
import os

# 把 backend/ 加入 sys.path，让 `from app.models import ...` 可以找到
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import Session, select
from app.models import (
    User, Product, Order,
    UserRole, SubRole, OrderStatus,
    create_tables, engine,
)


# ──────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────

def _exists(session: Session, model, **kwargs) -> bool:
    """通用：判断记录是否已存在，防止重复插入"""
    stmt = select(model)
    for k, v in kwargs.items():
        stmt = stmt.where(getattr(model, k) == v)
    return session.exec(stmt).first() is not None


# ──────────────────────────────────────────────────────────────
# 种子数据定义
# ──────────────────────────────────────────────────────────────

SEED_USERS = [
    {
        "username": "lion_manager",
        "role":     UserRole.MERCHANT,
        "sub_role": SubRole.MANAGER,
        "label":    "店长狮",
    },
    {
        "username": "wang_cs",
        "role":     UserRole.MERCHANT,
        "sub_role": SubRole.CS,
        "label":    "客服汪",
    },
    {
        "username": "mao_customer",
        "role":     UserRole.CUSTOMER,
        "sub_role": None,
        "label":    "买家猫",
    },
]

SEED_PRODUCTS = [
    {
        "name":       "蓝牙耳机 Pro",
        "price":      299.0,
        "cost_price": 89.0,   # 敏感字段：只有 manager/operator 能看
        "stock":      50,
        "category":   "电子产品",
    },
    {
        "name":       "纯棉内裤三件组",
        "price":      79.0,
        "cost_price": 22.0,
        "stock":      200,
        "category":   "内衣",   # 命中"内衣不退货"规则
    },
]


# ──────────────────────────────────────────────────────────────
# 主逻辑
# ──────────────────────────────────────────────────────────────

def seed() -> None:
    create_tables()
    print("✅ 建表完成\n")

    with Session(engine) as session:

        # ── 插入用户 ──────────────────────────────────────────
        print("👤 写入测试用户：")
        inserted_users: dict[str, User] = {}

        for ud in SEED_USERS:
            if _exists(session, User, username=ud["username"]):
                u = session.exec(
                    select(User).where(User.username == ud["username"])
                ).one()
                print(f"   跳过（已存在）: {ud['label']}  [{ud['username']}]")
            else:
                u = User(
                    username=ud["username"],
                    role=ud["role"],
                    sub_role=ud["sub_role"],
                )
                session.add(u)
                session.commit()
                session.refresh(u)
                print(
                    f"   ✚ 插入: {ud['label']:8s} "
                    f"role={u.role.value:10s} "
                    f"sub_role={u.sub_role.value if u.sub_role else 'None':10s} "
                    f"id={u.id}"
                )
            inserted_users[ud["username"]] = u

        # ── 插入商品 ──────────────────────────────────────────
        print("\n📦 写入测试商品：")
        inserted_products: dict[str, Product] = {}

        for pd in SEED_PRODUCTS:
            if _exists(session, Product, name=pd["name"]):
                p = session.exec(
                    select(Product).where(Product.name == pd["name"])
                ).one()
                print(f"   跳过（已存在）: {pd['name']}")
            else:
                p = Product(**pd)
                session.add(p)
                session.commit()
                session.refresh(p)
                print(
                    f"   ✚ 插入: {p.name:20s} "
                    f"售价={p.price:>7.1f}  "
                    f"底价={p.cost_price:>6.1f}  "
                    f"id={p.id}"
                )
            inserted_products[pd["name"]] = p

        # ── 插入订单（买家猫 → 蓝牙耳机）──────────────────────
        print("\n📋 写入测试订单：")
        buyer = inserted_users["mao_customer"]
        product = inserted_products["蓝牙耳机 Pro"]

        if not _exists(session, Order, user_id=buyer.id, product_id=product.id):
            order = Order(
                user_id=buyer.id,
                product_id=product.id,
                amount=1,
                total_price=product.price,
                status=OrderStatus.PENDING,
                buyer_phone="13812345678",   # 原始号码，返回前脱敏
            )
            session.add(order)
            session.commit()
            session.refresh(order)
            print(
                f"   ✚ 插入: 买家猫的订单  "
                f"商品={product.name}  "
                f"状态={order.status.value}  "
                f"id={order.id}"
            )
        else:
            print("   跳过（已存在）: 买家猫的订单")

    # ── 汇总 ─────────────────────────────────────────────────
    print("\n" + "─" * 55)
    print("🎉 数据库初始化完成！可用以下账号测试权限：")
    print()
    print("  角色        username         role       sub_role")
    print("  ──────────────────────────────────────────────")
    print("  店长狮      lion_manager     merchant   manager")
    print("  客服汪      wang_cs          merchant   cs")
    print("  买家猫      mao_customer     customer   None")
    print()
    print("  数据库文件：backend/sentinel.db")
    print("  可用 DB Browser for SQLite 直接打开查看")
    print("─" * 55)


if __name__ == "__main__":
    seed()
