"""
文本处理器 — 调度器
根据 file_type 分发到对应处理器
"""
from pathlib import Path
import sys

BASE_DIR = Path.home() / "Documents" / "knowledge-system"
PROCESSED_TEXT = BASE_DIR / "processed" / "text"
PROCESSED_IMAGES = BASE_DIR / "processed" / "images"

sys.path.insert(0, str(BASE_DIR))


def process(file_hash: str, file_type: str, vault_path: str, conn) -> dict:
    """调度到对应处理器，返回 {text_path, image_paths, meta}"""
    PROCESSED_TEXT.mkdir(parents=True, exist_ok=True)

    if file_type == "docx":
        from processors.docx_processor import process_docx
        return process_docx(file_hash, vault_path, conn)
    elif file_type == "xlsx":
        from processors.xlsx_processor import process_xlsx
        return process_xlsx(file_hash, vault_path, conn)
    elif file_type == "pptx":
        from processors.pptx_processor import process_pptx
        return process_pptx(file_hash, vault_path, conn)
    elif file_type == "pdf":
        from processors.pdf_processor import process_pdf
        return process_pdf(file_hash, vault_path, conn)
    elif file_type == "text":
        from processors.text_processor import process_text
        return process_text(file_hash, vault_path, conn)
    elif file_type == "code":
        from processors.text_processor import process_text
        return process_text(file_hash, vault_path, conn)
    elif file_type == "image":
        from processors.image_processor import process_image
        return process_image(file_hash, vault_path, conn)
    elif file_type == "mindmap":
        from processors.mindmap_processor import process_mindmap
        return process_mindmap(file_hash, vault_path, conn)
    elif file_type == "visio":
        from processors.visio_processor import process_visio
        return process_visio(file_hash, vault_path, conn)
    elif file_type in ("video", "audio"):
        if file_type == "video":
            from processors.video_processor import process_video
            return process_video(file_hash, vault_path, conn)
        else:
            from processors.audio_processor import process_audio
            return process_audio(file_hash, vault_path, conn)
    else:
        return {"text_path": None, "image_paths": [], "meta": {}}
