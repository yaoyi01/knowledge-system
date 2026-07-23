#!/usr/bin/env python3
"""
RAG 知识库语义搜索
用法: python3 rag_search.py "<查询>" [top_k]
"""
import sys
import yaml
from pathlib import Path
from qdrant_client import QdrantClient
from openai import OpenAI

QDRANT_PATH = Path.home() / "Documents" / "knowledge-system" / "rag" / "qdrant_data"
COLLECTION = "rag_knowledge"


def search(query: str, top_k: int = 5):
    config = yaml.safe_load(open(Path.home() / ".hermes" / "config.yaml"))
    api_key = config["auxiliary"]["vision"]["api_key"]
    client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    resp = client.embeddings.create(model="text-embedding-v3", input=[query])

    qdrant = QdrantClient(path=str(QDRANT_PATH))
    results = qdrant.query_points(
        collection_name=COLLECTION,
        query=resp.data[0].embedding,
        limit=top_k,
    )

    print(f"🔍 '{query}' — {len(results.points)} 条结果")
    print("=" * 60)
    for hit in results.points:
        p = hit.payload
        print(f"\n#{hit.score:.3f} [{p.get('file_type','?')}] {p.get('title','')[:60]}")
        print(f"    {p.get('text','')[:300]}")
        print()


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "测试"
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    search(query, top_k)
