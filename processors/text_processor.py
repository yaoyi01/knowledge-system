"""文本/代码文件处理器"""
from pathlib import Path
from cleaner.state import upsert_metadata, log

BASE_DIR = Path.home() / "Documents" / "knowledge-system"


def process_text(file_hash: str, vault_path: str, conn) -> dict:
    path = Path(vault_path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        log(conn, file_hash, "processor", "error", "无法读取文件")
        return None

    text_path = BASE_DIR / "processed" / "text" / f"{file_hash}.txt"
    text_path.write_text(text, encoding="utf-8")

    meta = {"title": path.stem}
    upsert_metadata(conn, file_hash, **meta)

    log(conn, file_hash, "processor", "done", f"text: {len(text)} chars")
    return {"text_path": str(text_path), "image_paths": [], "meta": meta}
