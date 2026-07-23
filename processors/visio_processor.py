"""Visio 处理器 — .vsdx XML 解析"""
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from cleaner.state import upsert_metadata, log

BASE_DIR = Path.home() / "Documents" / "knowledge-system"
NS = "{http://schemas.microsoft.com/office/visio/2012/main}"


def process_visio(file_hash: str, vault_path: str, conn) -> dict:
    path = Path(vault_path)
    lines = [f"# Visio 图表: {path.stem}"]

    try:
        with zipfile.ZipFile(path, "r") as zf:
            # 读取页面列表
            if "visio/pages/pages.xml" in zf.namelist():
                pages_xml = ET.fromstring(zf.read("visio/pages/pages.xml"))
            else:
                pages_xml = None

            # 读取每个页面
            page_files = [n for n in zf.namelist() if n.startswith("visio/pages/page") and n.endswith(".xml")]
            for pf in sorted(page_files):
                page_num = pf.replace("visio/pages/page", "").replace(".xml", "")
                page_xml = ET.fromstring(zf.read(pf))
                lines.append(f"\n## 页面 {page_num}")

                # 提取形状文本
                shapes = []
                for shape in page_xml.iter(f"{NS}Shape"):
                    name = shape.get("Name", "")
                    texts = []
                    for t in shape.iter(f"{NS}Text"):
                        text = "".join(t.itertext()).strip()
                        if text:
                            texts.append(text)
                    if name or texts:
                        shapes.append({"name": name, "texts": texts})

                if shapes:
                    lines.append("\n| 名称 | 文本 |")
                    lines.append("|------|------|")
                    for s in shapes:
                        text_str = " / ".join(s["texts"]) if s["texts"] else ""
                        lines.append(f"| {s['name']} | {text_str} |")

                # 提取连接关系
                connects = []
                for conn in page_xml.iter(f"{NS}Connect"):
                    from_sheet = conn.get("FromSheet", "")
                    to_sheet = conn.get("ToSheet", "")
                    if from_sheet and to_sheet:
                        connects.append((from_sheet, to_sheet))
                if connects:
                    lines.append(f"\n连接关系 ({len(connects)} 条):")
                    for f, t in connects[:50]:  # 最多 50 条
                        lines.append(f"- {f} → {t}")

    except Exception as e:
        log(conn, file_hash, "processor", "error", str(e))
        return None

    text = "\n".join(lines)
    text_path = BASE_DIR / "processed" / "text" / f"{file_hash}.txt"
    text_path.write_text(text, encoding="utf-8")

    upsert_metadata(conn, file_hash, title=path.stem)
    log(conn, file_hash, "processor", "done", f"visio→text: {len(text)} chars")
    return {"text_path": str(text_path), "image_paths": [], "meta": {"title": path.stem}}
