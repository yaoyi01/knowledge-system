#!/usr/bin/env python3
"""
LLM Wiki 对接 — 将提取的文本送入 Wiki raw/ 目录，标记可被 Agent 处理
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path.home() / "Documents" / "knowledge-system"
WIKI_DIR = BASE_DIR / "wiki"

sys.path.insert(0, str(BASE_DIR))
from cleaner.state import init_db, DB_PATH, upsert_metadata, log


def stage_for_wiki(file_hash: str, text_path: str, conn):
    """将文本复制到 wiki/raw/ 并标记"""
    text_file = Path(text_path)
    if not text_file.exists():
        return

    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = WIKI_DIR / "raw" / "articles"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 获取文件元数据
    row = conn.execute(
        "SELECT f.original_name, m.title FROM files f LEFT JOIN file_metadata m ON f.file_hash = m.file_hash WHERE f.file_hash = ?",
        (file_hash,),
    ).fetchone()
    title = (row[1] if row and row[1] else row[0] if row else text_file.stem)

    # 保存到 wiki/raw/
    raw_name = f"{datetime.now().strftime('%Y%m%d')}_{file_hash[:8]}_{title[:50]}.md"
    raw_path = raw_dir / raw_name

    text = text_file.read_text(encoding="utf-8")
    raw_md = f"""---
source_path: {text_path}
ingested: {datetime.now().isoformat()}
sha256: {file_hash}
file_type: text
---

{text}
"""
    raw_path.write_text(raw_md, encoding="utf-8")

    # 更新状态
    upsert_metadata(conn, file_hash, wiki_page_path=str(raw_path))
    conn.execute("UPDATE files SET status = 'ready_for_wiki' WHERE file_hash = ?", (file_hash,))
    log(conn, file_hash, "wiki", "staged", f"→ wiki/raw/{raw_name}")

    print(f"  ✓ Wiki raw: {raw_name}")


def main():
    init_db()
    conn = sqlite3.connect(str(DB_PATH))

    if len(sys.argv) < 2:
        # 处理所有 'processing' 状态的文件
        rows = conn.execute(
            "SELECT f.file_hash FROM files f WHERE f.status = 'processing'"
        ).fetchall()
        for (file_hash,) in rows:
            text_path = BASE_DIR / "processed" / "text" / f"{file_hash}.txt"
            stage_for_wiki(file_hash, str(text_path), conn)
        conn.commit()
    else:
        file_hash = sys.argv[1]
        text_path = BASE_DIR / "processed" / "text" / f"{file_hash}.txt"
        stage_for_wiki(file_hash, str(text_path), conn)
        conn.commit()

    conn.close()


if __name__ == "__main__":
    main()
