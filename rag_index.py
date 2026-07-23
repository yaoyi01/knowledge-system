#!/usr/bin/env python3
"""
RAG 向量索引器
读取 processed/text/ 下的文本 → chunk → DashScope embedding → Qdrant collection rag_knowledge
"""
import os
import re
import sys
import uuid
from pathlib import Path

BASE_DIR = Path.home() / "Documents" / "knowledge-system"
QDRANT_PATH = BASE_DIR / "rag" / "qdrant_data"
COLLECTION = "rag_knowledge"
EMBEDDING_MODEL = "text-embedding-v3"
BATCH_SIZE = 10
CHUNK_SIZE = 500   # 约 500 中文字
CHUNK_OVERLAP = 80

sys.path.insert(0, str(BASE_DIR))
from cleaner.state import init_db, DB_PATH, upsert_metadata, log
import sqlite3


def chunk_text(text: str) -> list[str]:
    """按段落+句子分割文本"""
    # 先按空行分段落
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) < CHUNK_SIZE:
            current += ("\n" + para) if current else para
        else:
            if current:
                chunks.append(current)
            current = para

    if current:
        chunks.append(current)

    # 对过长的 chunk 再按句号分割
    final = []
    for c in chunks:
        if len(c) <= CHUNK_SIZE * 1.5:
            final.append(c)
        else:
            sentences = re.split(r'[。！？\n]', c)
            sub = ""
            for s in sentences:
                s = s.strip()
                if not s:
                    continue
                if len(sub) + len(s) < CHUNK_SIZE:
                    sub += s + "。"
                else:
                    if sub:
                        final.append(sub)
                    sub = s + "。"
            if sub:
                final.append(sub)

    return final


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """DashScope embedding"""
    import yaml
    from openai import OpenAI

    try:
        config = yaml.safe_load(open(Path.home() / ".hermes" / "config.yaml"))
        api_key = config.get("auxiliary", {}).get("vision", {}).get("api_key", "")
    except Exception:
        api_key = ""
    # 从 .env 读取
    if not api_key:
        env_path = Path.home() / ".hermes" / ".env"
        if env_path.exists():
            for line in env_path.read_text().split("\n"):
                if "DASHSCOPE_API_KEY" in line and "=" in line:
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not api_key:
        print("  ⚠️ API Key 未配置，跳过 RAG 索引")
        return []

    client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

    embs = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        embs.extend([d.embedding for d in resp.data])
    return embs


def index_text(file_hash: str, text: str, meta: dict, conn) -> list[str]:
    """将文本向量化并存入 Qdrant"""
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct

    chunks = chunk_text(text)
    if not chunks:
        log(conn, file_hash, "rag", "skipped", "无有效 chunk")
        return []

    embeddings = get_embeddings(chunks)

    qdrant = QdrantClient(path=str(QDRANT_PATH))
    collections = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION not in collections:
        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )

    file_type = meta.get("file_type", "unknown")
    title = meta.get("title", "")

    points = []
    chunk_ids = []
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        cid = str(uuid.uuid4())
        chunk_ids.append(cid)
        points.append(PointStruct(
            id=cid,
            vector=emb,
            payload={
                "file_hash": file_hash,
                "file_type": file_type,
                "title": title,
                "chunk_idx": i,
                "chunk_count": len(chunks),
                "text": chunk[:2000],
            },
        ))

    qdrant.upsert(collection_name=COLLECTION, points=points)
    log(conn, file_hash, "rag", "indexed", f"{len(chunks)} chunks → Qdrant")
    return chunk_ids


# ─── CLI ────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        # 处理所有 'processing' 状态的文件
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute(
            "SELECT f.file_hash, f.file_type, f.vault_path, f.original_name FROM files f WHERE f.status = 'processing'"
        ).fetchall()
        if not rows:
            print("没有待处理的文件")
            conn.close()
            return

        for file_hash, file_type, vault_path, name in rows:
            text_path = BASE_DIR / "processed" / "text" / f"{file_hash}.txt"
            if not text_path.exists():
                print(f"  ⏭ {name}: 文本未提取")
                continue
            text = text_path.read_text(encoding="utf-8")
            meta = {"file_type": file_type, "title": name}
            print(f"  📝 {name} ({file_type}): {len(text)} chars")
            chunks = chunk_text(text)
            print(f"     → {len(chunks)} chunks, embedding...")
            ids = index_text(file_hash, text, meta, conn)
            conn.execute("UPDATE files SET status = 'indexed' WHERE file_hash = ?", (file_hash,))
            conn.commit()
            print(f"     ✅ {len(ids)} vectors in rag_knowledge")

        conn.close()
    else:
        # 指定文件
        file_hash = sys.argv[1]
        conn = sqlite3.connect(str(DB_PATH))
        text_path = BASE_DIR / "processed" / "text" / f"{file_hash}.txt"
        text = text_path.read_text(encoding="utf-8")
        meta = {"file_type": "text", "title": file_hash}
        ids = index_text(file_hash, text, meta, conn)
        conn.execute("UPDATE files SET status = 'indexed' WHERE file_hash = ?", (file_hash,))
        conn.commit()
        conn.close()
        print(f"✅ {len(ids)} chunks indexed")


if __name__ == "__main__":
    init_db()
    main()
