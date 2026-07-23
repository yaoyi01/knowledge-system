#!/usr/bin/env python3
"""知识系统健康检查"""
import sys
from pathlib import Path

BASE = Path.home() / "Documents" / "knowledge-system"

def check(name, path, check_type="exists"):
    p = Path(path).expanduser() if isinstance(path, str) else path
    if check_type == "exists":
        ok = p.exists()
    elif check_type == "file":
        ok = p.is_file()
    elif check_type == "dir":
        ok = p.is_dir()
    print(f"  {'✅' if ok else '❌'} {name}: {p}")
    return ok

print("🔍 知识系统健康检查")
print("=" * 50)

# 目录结构
all_ok = True
all_ok &= check("知识系统根目录", BASE, "dir")
all_ok &= check("vault 归档", BASE / "vault", "dir")
all_ok &= check("processed 产物", BASE / "processed" / "text", "dir")
all_ok &= check("rag 向量库", BASE / "rag" / "qdrant_data", "dir")
all_ok &= check("wiki 知识库", BASE / "wiki" / "index.md", "file")
all_ok &= check("state.db", BASE / "state.db", "file")

# Qdrant
try:
    from qdrant_client import QdrantClient
    h = QdrantClient(path=str(BASE / "holographic" / "qdrant_data"))
    r = QdrantClient(path=str(BASE / "rag" / "qdrant_data"))
    hp, _ = h.scroll("holographic_conversations", limit=1)
    rp, _ = r.scroll("rag_knowledge", limit=1)
    print(f"  ✅ Holographic: {len(hp)}+ vectors")
    print(f"  ✅ RAG: {len(rp)}+ vectors")
except Exception as e:
    print(f"  ❌ Qdrant: {e}")
    all_ok = False

# state.db
import sqlite3
try:
    conn = sqlite3.connect(str(BASE / "state.db"))
    count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    print(f"  ✅ state.db: {count} 文件已索引")
    conn.close()
except Exception as e:
    print(f"  ❌ state.db: {e}")
    all_ok = False

# PageIndex
pi = BASE / "pageindex" / "index.db"
if pi.exists():
    conn = sqlite3.connect(str(pi))
    count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    print(f"  ✅ PageIndex: {count} 文件")
    conn.close()
else:
    print("  ❌ PageIndex: index.db 不存在")
    all_ok = False

# ffmpeg
import subprocess
try:
    r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
    print(f"  ✅ ffmpeg: {'可用' if r.returncode == 0 else '异常'}")
except Exception:
    print("  ❌ ffmpeg: 未安装")
    all_ok = False

# 配置
if (BASE / "config.yaml").exists():
    print("  ✅ config.yaml")
else:
    print("  ❌ config.yaml 缺失")
    all_ok = False

# Wiki
wiki_index = BASE / "wiki" / "index.md"
if wiki_index.exists():
    pages = [l for l in wiki_index.read_text().split("\n") if l.startswith("- [")]
    print(f"  ✅ Wiki: {len(pages)} 个知识页面")
else:
    print("  ❌ Wiki: index.md 不存在")
    all_ok = False

print()
if all_ok:
    print("🎉 全部正常")
else:
    print("⚠️ 有问题，请检查 ❌ 项")
