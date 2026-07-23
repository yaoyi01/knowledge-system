"""PDF 处理器"""
from pathlib import Path
from cleaner.state import upsert_metadata, log

BASE_DIR = Path.home() / "Documents" / "knowledge-system"


def process_pdf(file_hash: str, vault_path: str, conn) -> dict:
    try:
        import pymupdf
    except ImportError:
        log(conn, file_hash, "processor", "error", "pymupdf 未安装")
        return None

    doc = pymupdf.open(vault_path)
    lines = []

    for i, page in enumerate(doc, 1):
        text = page.get_text("text")
        if text.strip():
            lines.append(f"\n--- Page {i} ---")
            lines.append(text)

    text = "\n".join(lines)
    text_path = BASE_DIR / "processed" / "text" / f"{file_hash}.txt"
    text_path.write_text(text, encoding="utf-8")

    # 内嵌图片
    image_paths = []
    try:
        img_dir = BASE_DIR / "processed" / "images" / file_hash
        img_dir.mkdir(parents=True, exist_ok=True)
        for i, page in enumerate(doc):
            for j, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                base_image = doc.extract_image(xref)
                ext = base_image["ext"]
                img_path = img_dir / f"page{i+1}_img{j:03d}.{ext}"
                img_path.write_bytes(base_image["image"])
                image_paths.append(str(img_path))
    except Exception:
        pass

    meta = {
        "title": doc.metadata.get("title") or Path(vault_path).stem,
        "author": doc.metadata.get("author"),
        "page_count": len(doc),
    }
    doc.close()
    upsert_metadata(conn, file_hash, **meta)

    log(conn, file_hash, "processor", "done", f"pdf→text: {len(text)} chars, {len(image_paths)} images")
    return {"text_path": str(text_path), "image_paths": image_paths, "meta": meta}
