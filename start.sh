#!/bin/bash

# PPT Generator 启动脚本
# 用法: ./start.sh [端口] [运行模式]
#   端口: 服务监听端口 (默认: 8080)
#   运行模式: web 或 cli (默认: web)

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 端口配置
PORT="${1:-8080}"
MODE="${2:-web}"

# 创建日志目录
LOG_DIR="$SCRIPT_DIR/log"
mkdir -p "$LOG_DIR"

# 生成日志文件名
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
LOG_FILE="$LOG_DIR/app_${TIMESTAMP}.log"

# 显示配置信息
echo "=================================="
echo "🖥️  PPT Generator 启动配置"
echo "=================================="
echo "📂 项目目录: $SCRIPT_DIR"
echo "🔌 端口: $PORT"
echo "📊 模式: $MODE"
echo "📋 日志文件: $LOG_FILE"
echo "=================================="
echo ""

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3，请确保 Python 已安装"
    exit 1
fi

# 检查依赖
echo "🔍 检查依赖..."
python3 -c "import flask" 2>/dev/null || {
    echo "⚠️  未安装 flask，正在安装..."
    pip install flask -q
}
echo "✅ 依赖检查完成"
echo ""

# 设置环境变量
export FLASK_PORT="$PORT"

# 启动服务
echo "🚀 正在启动服务..."
echo "🌐 访问地址: http://localhost:$PORT"
echo "📊 实时日志将同时显示在终端并保存到文件"
echo ""
echo "按 Ctrl+C 停止服务"
echo "----------------------------------------"

if [ "$MODE" = "web" ]; then
    # Web 模式: 运行 Flask 应用
    export FLASK_RUN_PORT="$PORT"
    python3 app.py 2>&1 | tee "$LOG_FILE"
else
    # CLI 模式: 运行 main.py
    python3 main.py test_input.json 2>&1 | tee "$LOG_FILE"
fi
