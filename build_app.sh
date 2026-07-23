#!/bin/bash
# 打包为自包含 macOS .app
# 包含所有脚本、配置文件、Python 依赖
set -e

VENV="$HOME/.hermes/hermes-agent/venv/bin/python3"
APP_NAME="知识库"
SRC="$HOME/Documents/knowledge-system/kb_app.py"
KB="$HOME/Documents/knowledge-system"
OUT="$HOME/Desktop"
BUILD="/tmp/kb_build"

echo "📦 打包自包含 $APP_NAME.app ..."

# 清理旧的构建
rm -rf "$BUILD" "$OUT/$APP_NAME.app" "$OUT/$APP_NAME"

# 收集所有需要打包的文件
$VENV -m PyInstaller \
    --name="$APP_NAME" \
    --windowed \
    --onedir \
    --add-data "$KB/pipeline.py:." \
    --add-data "$KB/rag_index.py:." \
    --add-data "$KB/rag_search.py:." \
    --add-data "$KB/wiki_ingest.py:." \
    --add-data "$KB/health_check.py:." \
    --add-data "$KB/config.yaml:." \
    --add-data "$KB/cleaner:cleaner" \
    --add-data "$KB/processors:processors" \
    --add-data "$KB/holographic:holographic" \
    --add-data "$KB/pageindex:pageindex" \
    --add-data "$KB/wiki/wiki:wiki" \
    --add-data "$HOME/.hermes/scripts/holographic-archive.sh:scripts" \
    --hidden-import=customtkinter \
    --hidden-import=qdrant_client \
    --hidden-import=openai \
    --hidden-import=yaml \
    --hidden-import=PIL \
    --hidden-import=sqlite3 \
    --hidden-import=docx \
    --hidden-import=openpyxl \
    --hidden-import=pptx \
    --hidden-import=pymupdf \
    --hidden-import=watchdog \
    --hidden-import=PIL._imaging \
    --hidden-import=PIL.Image \
    "$SRC" \
    --distpath "$OUT" \
    --workpath "$BUILD" \
    --specpath "$BUILD" \
    --clean \
    2>&1 | grep -E "INFO: Building|INFO: App|completed|Error|WARNING" | tail -10

echo ""
echo "✅ 打包完成: $OUT/$APP_NAME.app"
echo ""
echo "  安装指南:"
echo "  1. 将 $APP_NAME.app 拖到 /Applications"
echo "  2. 双击启动"
echo "  3. 首次启动会显示安装向导，勾选需要的组件"
echo "  4. 安装完成后即可使用全部功能"
echo ""
echo "  注意: 需要同一台电脑上已安装 Hermes Agent"
echo "        (自动读取 Hermes 的 API 配置)"
