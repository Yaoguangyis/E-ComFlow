"""
backend/scripts/ingest.py
==========================
知识库向量化灌入脚本

设计要点：
  1. 用文件名判断敏感度，打上 access_level metadata
  2. public     → 所有角色可检索
  3. merchant_only → 仅 merchant 角色可检索
  4. 灌入完成后自动跑验证测试（无过滤 vs public 过滤）

运行方式（从 backend/ 目录执行）：
    python scripts/ingest.py

依赖：
    pip install langchain langchain-community chromadb sentence-transformers
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path

# ──────────────────────────────────────────────────────────────
# 路径常量
# ──────────────────────────────────────────────────────────────

BACKEND_DIR   = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = BACKEND_DIR / "knowledge"
CHROMA_DIR    = BACKEND_DIR / "chroma_db"
COLLECTION    = "sentinel_knowledge"

# ──────────────────────────────────────────────────────────────
# 文件 → access_level 映射表
# 新增文档时只需在这里登记，其余代码不变
# ──────────────────────────────────────────────────────────────

ACCESS_CONFIG: dict[str, dict] = {
    "public_faq.md": {
        "access_level": "public",
        "source_label": "退换货公共规则 FAQ",
        "dept":         "客服",
    },
    "internal_guide.md": {
        "access_level": "merchant_only",
        "source_label": "内部商家指南（含进货底价表）",
        "dept":         "运营/管理",
    },
}


# ──────────────────────────────────────────────────────────────
# Step 1：加载 & 切片
# ──────────────────────────────────────────────────────────────

def load_and_split() -> list:
    from langchain_community.document_loaders import TextLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,          # 每片约 400 字符，覆盖一个完整政策段落
        chunk_overlap=60,        # 60 字重叠，防止语义被截断在边界
        separators=["\n\n", "\n", "。", "，", " "],
    )

    all_docs = []

    for filename, meta in ACCESS_CONFIG.items():
        filepath = KNOWLEDGE_DIR / filename
        if not filepath.exists():
            print(f"  ⚠️  跳过（文件不存在）: {filepath}")
            continue

        level = meta["access_level"]
        print(f"  📄 加载 [{level:15s}] {filename}")

        loader = TextLoader(str(filepath), encoding="utf-8")
        raw = loader.load()
        chunks = splitter.split_documents(raw)

        for chunk in chunks:
            # 注入核心 metadata —— Chroma 过滤时依赖这些字段
            chunk.metadata.update({
                "access_level": meta["access_level"],
                "source_label": meta["source_label"],
                "dept":         meta["dept"],
                "filename":     filename,
            })

        print(f"     └─ 切分为 {len(chunks)} 个 chunk")
        all_docs.extend(chunks)

    return all_docs


# ──────────────────────────────────────────────────────────────
# Step 2：向量化 & 存库
# ──────────────────────────────────────────────────────────────

def build_vectorstore(docs: list):
    """
    Embedding 选用 paraphrase-multilingual-MiniLM-L12-v2：
    - 完全本地运行，无需 API Key
    - 支持中英文双语，中文语义检索效果良好
    - 模型体积约 500MB，首次运行自动下载
    """
    from langchain_community.vectorstores import Chroma
    from langchain_community.embeddings import HuggingFaceEmbeddings

    print("\n🔢 初始化 Embedding 模型（首次运行约需 2-5 分钟下载）...")
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📦 写入 ChromaDB → {CHROMA_DIR}")

    vs = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR),
        collection_name=COLLECTION,
    )
    # 兼容旧版 Chroma（新版自动持久化）
    if hasattr(vs, "persist"):
        vs.persist()

    return vs


# ──────────────────────────────────────────────────────────────
# Step 3：验证检索与权限过滤
# ──────────────────────────────────────────────────────────────

def verify(vs) -> None:
    """
    用三个场景验证：
      A. 买家问退货政策 → 无过滤，应命中 public_faq.md
      B. 买家问底价    → public 过滤，不应命中 internal_guide.md
      C. 店长问底价    → 无过滤，应命中 internal_guide.md
    """
    cases = [
        {
            "tag":    "A  买家/公开检索",
            "query":  "内衣可以退货吗",
            "filter": {"access_level": "public"},
            "expect": "应命中 public_faq.md，找到内衣退货规则",
        },
        {
            "tag":    "B  买家询问底价（过滤拦截）",
            "query":  "蓝牙耳机的进货底价是多少",
            "filter": {"access_level": "public"},
            "expect": "因 public 过滤，不应命中 internal_guide.md",
        },
        {
            "tag":    "C  店长查看底价（无过滤）",
            "query":  "蓝牙耳机的进货底价是多少",
            "filter": None,
            "expect": "应命中 internal_guide.md，找到底价表",
        },
    ]

    print("\n" + "─" * 58)
    print("🧪 检索验证")
    print("─" * 58)

    for c in cases:
        print(f"\n[{c['tag']}]")
        print(f"  问：{c['query']}")
        print(f"  预期：{c['expect']}")

        kwargs = {"k": 2}
        if c["filter"]:
            kwargs["filter"] = c["filter"]

        results = vs.similarity_search(c["query"], **kwargs)

        if not results:
            print("  → 无结果（过滤生效 ✅）")
        else:
            for r in results:
                fn = r.metadata.get("filename", "?")
                lv = r.metadata.get("access_level", "?")
                sl = r.metadata.get("source_label", "?")
                preview = r.page_content[:70].replace("\n", " ").strip()
                print(f"  → [{fn} | {lv}]")
                print(f"     来源：{sl}")
                print(f"     内容：{preview}...")


# ──────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 58)
    print("  Sentinel 知识库向量化灌入脚本")
    print("=" * 58)

    if not KNOWLEDGE_DIR.exists():
        print(f"❌ 找不到 knowledge/ 目录：{KNOWLEDGE_DIR}")
        sys.exit(1)

    print("\n📂 扫描知识库文件...\n")
    docs = load_and_split()

    if not docs:
        print("❌ 没有可灌入的文档")
        sys.exit(1)

    print(f"\n✅ 共 {len(docs)} 个 chunk，开始向量化...")
    vs = build_vectorstore(docs)

    verify(vs)

    print("\n" + "=" * 58)
    print("🎉 灌入完成！")
    print(f"   向量库路径：{CHROMA_DIR}")
    print("   下一步：运行 uvicorn app.main:app --reload")
    print("=" * 58)


if __name__ == "__main__":
    main()
