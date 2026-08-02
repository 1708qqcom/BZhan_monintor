#!/bin/bash

# B站UP主视频监控服务 - 一键部署脚本
# 适用于 Ubuntu 20.04+ 系统

set -e

# ==================== 配置项 ====================
PROJECT_NAME="monitor_onlineVideo"
PROJECT_DIR="/opt/${PROJECT_NAME}"
SERVICE_NAME="bilibili-monitor"
PYTHON_VERSION="3.10"
REPO_URL="<repository-url>"  # 替换为实际仓库地址

# ==================== 颜色输出 ====================
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

# ==================== 检查 root 权限 ====================
if [ "$EUID" -ne 0 ]; then
    log_error "请使用 root 权限运行此脚本"
    log_info "使用: sudo bash deploy.sh"
    exit 1
fi

# ==================== 检查系统版本 ====================
log_info "检查系统环境..."

if [ ! -f /etc/os-release ]; then
    log_error "无法检测系统版本，仅支持 Ubuntu 20.04+"
    exit 1
fi

. /etc/os-release

if [ "$ID" != "ubuntu" ]; then
    log_warn "此脚本主要针对 Ubuntu 系统优化，其他系统可能需要调整"
fi

# ==================== 安装系统依赖 ====================
log_info "更新软件包索引..."
apt update

log_info "安装系统依赖..."
apt install -y python3 python3-pip python3-venv git curl

# ==================== 检查 Python 版本 ====================
PYTHON_BIN="python3"

# 检查 Python 版本
PYTHON_VERSION_ACTUAL=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION_ACTUAL | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION_ACTUAL | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    log_error "Python 版本过低: $PYTHON_VERSION_ACTUAL，需要 3.10+"
    exit 1
fi

log_info "Python 版本: $PYTHON_VERSION_ACTUAL ✓"

# ==================== 克隆项目 ====================
if [ -d "$PROJECT_DIR" ]; then
    log_warn "项目目录已存在: $PROJECT_DIR"
    read -p "是否删除并重新安装? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "停止旧服务..."
        systemctl stop $SERVICE_NAME 2>/dev/null || true
        systemctl disable $SERVICE_NAME 2>/dev/null || true

        log_info "删除旧项目目录..."
        rm -rf $PROJECT_DIR
    else
        log_error "部署已取消"
        exit 1
    fi
fi

log_info "克隆项目到 $PROJECT_DIR..."
git clone $REPO_URL $PROJECT_DIR

# ==================== 创建虚拟环境 ====================
log_info "创建 Python 虚拟环境..."
cd $PROJECT_DIR
python3 -m venv venv

log_info "激活虚拟环境..."
source venv/bin/activate

# ==================== 安装 Python 依赖 ====================
log_info "安装 Python 依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# ==================== 创建必要目录 ====================
log_info "创建数据和日志目录..."
mkdir -p data logs config

# ==================== 配置 systemd 服务 ====================
log_info "配置 systemd 服务..."
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=Bilibili UP Monitor Service (Web + Monitor)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${PROJECT_DIR}/venv/bin:$PATH"
ExecStart=${PROJECT_DIR}/venv/bin/python main.py --web
Restart=always
RestartSec=10
StandardOutput=append:${PROJECT_DIR}/logs/monitor.log
StandardError=append:${PROJECT_DIR}/logs/monitor.log

[Install]
WantedBy=multi-user.target
EOF

# 重新加载 systemd
systemctl daemon-reload

# ==================== 启动服务 ====================
log_info "启动服务..."
systemctl start $SERVICE_NAME
systemctl enable $SERVICE_NAME

# ==================== 检查服务状态 ====================
sleep 2

if systemctl is-active --quiet $SERVICE_NAME; then
    log_info "服务启动成功 ✓"
else
    log_error "服务启动失败"
    log_info "查看日志: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

# ==================== 显示访问信息 ====================
SERVER_IP=$(curl -s https://ipinfo.io/ip 2>/dev/null || echo "<服务器IP>")

echo ""
echo "========================================"
log_info "部署完成!"
echo "========================================"
echo ""
echo "Web 管理后台: http://${SERVER_IP}:3231"
echo "API 文档:     http://${SERVER_IP}:3231/docs"
echo "管理密码:     123456 (请及时修改)"
echo ""
echo "常用命令:"
echo "  查看状态:   sudo systemctl status $SERVICE_NAME"
echo "  查看日志:   sudo journalctl -u $SERVICE_NAME -f"
echo "  重启服务:   sudo systemctl restart $SERVICE_NAME"
echo ""
echo "后续步骤:"
echo "  1. 访问 Web 管理后台"
echo "  2. 在「登录管理」页面扫码登录B站账号"
echo "  3. 在「配置管理」页面配置飞书 Webhook"
echo "  4. 在「UP主管理」页面同步关注列表"
echo ""