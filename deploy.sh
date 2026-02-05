#!/bin/bash
#
# SonicVideo 一键部署脚本
# 使用方法: ./deploy.sh [--langgraph] [--port PORT]
#

set -e  # 遇到错误立即退出

# ============ 配置项 ============
PROJECT_DIR="/opt/sonicvideo"  # 项目部署目录
VENV_DIR="venv"
LOG_DIR="/var/log/sonicvideo"
PID_FILE="/var/run/sonicvideo.pid"
DEFAULT_PORT=8000
USE_LANGGRAPH=false

# ============ 颜色输出 ============
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============ 参数解析 ============
PORT=$DEFAULT_PORT

while [[ $# -gt 0 ]]; do
    case $1 in
        --langgraph)
            USE_LANGGRAPH=true
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --help)
            echo "使用方法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --langgraph    启用 LangGraph v2 工作流"
            echo "  --port PORT    指定服务端口 (默认: 8000)"
            echo "  --help         显示此帮助信息"
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            exit 1
            ;;
    esac
done

# ============ 检查权限 ============
if [ "$EUID" -ne 0 ]; then
    log_warn "建议使用 sudo 运行此脚本以确保完整权限"
fi

# ============ 步骤 1: 检查依赖 ============
log_info "检查系统依赖..."

# 检查 Python
if ! command -v python3 &> /dev/null; then
    log_error "未找到 Python 3，请先安装"
    exit 1
fi
log_info "Python 版本: $(python3 --version)"

# 检查 FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    log_error "未找到 FFmpeg，请先安装"
    log_info "Ubuntu/Debian: sudo apt-get install ffmpeg"
    log_info "CentOS/RHEL: sudo yum install ffmpeg"
    log_info "macOS: brew install ffmpeg"
    exit 1
fi
log_info "FFmpeg 版本: $(ffmpeg -version | head -n1)"

# ============ 步骤 2: 拉取最新代码 ============
log_info "拉取最新代码..."

if [ -d "$PROJECT_DIR/.git" ]; then
    cd "$PROJECT_DIR"
    git pull
else
    log_warn "项目目录不存在或不是 Git 仓库"
    log_info "请先克隆代码: git clone <your-repo-url> $PROJECT_DIR"
    exit 1
fi

# ============ 步骤 3: 创建虚拟环境 ============
log_info "设置 Python 虚拟环境..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    log_info "虚拟环境已创建"
else
    log_info "虚拟环境已存在，跳过创建"
fi

# ============ 步骤 4: 安装依赖 ============
log_info "安装 Python 依赖包..."

source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

# ============ 步骤 5: 配置环境变量 ============
log_info "配置环境变量..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        log_warn "已创建 .env 文件，请编辑并填写 API 密钥"
        log_warn "编辑命令: nano .env"
    else
        log_warn "未找到 .env 文件，请手动创建并配置 API 密钥"
    fi
else
    log_info ".env 文件已存在"
fi

# 设置 LangGraph 标志
if [ "$USE_LANGGRAPH" = true ]; then
    export USE_LANGGRAPH=true
    log_info "✅ LangGraph v2 工作流已启用"
else
    export USE_LANGGRAPH=false
    log_info "使用传统工作流（v1）"
fi

# ============ 步骤 6: 创建日志目录 ============
log_info "创建日志目录..."

if [ ! -d "$LOG_DIR" ]; then
    sudo mkdir -p "$LOG_DIR"
    sudo chown -R $(whoami):$(whoami) "$LOG_DIR"
    log_info "日志目录已创建: $LOG_DIR"
fi

# ============ 步骤 7: 停止旧服务 ============
log_info "检查并停止旧服务..."

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p $OLD_PID > /dev/null 2>&1; then
        log_info "停止旧服务 (PID: $OLD_PID)..."
        kill $OLD_PID
        sleep 2
    fi
    rm -f "$PID_FILE"
fi

# 检查端口占用
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    log_warn "端口 $PORT 已被占用，尝试终止..."
    sudo kill $(lsof -t -i:$PORT) 2>/dev/null || true
    sleep 2
fi

# ============ 步骤 8: 运行测试（可选）============
if [ "$USE_LANGGRAPH" = true ]; then
    log_info "运行 LangGraph 验证测试..."
    if python test_langgraph.py; then
        log_info "✅ 所有测试通过"
    else
        log_error "测试失败，请检查配置"
        exit 1
    fi
fi

# ============ 步骤 9: 启动服务 ============
log_info "启动 SonicVideo 服务..."

# 后台启动服务
nohup uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 2 \
    > "$LOG_DIR/sonicvideo.log" 2>&1 &

# 保存 PID
echo $! > "$PID_FILE"

# 等待服务启动
sleep 3

# ============ 步骤 10: 验证服务 ============
log_info "验证服务状态..."

if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
    log_info "✅ 服务启动成功！"
    log_info ""
    log_info "=========================================="
    log_info "  SonicVideo 部署信息"
    log_info "=========================================="
    log_info "服务地址: http://0.0.0.0:$PORT"
    log_info "API 文档: http://0.0.0.0:$PORT/docs"
    log_info "PID 文件: $PID_FILE"
    log_info "日志文件: $LOG_DIR/sonicvideo.log"
    log_info "工作流版本: $([ "$USE_LANGGRAPH" = true ] && echo "v2 (LangGraph)" || echo "v1 (Legacy)")"
    log_info ""
    log_info "管理命令:"
    log_info "  查看日志: tail -f $LOG_DIR/sonicvideo.log"
    log_info "  停止服务: kill \$(cat $PID_FILE)"
    log_info "  重启服务: ./deploy.sh --port $PORT $([ "$USE_LANGGRAPH" = true ] && echo "--langgraph")"
    log_info "=========================================="

    # 测试健康检查
    if curl -s http://localhost:$PORT/ > /dev/null; then
        log_info "✅ 健康检查通过"
    else
        log_warn "健康检查失败，请检查日志"
    fi
else
    log_error "服务启动失败，请检查日志: $LOG_DIR/sonicvideo.log"
    exit 1
fi

exit 0
