<div align="center">

<img src="https://img.shields.io/badge/Hermes-Agent-FF6B35?style=for-the-badge" alt="Hermes Agent">
<img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
<img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge" alt="Python">

</div>

# 🧠 Knowledge System — 让 AI Agent 拥有记忆与知识

**一键安装 | 桌面 App | 10 种文件处理 | RAG 检索 | LLM Wiki 自动生成**

> 为 Hermes Agent 打造的即插即用记忆系统。导入你的文档，AI 即刻获得可搜索的长期记忆和结构化知识库。

---

## ✨ 为什么需要它？

AI Agent 会话结束就"失忆"？文档散落各处无法检索？**Knowledge System 在 Hermes 之上构建了一套完整的认知架构：**

- 📥 **吃进你的一切** — Word / Excel / PPT / PDF / 图片 / 视频 / 音频 / 思维导图 / Visio / 代码，10 种格式自动处理
- 🔍 **随问随答** — 文档内容向量化存入 RAG 知识库，语义搜索秒级响应
- 📖 **自动整理** — LLM Wiki 从文档中提取实体和概念，自动生成结构化知识页面
- 💬 **不会遗忘** — Holographic 定时归档你的每段对话，历史交流随时回溯

---

## 🚀 30 秒上手

```bash
# 1. 克隆
git clone https://github.com/yaoyi01/knowledge-system.git
cd knowledge-system

# 2. 安装
bash install.sh

# 3. 启动
kui
```

双击 `KB.app` 或运行 `kui`，弹出安装向导 → 勾选组件 → 开始导入你的文档。

---

## 🎯 核心能力

<table>
<tr>
<td width="50%">

### 📊 桌面管理 App
- 可视化仪表盘，实时查看文档/向量/对话/Wiki 数量
- 拖拽导入 + 目录监听
- Wiki 内容浏览与编辑
- 对话历史语义搜索
- 一键健康检查

</td>
<td width="50%">

### 🧹 数据 Pipeline
- 格式检查 → 去重 → 元数据归一
- 10 种文件处理器并行工作
- 图片/视频 → DashScope 视觉识别
- 音频 → DashScope 语音转文字
- 文件归档到 vault/ 不可变存储

</td>
</tr>
<tr>
<td width="50%">

### 🔍 RAG 知识检索
- DashScope text-embedding-v3 向量化
- Qdrant 本地存储，零依赖外部服务
- 语义搜索秒级响应
- 自动 chunk 分块（500 tokens/块）

</td>
<td width="50%">

### 📖 LLM Wiki 自动生成
- DeepSeek 从文档提取实体和概念
- 自动生成交叉引用知识页面
- Markdown 格式，Wiki 链接导航
- 每次导入自动触发

</td>
</tr>
</table>

---

## 🏗️ 架构

```
┌── 用户文档 ─────────────────────────────────────┐
│  .docx .xlsx .pptx .pdf .jpg .mp4 .mp3 .xmind .vsdx .md .py ... │
└─────────────────┬───────────────────────────────┘
                  ▼
┌── 数据清理器 ───────────────────────────────────┐
│  格式检查 → 去重 → 元数据归一 → 文件归档         │
└─────────────────┬───────────────────────────────┘
                  ▼
┌── 文件处理器 (10种) ────────────────────────────┐
│  docx → python-docx    xlsx → openpyxl           │
│  pptx → python-pptx    pdf → pymupdf             │
│  image → DashScope VL   video → ffmpeg+VL        │
│  audio → fun-asr       mindmap → XML             │
│  visio → XML            text → 直接读取           │
└────────┬──────────────────┬─────────────────────┘
         ▼                  ▼
┌── RAG (Qdrant) ──┐  ┌── LLM Wiki ──────────────┐
│ DashScope embed → │  │ DeepSeek 提取 →          │
│ 语义搜索 ←        │  │ 实体/概念页面 →          │
│                   │  │ [[wikilink]] 导航        │
└───────────────────┘  └──────────────────────────┘

         ┌── Holographic ──────────────────────┐
         │ 对话归档 → Qdrant → 语义搜索         │
         │ Cron 每 30 分钟自动运行               │
         └──────────────────────────────────────┘

         ┌── PageIndex ────────────────────────┐
         │ 代码符号索引 → 函数/类/import 搜索    │
         └──────────────────────────────────────┘
```

---

## 🔌 与 Hermes 深度集成

系统**自动读取** Hermes 已配置的 API Key，零手动配置：

| 检测源 | 优先级 |
|--------|:---:|
| 环境变量 (`DEEPSEEK_API_KEY`, `DASHSCOPE_API_KEY`) | 1 |
| `~/.hermes/config.yaml` (`auxiliary.vision`) | 2 |
| `~/.hermes/auth.json` (`credential_pool`) | 3 |
| `~/.hermes/.env` (`KEY=VALUE`) | 4 |

**支持的模型分工：**
- 🔵 DeepSeek → Wiki 知识页面生成
- 🟠 DashScope → 向量嵌入、视觉识别、语音识别
- 🟢 OpenAI 兼容 → 任意兼容接口的 Provider

---

## 📦 命令行工具

| 命令 | 功能 |
|------|------|
| `kui` | 启动桌面 App |
| `kp <文件>` | 导入文档到知识库 |
| `kp --scan` | 扫描所有配置目录 |
| `kp --watch` | 实时监听文件变更 |
| `kr "关键词"` | RAG 语义搜索 |
| `kh "内容"` | 对话历史搜索 |
| `kc search "函数"` | 代码符号搜索 |
| `kcheck` | 系统健康检查 |

---

## 🎨 设计理念

遵循 [Apple Notes 设计规范](DESIGN.md)：
- 画布色 `#FFFBED` Notes Cream
- 强调色 `#F09A38` Notes Orange
- SF Pro 字体，便签纸质感
- 零装饰阴影，内容即界面

---

## 🔐 安全性

- ✅ 所有数据本地存储（Qdrant 嵌入式 + SQLite + 文件系统）
- ✅ API Key 从 Hermes 继承，不额外存储
- ✅ 原始文件归档到 vault/，处理过程可追溯
- ✅ 不含遥测/追踪/分析代码
- ✅ .gitignore 排除所有用户数据

---

## 🧩 通过 AI Agent 一键安装

在 Hermes 对话中说：

```
访问 https://github.com/yaoyi01/knowledge-system，根据 README 安装知识库系统
```

Agent 会自动 clone 项目 → 运行 install.sh → 配置所有组件 → 启动桌面 App。

---

## 📄 License

MIT © [yaoyi01](https://github.com/yaoyi01)
