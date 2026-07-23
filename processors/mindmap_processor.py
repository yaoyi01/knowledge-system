"""思维导图处理器 — .xmind / .mm / .opml"""
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from cleaner.state import upsert_metadata, log

BASE_DIR = Path.home() / "Documents" / "knowledge-system"


def process_mindmap(file_hash: str, vault_path: str, conn) -> dict:
    path = Path(vault_path)
    suffix = path.suffix.lower()
    lines = [f"# 思维导图: {path.stem}"]

    try:
        if suffix == ".xmind":
            lines.extend(_parse_xmind(path))
        elif suffix == ".mm":
            lines.extend(_parse_freemind(path))
        elif suffix == ".opml":
            lines.extend(_parse_opml(path))
    except Exception as e:
        log(conn, file_hash, "processor", "error", str(e))
        return None

    text = "\n".join(lines)
    text_path = BASE_DIR / "processed" / "text" / f"{file_hash}.txt"
    text_path.write_text(text, encoding="utf-8")

    upsert_metadata(conn, file_hash, title=path.stem)
    log(conn, file_hash, "processor", "done", f"mindmap→text: {len(text)} chars")
    return {"text_path": str(text_path), "image_paths": [], "meta": {"title": path.stem}}


def _parse_xmind(path):
    lines = []
    with zipfile.ZipFile(path, "r") as zf:
        # 尝试 content.json (XMind Zen)
        if "content.json" in zf.namelist():
            data = json.loads(zf.read("content.json"))
            for sheet in data:
                root = sheet.get("rootTopic", {})
                lines.extend(_extract_xmind_node(root, 1))
        # 降级: content.xml (XMind 8)
        elif "content.xml" in zf.namelist():
            root = ET.fromstring(zf.read("content.xml"))
            for sheet in root.iter("{*}sheet"):
                for topic in sheet.iter("{*}topic"):
                    lines.extend(_extract_freemind_node(topic, 1))
    return lines


def _extract_xmind_node(node, depth):
    lines = []
    title = node.get("title", "")
    if title:
        prefix = "  " * (depth - 1) + "- "
        lines.append(f"{prefix}{title}")
        # 备注
        notes = node.get("notes", {})
        if isinstance(notes, dict) and notes.get("content"):
            lines.append(f"  {prefix}  💬 {notes['content']}")
    for child in node.get("children", {}).get("attached", []):
        lines.extend(_extract_xmind_node(child, depth + 1))
    return lines


def _parse_freemind(path):
    lines = []
    root = ET.parse(str(path)).getroot()
    for node in root.iter("node"):
        text = node.get("TEXT", "")
        if text:
            depth = len(list(node.iterancestors("node"))) + 1
            prefix = "  " * (depth - 1) + "- "
            lines.append(f"{prefix}{text}")
    return lines


def _extract_freemind_node(node, depth):
    lines = []
    text = node.get("TEXT", "")
    if text:
        prefix = "  " * (depth - 1) + "- "
        lines.append(f"{prefix}{text}")
    for child in node.findall("node"):
        lines.extend(_extract_freemind_node(child, depth + 1))
    return lines


def _parse_opml(path):
    lines = []
    root = ET.parse(str(path)).getroot()
    for outline in root.iter("outline"):
        text = outline.get("text", "")
        if text:
            depth = len(list(outline.iterancestors("outline"))) + 1
            prefix = "  " * (depth - 1) + "- "
            lines.append(f"{prefix}{text}")
    return lines
