#!/usr/bin/env python3
"""
Holographic Session Archiver
从 Hermes state.db 增量读取对话 → chunk → embedding → Qdrant
"""

import sqlite3
import json
import os
import sys
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

# ─── 路径配置 ─────────────────────────────────────────────────
HERMES_HOME = Path.home() / ".hermes"
STATE_DB = HERMES_HOME / "state.db"
CONFIG_YAML = HERMES_HOME / "config.yaml"
KNOWLEDGE_SYSTEM = Path.home() / "Documents" / "knowledge-system"
HOLOGRAPHIC_DIR = KNOWLEDGE_SYSTEM / "holographic"
CONVERSATIONS_DIR = HOLOGRAPHIC_DIR / "conversations"
QDRANT_PATH = HOLOGRAPHIC_DIR / "qdrant_data"
STATE_FILE = HOLOGRAPHIC_DIR / "archive_state.json"

COLLECTION_NAME = "holographic_conversations"
EMBEDDING_MODEL = "text-embedding-v3"
EMBEDDING_DIM = 1024
CHUNK_TURNS = 5          # 每段对话包含的轮次数
BATCH_SIZE = 10           # DashScope embedding batch 上限

# ─── 工具函数 ─────────────────────────────────────────────────

def load_config():
    """从 Hermes config.yaml 读取 DashScope API key"""
    try:
        import yaml
        with open(CONFIG_YAML) as f:
            config = yaml.safe_load(f)
        key = config.get("auxiliary", {}).get("vision", {}).get("api_key", "")
        if key:
            os.environ["DASHSCOPE_API_KEY"] = key
            return key
    except Exception:
        pass
    # 从 .env 文件读取
    env_file = HERMES_HOME / ".env"
    if env_file.exists():
        for line in env_file.read_text().split("\n"):
            if "DASHSCOPE_API_KEY" in line and "=" in line:
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    os.environ["DASHSCOPE_API_KEY"] = key
                    return key
    # fallback: 直接读环境变量
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not key:
        print("ERROR: 未找到 DASHSCOPE_API_KEY (检查 ~/.hermes/config.yaml 或环境变量)")
        sys.exit(1)
    return key


def load_archive_state():
    """读取上次归档的时间戳"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_archive_timestamp": 0}


def save_archive_state(state):
    """保存归档状态"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_sessions_since(last_timestamp):
    """获取上次归档后的新 session"""
    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row
    sessions = conn.execute(
        "SELECT id, title, started_at, ended_at, message_count "
        "FROM sessions "
        "WHERE started_at > ? AND archived = 0 "
        "ORDER BY started_at",
        (last_timestamp,),
    ).fetchall()
    conn.close()
    return sessions


def get_messages_for_session(session_id, last_timestamp):
    """获取 session 的新消息 (过滤掉 tool 输出以减少噪音)"""
    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row
    messages = conn.execute(
        "SELECT id, role, content, timestamp "
        "FROM messages "
        "WHERE session_id = ? AND timestamp > ? AND active = 1 "
        "AND role IN ('user', 'assistant') "  # 只取用户和助手消息
        "ORDER BY timestamp",
        (session_id, last_timestamp),
    ).fetchall()
    conn.close()
    return messages


def chunk_messages(messages):
    """将消息按轮次分块 (每 CHUNK_TURNS 个 user+assistant 对为一组)"""
    chunks = []
    current_chunk = []
    turn_count = 0

    for msg in messages:
        current_chunk.append(msg)
        if msg["role"] == "assistant":
            turn_count += 1
            if turn_count >= CHUNK_TURNS:
                chunks.append(current_chunk)
                current_chunk = []
                turn_count = 0

    # 剩余不足一组的也打包
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def chunk_to_text(chunk):
    """将消息块转为纯文本 (用于 embedding)"""
    lines = []
    for msg in chunk:
        role_label = "用户" if msg["role"] == "user" else "助手"
        content = msg["content"] or ""
        # 截断过长内容
        if len(content) > 2000:
            content = content[:2000] + "…"
        lines.append(f"[{role_label}] {content}")
    return "\n".join(lines)


def get_embeddings(texts):
    """调用 DashScope embedding API (兼容 OpenAI SDK)"""
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["DASHSCOPE_API_KEY"],
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        resp = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch,  # DashScope: 直接传字符串列表
        )
        all_embeddings.extend([d.embedding for d in resp.data])
    return all_embeddings


