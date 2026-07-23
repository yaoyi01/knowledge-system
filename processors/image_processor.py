"""图片处理器 — DashScope qwen-vl 视觉识别"""
import base64
from pathlib import Path
from cleaner.state import upsert_metadata, log

BASE_DIR = Path.home() / "Documents" / "knowledge-system"


def process_image(file_hash: str, vault_path: str, conn) -> dict:
    import yaml
    from openai import OpenAI

    config = yaml.safe_load(open(Path.home() / ".hermes" / "config.yaml"))
    api_key = config["auxiliary"]["vision"]["api_key"]
    # 优先用 qwen3-vl-flash（更快更便宜），降级用 qwen-vl-max
    model = config.get("auxiliary", {}).get("vision", {}).get("model", "qwen-vl-max")
    client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

    # 读取并编码图片
    with open(vault_path, "rb") as f:
        img_data = base64.b64encode(f.read()).decode()

    # 预处理: 大图压缩
    try:
        from PIL import Image
        import io
        img = Image.open(vault_path)
        if max(img.size) > 2048:
            img.thumbnail((2048, 2048), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            img_data = base64.b64encode(buf.getvalue()).decode()
    except Exception:
        pass

    # 调用视觉模型
    resp = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_data}"}},
                {"type": "text", "text": "请详细描述这张图片的内容。如果是文档截图/表格，提取所有文字。如果是照片，描述场景、人物、物体和关键细节。如果是图表，描述图表类型、数据趋势和关键数值。用中文回答。"},
            ],
        }],
        max_tokens=1000,
    )

    description = resp.choices[0].message.content

    # 保存结果
    vision_dir = BASE_DIR / "processed" / "vision"
    vision_dir.mkdir(parents=True, exist_ok=True)
    result_path = vision_dir / f"{file_hash}.md"
    result_path.write_text(f"# 图片视觉分析\n\n{description}", encoding="utf-8")

    # 也存为文本供 RAG/Wiki
    text_path = BASE_DIR / "processed" / "text" / f"{file_hash}.txt"
    text_path.write_text(description, encoding="utf-8")

    upsert_metadata(conn, file_hash, vision_result_path=str(result_path))
    log(conn, file_hash, "processor", "done", f"image→vision: {len(description)} chars")

    return {"text_path": str(text_path), "image_paths": [], "meta": {"title": Path(vault_path).stem}}
