#!/bin/bash
set -e

# ═══════════════════════════════════════════════════
#  PPT Generator 启动脚本
#  用法: ./start.sh [选项]
#
#  选项:
#    -p, --port PORT    服务端口 (默认: 8080)
#    -m, --mode MODE    运行模式: web | cli (默认: web)
#    -f, --force        端口被占用时强制关闭，不提示
#    -h, --help         显示帮助
# ═══════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 默认值 ──
PORT=8080
MODE="web"
FORCE=false

# ── 参数解析 ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--port)  PORT="$2"; shift 2 ;;
        -m|--mode)  MODE="$2"; shift 2 ;;
        -f|--force) FORCE=true; shift ;;
        -h|--help)
            head -12 "$0" | tail -9
            exit 0 ;;
        *)
            # 兼容旧版位置参数: ./start.sh 8080 web
            if [[ "$1" =~ ^[0-9]+$ ]]; then PORT="$1"; shift
            elif [[ "$1" =~ ^(web|cli)$ ]]; then MODE="$1"; shift
            else echo "未知参数: $1"; exit 1; fi ;;
    esac
done

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}▶${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*"; }
err()   { echo -e "${RED}✗${NC} $*"; }

# ── 1. 检查 Python ──
info "检查 Python 环境..."

PYTHON=""
if [ -x "$SCRIPT_DIR/.venv/bin/python3" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
fi

if [ -z "$PYTHON" ]; then
    err "未找到 python3，请先安装 Python 3.9+"
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
ok "Python $PY_VERSION ($PYTHON)"

# ── 2. 虚拟环境 + 依赖 ──
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    info "首次运行，创建虚拟环境..."

    if command -v uv &>/dev/null; then
        uv venv "$SCRIPT_DIR/.venv" --quiet
        ok "venv 已创建 (via uv)"
        uv pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
        ok "依赖已安装 (via uv)"
    else
        python3 -m venv "$SCRIPT_DIR/.venv"
        ok "venv 已创建"
        "$SCRIPT_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q
        ok "依赖已安装"
    fi

    PYTHON="$SCRIPT_DIR/.venv/bin/python3"
else
    # venv 已存在，快速检查关键依赖
    if ! "$PYTHON" -c "import flask" 2>/dev/null; then
        info "检测到依赖缺失，重新安装..."
        if command -v uv &>/dev/null; then
            uv pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
        else
            "$SCRIPT_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q
        fi
        ok "依赖已修复"
    else
        ok "虚拟环境就绪"
    fi
fi

# ── 3. 检查 .env ──
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        warn ".env 不存在，已从 .env.example 复制模板"
        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        warn "请编辑 .env 填入你的 API Key"
    fi
fi

# ── 4. 端口冲突检测 ──
info "检查端口 $PORT..."

kill_port() {
    local pid
    if command -v lsof &>/dev/null; then
        # macOS
        pid=$(lsof -ti :"$PORT" 2>/dev/null)
    elif command -v ss &>/dev/null; then
        # Linux
        pid=$(ss -tlnp "sport = :$PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1)
    elif command -v fuser &>/dev/null; then
        pid=$(fuser "$PORT/tcp" 2>/dev/null | tr -d ' ')
    fi

    if [ -n "$pid" ]; then
        echo "$pid"
    fi
}

EXISTING_PID=$(kill_port)

if [ -n "$EXISTING_PID" ]; then
    warn "端口 $PORT 已被占用 (PID: $EXISTING_PID)"

    if [ "$FORCE" = true ]; then
        info "强制模式，正在关闭占用进程..."
        kill -9 "$EXISTING_PID" 2>/dev/null || true
        sleep 0.5
        ok "进程 $EXISTING_PID 已终止"
    else
        echo ""
        echo -e "  ${YELLOW}端口 $PORT 正被进程 $EXISTING_PID 占用${NC}"
        echo -e "  是否关闭该进程并启动新服务？"
        echo ""
        echo -e "  ${CYAN}[Y]${NC} 关闭旧进程并启动"
        echo -e "  ${CYAN}[n]${NC} 取消退出"
        echo -e "  ${CYAN}[p]${NC} 换一个新端口"
        echo ""
        read -rp "  请选择 [Y/n/p]: " choice
        choice=${choice:-Y}

        case "$choice" in
            Y|y|yes)
                info "正在关闭进程 $EXISTING_PID..."
                kill -9 "$EXISTING_PID" 2>/dev/null || true
                sleep 0.5
                ok "旧进程已终止"
                ;;
            P|p)
                read -rp "  输入新端口号: " NEW_PORT
                if [[ "$NEW_PORT" =~ ^[0-9]+$ ]] && [ "$NEW_PORT" -gt 1024 ] && [ "$NEW_PORT" -lt 65535 ]; then
                    PORT="$NEW_PORT"
                    ok "切换到端口 $PORT"
                else
                    err "无效端口号"
                    exit 1
                fi
                ;;
            *)
                info "已取消"
                exit 0
                ;;
        esac
    fi
else
    ok "端口 $PORT 可用"
fi

# ── 5. 创建日志目录 ──
LOG_DIR="$SCRIPT_DIR/log"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/app_$(date '+%Y%m%d_%H%M%S').log"

# ── 6. 启动 ──
echo ""
echo -e "${CYAN}══════════════════════════════════════${NC}"
echo -e "  🖥  PPT Generator"
echo -e "${CYAN}══════════════════════════════════════${NC}"
echo -e "  📂 目录: $SCRIPT_DIR"
echo -e "  🔌 端口: ${GREEN}$PORT${NC}"
echo -e "  📊 模式: $MODE"
echo -e "  📋 日志: $LOG_FILE"
echo -e "${CYAN}══════════════════════════════════════${NC}"

if [ "$MODE" = "web" ]; then
    echo -e "  🌐 ${GREEN}http://localhost:$PORT${NC}"
    echo ""
    echo -e "  按 ${YELLOW}Ctrl+C${NC} 停止服务"
    echo -e "${CYAN}──────────────────────────────────────${NC}"
    echo ""
    export FLASK_PORT="$PORT"
    "$PYTHON" app.py --port "$PORT" 2>&1 | tee "$LOG_FILE"
else
    echo -e "  📝 CLI 模式: main.py test_input.json"
    echo -e "${CYAN}──────────────────────────────────────${NC}"
    echo ""
    "$PYTHON" main.py test_input.json 2>&1 | tee "$LOG_FILE"
fi