def init_qdrant():
    """初始化 Qdrant 本地存储"""
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(QDRANT_PATH))

    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        print(f"[Qdrant] 创建 collection: {COLLECTION_NAME}")

    return client


def upsert_chunks(client, session_id, session_title, chunks, chunk_texts, embeddings):
    """将 embedding 写入 Qdrant"""
    from qdrant_client.models import PointStruct
    import uuid

    points = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_id = str(uuid.uuid4())
        first_ts = chunk[0]["timestamp"]
        last_ts = chunk[-1]["timestamp"]
        first_id = chunk[0]["id"]
        last_id = chunk[-1]["id"]

        points.append(
            PointStruct(
                id=chunk_id,
                vector=embedding,
                payload={
                    "session_id": session_id,
                    "session_title": session_title or "(无标题)",
                    "chunk_idx": i,
                    "chunk_count": len(chunks),
                    "message_ids": f"{first_id}-{last_id}",
                    "timestamp_start": first_ts,
                    "timestamp_end": last_ts,
                    "date": datetime.fromtimestamp(first_ts).strftime("%Y-%m-%d"),
                    "text_preview": chunk_texts[i][:300],
                    "turn_count": len([m for m in chunk if m["role"] == "assistant"]),
                },
            )
        )

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    return points


def save_conversation_json(session_id, session_title, messages, started_at):
    """将会话保存为 JSON 归档"""
    date_str = datetime.fromtimestamp(started_at).strftime("%Y-%m-%d")
    filename = f"{date_str}_{session_id[:8]}.json"
    filepath = CONVERSATIONS_DIR / filename

    data = {
        "session_id": session_id,
        "title": session_title,
        "started_at": started_at,
        "message_count": len(messages),
        "archived_at": datetime.now().isoformat(),
        "messages": [
            {
                "role": m["role"],
                "content": m["content"],
                "timestamp": m["timestamp"],
            }
            for m in messages
        ],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return filepath


# ─── 主流程 ───────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("Holographic Session Archiver")
    print("=" * 50)

    # 1. 初始化
    load_config()
    state = load_archive_state()
    last_ts = state.get("last_archive_timestamp", 0)
    print(f"上次归档时间: {datetime.fromtimestamp(last_ts) if last_ts else '从未'}")

    # 2. 获取新 sessions
    sessions = get_sessions_since(last_ts)
    if not sessions:
        print("没有新的对话需要归档。")
        return

    print(f"发现 {len(sessions)} 个新会话")

    # 3. 初始化 Qdrant
    qdrant = init_qdrant()

    # 4. 逐个 session 处理
    total_chunks = 0
    max_timestamp = last_ts

    for session in sessions:
        sid = session["id"]
        title = session["title"] or "(无标题)"
        msg_count = session["message_count"]
        started_at = session["started_at"]

        print(f"\n  📝 {title} ({sid[:8]}…) — {msg_count} 条消息")

        messages = get_messages_for_session(sid, last_ts)
        if not messages:
            print("    → 无新消息，跳过")
            continue

        chunks = chunk_messages(messages)
        if not chunks:
            print("    → 无可用块，跳过")
            continue

        # 生成 embedding
        chunk_texts = [chunk_to_text(c) for c in chunks]
        print(f"    → {len(chunks)} 个块，生成 embedding…")

        embeddings = get_embeddings(chunk_texts)

        # 写入 Qdrant
        points = upsert_chunks(qdrant, sid, title, chunks, chunk_texts, embeddings)
        print(f"    → 已写入 {len(points)} 个向量")

        # 保存 JSON 归档
        json_path = save_conversation_json(sid, title, messages, started_at)
        print(f"    → 已归档: {json_path.name}")

        total_chunks += len(chunks)

        # 更新最大时间戳
        session_max = max(m["timestamp"] for m in messages)
        if session_max > max_timestamp:
            max_timestamp = session_max

    # 5. 更新状态
    state["last_archive_timestamp"] = max_timestamp
    save_archive_state(state)
    print(f"\n✅ 完成: {len(sessions)} 个会话, {total_chunks} 个向量块")
    print(f"   下次从 {datetime.fromtimestamp(max_timestamp)} 开始")


if __name__ == "__main__":
    import yaml  # noqa: F811
    main()
