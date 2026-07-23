#!/usr/bin/env python3
"""
Wiki 自动处理器 — 读取 raw 文件，调用 DeepSeek 生成结构化知识页面
"""
import sys, re, yaml, json
from pathlib import Path
from datetime import datetime
from openai import OpenAI

BASE_DIR = Path.home() / "Documents" / "knowledge-system"
WIKI_DIR = BASE_DIR / "wiki"
RAW_DIR = WIKI_DIR / "raw" / "articles"


def get_api_keys():
    """从 Hermes 配置/环境变量读取所有 API Key"""
    import yaml, os, json
    keys = {}
    for env_var in ["DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"]:
        key = os.environ.get(env_var, "")
        if key:
            provider = env_var.replace("_API_KEY", "").lower()
            keys[provider] = key
    config_path = Path.home() / ".hermes" / "config.yaml"
    if config_path.exists():
        cfg = yaml.safe_load(config_path.read_text())
        aux_key = cfg.get("auxiliary", {}).get("vision", {}).get("api_key", "")
        if aux_key: keys["dashscope"] = aux_key
        for pid, p in cfg.get("providers", {}).items():
            k = p.get("api_key", "") or p.get("key", "")
            if k: keys[pid] = k
    auth_path = Path.home() / ".hermes" / "auth.json"
    if auth_path.exists():
        auth = json.loads(auth_path.read_text())
        for provider, creds in auth.get("credential_pool", {}).items():
            for c in creds:
                src = c.get("source", "")
                if src.startswith("env:"):
                    env_name = src[4:]
                    key = os.environ.get(env_name, "")
                    if key: keys[provider] = key
    # 4. ~/.hermes/.env 文件
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        for line in env_path.read_text().split("\n"):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k.endswith("_API_KEY") and v:
                    provider = k.replace("_API_KEY", "").lower()
                    keys[provider] = v
    return keys

def get_api_key(prefer="dashscope"):
    keys = get_api_keys()
    for k, v in keys.items():
        if prefer in k.lower(): return v
    return next(iter(keys.values()), None) if keys else None
def call_deepseek(text: str, title: str) -> dict:
    """调用 DeepSeek 提取实体和概念"""
    key = get_api_key('deepseek')
    if not key:
        return {"entities": [], "concepts": []}

    prompt = f"""你是一个知识管理助手。请从以下文档中提取关键实体和概念，用 JSON 格式返回。

文档标题: {title}
文档内容: {text[:4000]}

返回格式:
{{
  "summary": "文档一句话概述",
  "entities": [
    {{"name": "实体名", "type": "company|project|product|person", "description": "一句话描述"}}
  ],
  "concepts": [
    {{"name": "概念名", "description": "一句话解释"}}
  ]
}}

只返回 JSON，不要其他内容。"""

    client = OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3, max_tokens=2000,
    )
    content = resp.choices[0].message.content.strip()
    # 尝试提取 JSON
    if content.startswith("```"):
        content = re.sub(r"```\w*\n?", "", content).replace("```", "")
    return json.loads(content)


def create_wiki_page(name: str, entity_type: str, desc: str, source: str) -> str:
    """创建 wiki 页面文件"""
    folder = "entities" if entity_type in ("company", "project", "product", "person") else "concepts"
    page_dir = WIKI_DIR / folder
    page_dir.mkdir(parents=True, exist_ok=True)

    slug = re.sub(r"[^\w\u4e00-\u9fff\-]", "", name)[:50]
    page_path = page_dir / f"{slug}.md"

    content = f"""---
title: {name}
created: {datetime.now().strftime('%Y-%m-%d')}
updated: {datetime.now().strftime('%Y-%m-%d')}
type: {folder.rstrip('s')}
tags: []
sources:
  - {source}
confidence: medium
---

# {name}

{desc}

## 来源

- {source}
"""
    page_path.write_text(content, encoding="utf-8")
    return str(page_path)


def update_index(pages: list):
    """更新 index.md"""
    index_path = WIKI_DIR / "index.md"
    if not index_path.exists():
        index_path.write_text("# Wiki Index\n\n## Entities\n\n## Concepts\n", encoding="utf-8")

    content = index_path.read_text(encoding="utf-8")
    for title, etype in pages:
        entry = f"- [[{title}]]\n"
        section = "## Entities" if etype in ("entities", "company", "project", "product", "person") else "## Concepts"
        if entry not in content:
            content = content.replace(section, f"{section}\n{entry}")

    # 更新统计
    total = len(re.findall(r"^- \[\[", content, re.MULTILINE))
    content = re.sub(r"Total pages: \d+", f"Total pages: {total}", content)
    index_path.write_text(content, encoding="utf-8")


def process_all():
    """处理所有待处理的 raw 文件"""
    if not RAW_DIR.exists():
        print("无 raw 文件")
        return

    raws = list(RAW_DIR.glob("*.md"))
    if not raws:
        print("无待处理文件")
        return

    print(f"📖 处理 {len(raws)} 个 raw 文件...")
    created = []

    for f in raws:
        print(f"  📄 {f.name[:40]}...")
        try:
            text = f.read_text(encoding="utf-8")
            # 去掉 frontmatter
            text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL).strip()

            if len(text) < 100:
                print("    ⏭ 内容太少，跳过")
                continue

            result = call_deepseek(text, f.stem)

            for e in result.get("entities", []):
                path = create_wiki_page(e["name"], e.get("type", "entity"), e["description"], f"raw/articles/{f.name}")
                created.append((e["name"], "entities"))
                print(f"    ✅ 实体: {e['name']}")

            for c in result.get("concepts", []):
                path = create_wiki_page(c["name"], "concept", c["description"], f"raw/articles/{f.name}")
                created.append((c["name"], "concepts"))
                print(f"    ✅ 概念: {c['name']}")

        except Exception as e:
            print(f"    ❌ 失败: {e}")

    if created:
        update_index(created)
        print(f"\n✅ 完成: {len(created)} 个页面")
    else:
        print("⚠️ 未生成任何页面")


if __name__ == "__main__":
    process_all()
