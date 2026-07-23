#!/usr/bin/env python3
"""
Holographic 语义搜索 — 查询历史对话
用法: python3 search.py "<查询语句>" [top_k=5]
"""
import sys
import yaml
from pathlib import Path
from qdrant_client import QdrantClient
from openai import OpenAI

QDRANT_PATH = Path.home() / "Documents" / "knowledge-system" / "holographic" / "qdrant_data"
COLLECTION = "holographic_conversations"
EMBEDDING_MODEL = "text-embedding-v3"


def search(query: str, top_k: int = 5):
    # API key
    config = yaml.safe_load(open(Path.home() / ".hermes" / "config.yaml"))
    api_key = config["auxiliary"]["vision"]["api_key"]

    # Embedding
    client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=[query])

    # Qdrant 搜索
    qdrant = QdrantClient(path=str(QDRANT_PATH))
    results = qdrant.query_points(
        collection_name=COLLECTION,
        query=resp.data[0].embedding,
        limit=top_k,
    )

    # 格式化输出
    print(f"🔍 '{query}' — {len(results.points)} 条结果")
    print("=" * 60)
    for i, hit in enumerate(results.points):
        p = hit.payload
        start = p.get("timestamp_start", 0)
        from datetime import datetime

        ts = datetime.fromtimestamp(start).strftime("%m-%d %H:%M")
        print(f"\n#{i+1} [score={hit.score:.3f}] {p['session_title']} ({ts})")
        print(f"    Chunk {p.get('chunk_idx', 0)+1}/{p.get('chunk_count', 1)}")
        # 展示完整文本预览
        preview = p.get("text_preview", "")
        for line in preview.split("\n")[:10]:
            if line.strip():
                print(f"    {line[:120]}")
    print()


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "知识库"
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    search(query, top_k)
