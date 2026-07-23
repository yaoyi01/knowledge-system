#!/bin/bash
# 知识库系统一键安装器
# 用法: bash install.sh
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
echo -e "${GREEN}📚 知识库系统安装器${NC}"
echo ""

# ── 1. 检查 Hermes ──
HERMES_HOME="$HOME/.hermes"
if [ ! -d "$HERMES_HOME" ]; then
    echo -e "${RED}❌ 未找到 Hermes ($HERMES_HOME)${NC}"
    echo "   请先安装 Hermes Agent"
    exit 1
fi
echo -e "${GREEN}✓${NC} 检测到 Hermes"

# ── 2. 确定 Python ──
VENV_PYTHON="$HERMES_HOME/hermes-agent/venv/bin/python3"
if [ ! -f "$VENV_PYTHON" ]; then
    echo -e "${YELLOW}⚠ 未找到 Hermes venv，使用系统 Python${NC}"
    VENV_PYTHON="python3"
fi

# ── 3. 创建目录 ──
KB="$HOME/Documents/knowledge-system"
echo "📁 创建目录: $KB"
mkdir -p "$KB"/{cleaner,processors,vault,staging/incoming,quarantine,processed/{text,images,vision,speech,merged},rag/qdrant_data,logs,wiki/{raw/articles,entities,concepts,comparisons,queries},pageindex/{files,scripts},holographic/{conversations,qdrant_data}}

# ── 4. 安装 Python 依赖 ──
echo "📦 安装 Python 依赖..."
$VENV_PYTHON -m pip install --quiet \
    qdrant-client openai pyyaml python-docx openpyxl python-pptx pymupdf \
    Pillow customtkinter watchdog 2>&1 | tail -1
echo -e "${GREEN}✓${NC} 依赖安装完成"

# ── 5. 检查 ffmpeg ──
if command -v ffmpeg &>/dev/null; then
    echo -e "${GREEN}✓${NC} ffmpeg 已安装"
else
    echo -e "${YELLOW}⚠ ffmpeg 未安装 (音视频处理需要)${NC}"
    echo "   安装: brew install ffmpeg"
fi

# ── 6. 复制脚本 ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/pipeline.py" ]; then
    cp "$SCRIPT_DIR"/pipeline.py "$KB/"
    cp "$SCRIPT_DIR"/rag_index.py "$KB/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/rag_search.py "$KB/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/wiki_ingest.py "$KB/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/health_check.py "$KB/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/kb_app.py "$KB/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/cleaner/*.py "$KB/cleaner/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/processors/*.py "$KB/processors/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/config.yaml "$KB/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/pageindex/pageindex.py "$KB/pageindex/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/holographic/*.py "$KB/holographic/" 2>/dev/null || true
fi

# ── 7. 初始化数据库 ──
$VENV_PYTHON -c "
import sys; sys.path.insert(0, '$KB')
from cleaner.state import init_db; init_db()
print('state.db 已初始化')
"

# ── 8. 创建启动器 (Launch script) ──
LAUNCHER="$KB/knowledge-base"
cat > "$LAUNCHER" << LAUNCHEREOF
#!/bin/bash
exec $VENV_PYTHON $KB/kb_app.py
LAUNCHEREOF
chmod +x "$LAUNCHER"

# ── 9. 配置 zsh alias ──
if ! grep -q "alias kui=" "$HOME/.zshrc" 2>/dev/null; then
    cat >> "$HOME/.zshrc" << 'EOF'

# ─── 知识库快捷命令 ───
alias kui='~/.hermes/hermes-agent/venv/bin/python3 ~/Documents/knowledge-system/kb_app.py &'
alias kp='~/.hermes/hermes-agent/venv/bin/python3 ~/Documents/knowledge-system/pipeline.py'
alias kr='~/.hermes/hermes-agent/venv/bin/python3 ~/Documents/knowledge-system/rag_search.py'
alias kh='~/.hermes/hermes-agent/venv/bin/python3 ~/Documents/knowledge-system/holographic/search.py'
alias kc='~/.hermes/hermes-agent/venv/bin/python3 ~/Documents/knowledge-system/pageindex/pageindex.py'
alias kcheck='~/.hermes/hermes-agent/venv/bin/python3 ~/Documents/knowledge-system/health_check.py'
EOF
fi

echo ""
echo -e "${GREEN}✅ 安装完成！${NC}"
echo ""
echo "  启动命令:"
echo "    kui              # 打开管理界面"
echo "    kp <文件>         # 导入文档"
echo "    kr \"关键词\"        # 搜索知识库"
echo "    kh \"关键词\"        # 搜索对话"
echo "    kc search \"函数\"  # 搜索代码"
echo "    kcheck           # 健康检查"
echo ""
echo "  新开终端或执行: source ~/.zshrc"
