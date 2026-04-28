# Sentinel E-Com Agent — 任务一 & 任务二完成说明

## 最终目录结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── models.py       ← 任务 1.1：三张核心表
│   ├── services.py     ← 任务 2.1 + 2.2：权限感知业务函数
│   └── main.py         ← 任务 2.3：FastAPI + Swagger 测试入口
├── knowledge/
│   ├── public_faq.md        ← access_level: public
│   └── internal_guide.md    ← access_level: merchant_only（含底价表）
├── scripts/
│   ├── init_db.py      ← 任务 1.2：建表 + 三个测试角色种子数据
│   └── ingest.py       ← 任务 1.3：向量化灌入 + 权限 metadata
├── chroma_db/          ← ingest.py 运行后自动生成
└── requirements.txt
```

---

## 逐步运行指南

### 第一步：安装依赖

```bash
cd backend/
pip install -r requirements.txt
```

### 第二步：初始化数据库（任务 1.1 + 1.2）

```bash
python scripts/init_db.py
```

期望输出：
```
✅ 建表完成

👤 写入测试用户：
   ✚ 插入: 店长狮     role=merchant    sub_role=manager   id=1
   ✚ 插入: 客服汪     role=merchant    sub_role=cs        id=2
   ✚ 插入: 买家猫     role=customer    sub_role=None      id=3

📦 写入测试商品：
   ✚ 插入: 蓝牙耳机 Pro         售价=  299.0  底价= 89.0  id=1
   ✚ 插入: 纯棉内裤三件组       售价=   79.0  底价= 22.0  id=2

📋 写入测试订单：
   ✚ 插入: 买家猫的订单  商品=蓝牙耳机 Pro  状态=待发货  id=1
```

### 第三步：灌入向量知识库（任务 1.3）

```bash
python scripts/ingest.py
```

期望输出关键部分：
```
[A  买家/公开检索]
  → [public_faq.md | public] 内衣、内裤、泳衣、袜子...

[B  买家询问底价（过滤拦截）]
  → 无结果（过滤生效 ✅）

[C  店长查看底价（无过滤）]
  → [internal_guide.md | merchant_only] 蓝牙耳机 Pro...
```

### 第四步：启动 API 服务（任务 2.3）

```bash
uvicorn app.main:app --reload --port 8000
```

打开 http://localhost:8000/docs 进入 Swagger UI

---

## 任务 2.3：三个测试场景操作步骤

在 Swagger UI 的右上角 **Authorize** 按钮中填入 Bearer Token。

### Case 1：买家猫 尝试改价 → 403 权限拒绝

```
Authorization: Bearer token-customer
POST /products/1/price
Body: {"new_price": 199.0}

预期响应 403：
"权限不足：当前角色「customer」无改价权限，仅商家可操作"
```

### Case 2：客服汪 尝试改价 → 403 职位不足

```
Authorization: Bearer token-cs
POST /products/1/price
Body: {"new_price": 199.0}

预期响应 403：
"权限不足：职位「cs」无改价权限，请联系店长或运营（['manager', 'operator']）授权"
```

### Case 3：店长狮 改价 → 200 成功

```
Authorization: Bearer token-manager
POST /products/1/price
Body: {"new_price": 259.0}

预期响应 200：
{"success": true, "message": "商品「蓝牙耳机 Pro」售价已从 ¥299.0 更新为 ¥259.0"}
```

### Case 4：客服汪 取消买家订单 → 200 成功

```
Authorization: Bearer token-cs
POST /orders/1/status
Body: {"new_status": "已取消"}

预期响应 200：
{"success": true, "message": "订单 1 状态已更新为「已取消」"}
```

### Case 5：买家猫 查他人订单 → 403

```
Authorization: Bearer token-customer  (买家猫 id=3)
GET /orders/999  （不存在的订单，或者属于其他用户的订单 id）

预期响应 403：
"你无权查看他人订单"
```

---

## 核心设计决策（简历可用）

### 双层权限字段

```python
role     = "merchant"   # 大门：决定用户属于哪个阵营
sub_role = "cs"         # 内门：商家内部的职位精细化
```

这种设计让权限校验变成两次独立的 if 判断，逻辑清晰，
也方便后续 Supervisor Agent 在图节点里做拦截：
```
用户角色 → [大门校验] → [职位内门校验] → 执行 / 拒绝
```

### 状态机校验（防乱改）

`_VALID_TRANSITIONS` 字典显式定义每个状态的合法后继状态，
无论谁（包括 Agent）调用都不能绕过，形成不可逾越的业务边界。

### 脱敏在返回层做

数据库存原始号码 `13812345678`，
`_serialize_order()` 统一调用 `mask_phone()` 脱敏，
确保脱敏逻辑只有一处，不会被遗漏。

```python
re.sub(r"(\d{3})\d{4}(\d{4})", r"\1****\2", phone)
# 13812345678 → 138****5678
```

### RAG 权限在向量库层拦截

`ingest.py` 给每个 chunk 打上 `{"access_level": "public"}` 或
`{"access_level": "merchant_only"}`，
Agent 的 `knowledge_tool` 根据当前 `role` 自动注入过滤条件，
即使 Agent 被"欺骗"去查底价，向量库层面也会返回空结果。
