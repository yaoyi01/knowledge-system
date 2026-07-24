"""
格式检查 — 验证文件类型、magic bytes、可解析性
"""
import hashlib
import zipfile
from pathlib import Path

# ─── 支持的文件类型 ──────────────────────────────

TYPE_MAP = {
    # Office
    ".docx": "docx", ".doc": "doc",
    ".xlsx": "xlsx", ".xls": "xls",
    ".pptx": "pptx", ".ppt": "ppt",
    # PDF
    ".pdf": "pdf",
    # 图片
    ".jpg": "image", ".jpeg": "image", ".png": "image",
    ".gif": "image", ".webp": "image", ".bmp": "image",
    ".tiff": "image", ".tif": "image", ".svg": "image",
    # 视频
    ".mp4": "video", ".mov": "video", ".avi": "video",
    ".mkv": "video", ".wmv": "video", ".flv": "video",
    ".webm": "video",
    # 音频
    ".mp3": "audio", ".wav": "audio", ".m4a": "audio",
    ".aac": "audio", ".flac": "audio", ".ogg": "audio",
    ".wma": "audio",
    # 思维导图
    ".xmind": "mindmap", ".mm": "mindmap", ".opml": "mindmap",
    # Visio
    ".vsdx": "visio", ".vsd": "visio",
    # 文本
    ".md": "text", ".txt": "text", ".rst": "text",
    ".csv": "text", ".log": "text", ".json": "text",
    ".yaml": "text", ".yml": "text", ".xml": "text",
    ".html": "text", ".htm": "text",
    # 代码
    ".py": "code", ".pyw": "code",
    ".js": "code", ".mjs": "code", ".cjs": "code",
    ".ts": "code", ".tsx": "code", ".jsx": "code",
    ".go": "code", ".rs": "code",
    ".java": "code", ".kt": "code", ".swift": "code",
    ".c": "code", ".cpp": "code", ".h": "code", ".hpp": "code",
    ".rb": "code", ".sh": "code", ".bash": "code",
    ".sql": "code", ".r": "code",
}

# ─── Magic bytes 签名 ─────────────────────────────

SIGNATURES = {
    # ZIP-based (docx/xlsx/pptx/xmind/vsdx 都是 ZIP)
    "zip": b"PK\x03\x04",
    # PDF
    "pdf": b"%PDF",
    # 图片
    "png": b"\x89PNG\r\n\x1a\n",
    "jpg": b"\xff\xd8\xff",
    "gif": b"GIF8",
    "webp": b"RIFF",
    "bmp": b"BM",
    # 视频
    "mp4": b"\x00\x00\x00\x18ftyp",
    "mov": b"\x00\x00\x00\x14ftyp",
    "mkv": b"\x1aE\xdf\xa3",
    # 音频
    "mp3": b"\xff\xfb",  # or \xff\xf3, \xff\xf2
    "wav": b"RIFF",
    "flac": b"fLaC",
    "ogg": b"OggS",
}


def check_file(file_path: str) -> dict:
    """
    检查文件格式
    返回: {valid, file_type, mime_type, reason, original_name, file_size}
    """
    path = Path(file_path)
    result = {
        "valid": False,
        "file_type": None,
        "mime_type": None,
        "reason": "",
        "original_name": path.name,
        "original_path": str(path.resolve()),
        "file_size": 0,
    }

    # L1: 存在性 + 可读性
    if not path.exists():
        result["reason"] = "文件不存在"
        return result
    if not path.is_file():
        result["reason"] = "不是文件"
        return result
    try:
        result["file_size"] = path.stat().st_size
    except Exception:
        result["reason"] = "无法读取文件信息"
        return result
    if result["file_size"] == 0:
        result["reason"] = "空文件"
        return result
    # 检测云存储占位符（OneDrive/iCloud 按需文件）
    try:
        st = path.stat()
        if st.st_blocks == 0 and st.st_size > 0:
            result["reason"] = "云端占位符，未下载到本地"
            return result
    except Exception:
        pass

    # L2: 扩展名 → 类型
    ext = path.suffix.lower()
    file_type = TYPE_MAP.get(ext)
    if not file_type:
        result["reason"] = f"不支持的文件类型: {ext}"
        return result
    result["file_type"] = file_type

    # L3: Magic bytes 验证
    try:
        with open(path, "rb") as f:
            header = f.read(16)
    except Exception:
        result["reason"] = "无法读取文件"
        return result

    # ZIP-based 文件特殊处理
    if file_type in ("docx", "xlsx", "pptx", "xmind", "vsdx"):
        if header[:4] != SIGNATURES["zip"]:
            result["reason"] = f"不是有效的 {file_type.upper()} 文件 (非 ZIP 格式)"
            return result
        # 验证内部结构
        try:
            with zipfile.ZipFile(path, "r") as zf:
                names = [n.lower() for n in zf.namelist()]
            if file_type == "docx" and "[content_types].xml" not in names:
                result["reason"] = "不是有效的 DOCX (缺少 [Content_Types].xml)"
                return result
            if file_type == "xlsx" and "xl/workbook.xml" not in names:
                result["reason"] = "不是有效的 XLSX (缺少 xl/workbook.xml)"
                return result
            if file_type == "pptx" and "ppt/presentation.xml" not in names:
                result["reason"] = "不是有效的 PPTX (缺少 ppt/presentation.xml)"
                return result
        except zipfile.BadZipFile:
            result["reason"] = "ZIP 文件损坏"
            return result

    elif file_type == "pdf":
        if header[:4] != SIGNATURES["pdf"]:
            result["reason"] = "不是有效的 PDF 文件"
            return result

    elif file_type == "image":
        matched = False
        if header[:8] == SIGNATURES["png"]:
            matched = True
            result["mime_type"] = "image/png"
        elif header[:3] == SIGNATURES["jpg"]:
            matched = True
            result["mime_type"] = "image/jpeg"
        elif header[:4] == SIGNATURES["gif"]:
            matched = True
            result["mime_type"] = "image/gif"
        elif header[:4] == SIGNATURES["webp"]:
            matched = True
            result["mime_type"] = "image/webp"
        elif header[:2] == SIGNATURES["bmp"]:
            matched = True
            result["mime_type"] = "image/bmp"
        if not matched:
            result["reason"] = "无法识别的图片格式"
            return result
        # 额外: 用 PIL 验证可打开性
        try:
            from PIL import Image
            with Image.open(path) as img:
                img.verify()
        except Exception:
            result["reason"] = "图片文件损坏或无法解析"
            return result

    elif file_type in ("video", "audio"):
        # 只做基本的 magic bytes 检查，后续用 ffprobe 验证
        pass

    elif file_type in ("text", "code"):
        # 文本文件：检查是否可读
        try:
            with open(path, "r", encoding="utf-8") as f:
                f.read(1024)
        except UnicodeDecodeError:
            # 可能不是 UTF-8，但仍可能是有效二进制
            pass
        except Exception:
            result["reason"] = "无法读取文件内容"
            return result

    result["valid"] = True
    return result
