"""
数据清理器 — 处理状态数据库
负责 files/file_metadata/processing_log 三表的 CRUD
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path.home() / "Documents" / "knowledge-system"
DB_PATH = BASE_DIR / "state.db"

# ─── 初始化 ───────────────────────────────────────

def init_db():
    """创建数据库和表"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS files (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash       TEXT NOT NULL UNIQUE,
            original_path   TEXT NOT NULL,
            original_name   TEXT NOT NULL,
            file_type       TEXT NOT NULL,
            file_size       INTEGER NOT NULL,
            mime_type       TEXT,
            modified_at     TEXT,
            vault_path      TEXT,
            status          TEXT NOT NULL DEFAULT 'detected',
            error_message   TEXT,
            retry_count     INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS file_metadata (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash           TEXT NOT NULL UNIQUE REFERENCES files(file_hash),
            title               TEXT,
            author              TEXT,
            tags                TEXT,
            page_count          INTEGER,
            slide_count         INTEGER,
            sheet_count         INTEGER,
            duration_sec        REAL,
            resolution          TEXT,
            extracted_text_path TEXT,
            vision_result_path  TEXT,
            speech_result_path  TEXT,
            merged_text_path    TEXT,
            wiki_page_path      TEXT
        );

        CREATE TABLE IF NOT EXISTS processing_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash   TEXT NOT NULL REFERENCES files(file_hash),
            stage       TEXT NOT NULL,
            action      TEXT NOT NULL,
            detail      TEXT,
            duration_ms INTEGER,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
        CREATE INDEX IF NOT EXISTS idx_files_type ON files(file_type);
        CREATE INDEX IF NOT EXISTS idx_files_hash ON files(file_hash);
        CREATE INDEX IF NOT EXISTS idx_metadata_hash ON file_metadata(file_hash);
        CREATE INDEX IF NOT EXISTS idx_log_hash ON processing_log(file_hash);
    """)
    conn.commit()
    return conn

# ─── 文件记录 ─────────────────────────────────────

def file_exists(file_hash: str, conn=None) -> bool:
    """检查文件是否已处理"""
    close = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        close = True
    row = conn.execute("SELECT 1 FROM files WHERE file_hash = ?", (file_hash,)).fetchone()
    if close:
        conn.close()
    return row is not None

def insert_file(conn, file_hash, original_path, original_name, file_type, file_size, mime_type=None, modified_at=None, vault_path=None, status="validated"):
    """插入新文件记录"""
    conn.execute(
        "INSERT OR IGNORE INTO files (file_hash, original_path, original_name, file_type, file_size, mime_type, modified_at, vault_path, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (file_hash, str(original_path), original_name, file_type, file_size, mime_type, modified_at, str(vault_path) if vault_path else None, status),
    )

def update_status(conn, file_hash, status, error_message=None):
    """更新处理状态"""
    conn.execute(
        "UPDATE files SET status = ?, error_message = ?, updated_at = datetime('now') WHERE file_hash = ?",
        (status, error_message, file_hash),
    )

def get_files_by_status(conn, status, limit=100):
    """按状态查询文件"""
    return conn.execute(
        "SELECT * FROM files WHERE status = ? ORDER BY created_at LIMIT ?",
        (status, limit),
    ).fetchall()

# ─── 元数据 ───────────────────────────────────────

def upsert_metadata(conn, file_hash, **kwargs):
    """插入或更新元数据"""
    allowed = {"title", "author", "tags", "page_count", "slide_count", "sheet_count", "duration_sec", "resolution", "extracted_text_path", "vision_result_path", "speech_result_path", "merged_text_path", "wiki_page_path"}
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not fields:
        return
    if "tags" in fields and isinstance(fields["tags"], list):
        fields["tags"] = json.dumps(fields["tags"], ensure_ascii=False)
    columns = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + list(fields.values())  # INSERT 和 UPDATE 各用一次
    conn.execute(
        f"INSERT INTO file_metadata (file_hash, {', '.join(fields.keys())}) VALUES (?, {', '.join('?' * len(fields))}) ON CONFLICT(file_hash) DO UPDATE SET {columns}",
        [file_hash] + values,
    )

# ─── 日志 ─────────────────────────────────────────

def log(conn, file_hash, stage, action, detail=None, duration_ms=None):
    """记录处理日志"""
    conn.execute(
        "INSERT INTO processing_log (file_hash, stage, action, detail, duration_ms) VALUES (?, ?, ?, ?, ?)",
        (file_hash, stage, action, detail, duration_ms),
    )

# ─── 统计 ─────────────────────────────────────────

def stats(conn):
    """处理状态统计"""
    rows = conn.execute("SELECT status, COUNT(*) FROM files GROUP BY status").fetchall()
    return {row[0]: row[1] for row in rows}
