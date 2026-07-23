# Hermes 知识库系统

为 [Hermes Agent](https://hermes-agent.nousresearch.com/) 提供的记忆系统与文档知识库。

## 功能

| 组件 | 功能 |
|------|------|
| 📊 桌面 App | 图形化管理界面，非技术人员也能用 |
| 🧹 数据清理器 | 格式检查、去重、元数据归一 |
| ⚙️ 文件处理器 | 支持 Word/Excel/PPT/PDF/图片/视频/音频/思维导图/Visio/Markdown/代码 |
| 🔍 RAG 检索 | 文档语义搜索（DashScope embedding） |
| 📖 LLM Wiki | 自动提取实体和概念，生成结构化知识页面 |
| 💬 Holographic | 对话记忆归档 + 语义搜索 |
| 📇 PageIndex | 代码符号索引 |

## 快速安装

**前提**：已安装 [Hermes Agent](https://hermes-agent.nousresearch.com/)。

```bash
git clone https://github.com/xxx/knowledge-system.git
cd knowledge-system
bash install.sh
```

安装完成后：
```bash
kui          # 启动桌面 App
kp 文件路径   # 命令行导入文档
kr "关键词"   # 搜索知识库
kh "内容"     # 搜索对话历史
```

## 桌面 App

双击 `KB.app` 或运行 `kui`：

```
┌──────────────────────────────────────┐
│  📊 概览    📁 导入    📖 Wiki       │
│  💬 对话    🔍 搜索    ⚙️ 设置      │
└──────────────────────────────────────┘
```

首次启动会自动弹出安装向导，勾选需要的组件即可。

## 通过 AI Agent 安装

在 Hermes 对话中说：

> 访问 https://github.com/xxx/knowledge-system，根据项目 README 安装知识库系统

Agent 会自动执行安装脚本并配置所有组件。

## 架构

```
用户文件 → 数据清理器 → 文件处理器 → RAG 向量库
                                    → LLM Wiki
                                    → 归档存储

Hermes 对话 → Holographic → 语义搜索
            → PageIndex   → 代码搜索
```

详见 `architecture.html`。

## API Key 配置

系统自动从 Hermes 配置中读取 API Key（优先级）：

1. 环境变量 (`DEEPSEEK_API_KEY`, `DASHSCOPE_API_KEY`)
2. `~/.hermes/config.yaml` (`auxiliary.vision.api_key`)
3. `~/.hermes/auth.json` (credential_pool)
4. `~/.hermes/.env` (KEY=VALUE)

支持的模型：
- **DeepSeek** — Wiki 知识页面生成
- **DashScope** — 向量嵌入、视觉识别、语音识别

## 项目结构

```
├── kb_app.py              # 桌面管理 App
├── pipeline.py            # 数据 Pipeline 主入口
├── rag_index.py           # RAG 向量索引
├── rag_search.py          # RAG 语义搜索
├── wiki_ingest.py         # Wiki 导入
├── wiki_auto.py           # Wiki 自动生成
├── health_check.py        # 健康检查
├── config.yaml            # 配置模板
├── install.sh             # 一键安装
├── build_app.sh           # 打包 .app
├── architecture.html      # 架构图
├── cleaner/               # 数据清理器
├── processors/            # 文件处理器（10种格式）
├── holographic/           # 对话记忆
├── pageindex/             # 代码索引
├── wiki/                  # Wiki 模板
└── scripts/               # Cron 脚本
```
