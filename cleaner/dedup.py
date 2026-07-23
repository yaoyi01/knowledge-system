"""
去重 — SHA256 内容哈希 + 状态查询
"""
import hashlib
import shutil
from pathlib import Path
from datetime import datetime

from cleaner.state import DB_PATH, file_exists, insert_file, log
import sqlite3

BASE_DIR = Path.home() / "Documents" / "knowledge-system"
VAULT_DIR = BASE_DIR / "vault"
QUARANTINE_DIR = BASE_DIR / "quarantine"


def compute_hash(file_path: str) -> str:
    """计算 SHA256"""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()


def archive_to_vault(file_path: str, file_hash: str) -> str:
    """归档到 vault/YYYY/MM/{hash[:12]}_{原文件名}"""
    path = Path(file_path)
    now = datetime.now()
    dest_dir = VAULT_DIR / str(now.year) / f"{now.month:02d}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{file_hash[:12]}_{path.name}"
    shutil.copy2(path, dest)
    return str(dest)


def quarantine(file_path: str, reason: str) -> str:
    """移入隔离区"""
    path = Path(file_path)
    dest = QUARANTINE_DIR / f"{reason[:20]}_{datetime.now().strftime('%H%M%S')}_{path.name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dest))
    return str(dest)


def process(conn, file_path: str, file_type: str, file_size: int, mime_type=None) -> dict:
    """
    去重检查
    返回: {is_duplicate, file_hash, vault_path, action}
    """
    # 计算哈希
    file_hash = compute_hash(file_path)
    modified_at = datetime.fromtimestamp(Path(file_path).stat().st_mtime).isoformat()

    # 查重
    if file_exists(file_hash, conn):
        # 重复文件 → 隔离
        q_path = quarantine(file_path, "duplicate")
        log(conn, file_hash, "dedup", "skipped", f"重复文件: {q_path}")
        return {
            "is_duplicate": True,
            "file_hash": file_hash,
            "vault_path": None,
            "action": "skipped",
        }

    # 归档
    vault_path = archive_to_vault(file_path, file_hash)

    # 写入数据库
    insert_file(
        conn,
        file_hash=file_hash,
        original_path=str(Path(file_path).resolve()),
        original_name=Path(file_path).name,
        file_type=file_type,
        file_size=file_size,
        mime_type=mime_type,
        modified_at=modified_at,
        vault_path=vault_path,
        status="validated",
    )

    log(conn, file_hash, "dedup", "archived", f"归档: {vault_path}")

    return {
        "is_duplicate": False,
        "file_hash": file_hash,
        "vault_path": vault_path,
        "action": "validated",
    }
