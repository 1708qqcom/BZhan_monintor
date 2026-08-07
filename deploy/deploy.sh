#!/bin/bash
# B站UP主视频监控服务 - 部署脚本
# 支持 install（首次部署）/ update（CD 增量更新）两种模式
# 适用 Ubuntu 20.04+ / Python 3.10+

set -euo pipefail

# ==================== 常量配置 ====================
PROJECT_NAME="monitor_onlineVideo"
PROJECT_DIR="/my_web/BZhan_monintor"
SERVICE_NAME="bilibili-monitor"
VENV_DIR="${PROJECT_DIR}/venv"
PYTHON_BIN="python3"

# 健康检查
HEALTH_URL="http://localhost:3231/api/health"
HEALTH_TIMEOUT=30        # 最长等待秒数
HEALTH_INTERVAL=2        # 探活间隔秒数

# 运行时目录（更新时需备份/恢复，避免被 git 覆盖）
RUNTIME_DIRS=("data" "logs" "config/bilibili_cookies.json" "config/settings.yaml")
BACKUP_DIR="/tmp/${PROJECT_NAME}_backup_$$"   # $$ 为当前 PID，保证唯一

# ==================== 颜色输出 ====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# ==================== 用法说明 ====================
usage() {
    cat <<EOF
用法: bash deploy.sh <install|update> [选项]

子命令:
  install   首次部署：克隆仓库 -> venv -> 装依赖 -> systemd -> 启动
  update    增量更新：备份运行时 -> 拉代码 -> 恢复 -> 重启 -> 健康检查

install 选项:
  REPO_URL=<git地址>   必填，通过环境变量传入仓库地址

示例:
  sudo REPO_URL=https://github.com/xxx/yyy.git bash deploy.sh install
  sudo bash deploy.sh update
EOF
}

# ==================== 前置检查 ====================
check_prerequisites() {
    if [ "$EUID" -ne 0 ]; then
        log_error "需要 root 权限，请使用 sudo"
        exit 1
    fi

    if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
        log_error "未找到 ${PYTHON_BIN}，请先安装 Python 3.10+"
        exit 1
    fi

    local py_version
    py_version=$(${PYTHON_BIN} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    local py_major py_minor
    py_major=${py_version%%.*}
    py_minor=${py_version#*.}
    if [ "$py_major" -lt 3 ] || { [ "$py_major" -eq 3 ] && [ "$py_minor" -lt 10 ]; }; then
        log_error "Python 版本过低: ${py_version}，需要 3.10+"
        exit 1
    fi
    log_info "Python 版本: ${py_version} ✓"
}

# ==================== systemd 单元写入 ====================
write_systemd_unit() {
    log_info "写入 systemd 服务单元..."
    cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Bilibili UP Monitor Service (Web + Monitor)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${VENV_DIR}/bin:\$PATH"
ExecStart=${VENV_DIR}/bin/python main.py --web
Restart=always
RestartSec=10
StandardOutput=append:${PROJECT_DIR}/logs/monitor.log
StandardError=append:${PROJECT_DIR}/logs/monitor.log

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
}

# ==================== 健康检查（带重试） ====================
# 返回 0 表示服务健康，非 0 表示超时未就绪
wait_for_health() {
    log_info "健康检查: ${HEALTH_URL}（最长等待 ${HEALTH_TIMEOUT}s）"
    local elapsed=0
    while [ "$elapsed" -lt "$HEALTH_TIMEOUT" ]; do
        if curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
            log_info "服务健康检查通过 ✓"
            return 0
        fi
        sleep "$HEALTH_INTERVAL"
        elapsed=$((elapsed + HEALTH_INTERVAL))
        log_warn "等待服务就绪... (${elapsed}s)"
    done
    log_error "服务在 ${HEALTH_TIMEOUT}s 内未就绪"
    return 1
}

# ==================== 重启并探活 ====================
restart_and_verify() {
    log_info "重启服务..."
    systemctl restart "$SERVICE_NAME"

    if ! wait_for_health; then
        log_error "服务启动失败，最近日志:"
        journalctl -u "$SERVICE_NAME" -n 30 --no-pager >&2 || true
        return 1
    fi
    return 0
}

# ==================== 首次部署 ====================
do_install() {
    local repo_url="${REPO_URL:-}"
    if [ -z "$repo_url" ]; then
        log_error "install 模式需通过环境变量 REPO_URL 指定仓库地址"
        log_info "示例: sudo REPO_URL=https://github.com/xxx/yyy.git bash deploy.sh install"
        exit 1
    fi

    check_prerequisites

    log_info "安装系统依赖..."
    apt update -y
    apt install -y python3 python3-pip python3-venv git curl

    if [ -d "$PROJECT_DIR" ]; then
        log_error "项目目录已存在: ${PROJECT_DIR}，如需重装请先手动删除或改用 update"
        exit 1
    fi

    log_info "克隆项目: ${repo_url} -> ${PROJECT_DIR}"
    git clone "$repo_url" "$PROJECT_DIR"
    cd "$PROJECT_DIR"

    log_info "创建虚拟环境..."
    python3 -m venv venv
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"

    log_info "安装 Python 依赖..."
    pip install --upgrade pip
    pip install -r requirements.txt

    log_info "创建运行时目录..."
    mkdir -p data logs config

    write_systemd_unit

    log_info "启动服务..."
    systemctl enable "$SERVICE_NAME"
    if ! restart_and_verify; then
        log_error "首次部署启动失败，请检查日志后重试"
        exit 1
    fi

    print_access_info
}

# ==================== 备份运行时数据 ====================
backup_runtime() {
    log_info "备份运行时数据 -> ${BACKUP_DIR}"
    mkdir -p "$BACKUP_DIR"
    local item
    for item in "${RUNTIME_DIRS[@]}"; do
        local src="${PROJECT_DIR}/${item}"
        if [ -e "$src" ]; then
            # 保留相对路径结构
            mkdir -p "${BACKUP_DIR}/$(dirname "$item")"
            cp -a "$src" "${BACKUP_DIR}/${item}"
            log_info "  已备份: ${item}"
        fi
    done
}

# ==================== 恢复运行时数据 ====================
restore_runtime() {
    log_info "恢复运行时数据 <- ${BACKUP_DIR}"
    local item
    for item in "${RUNTIME_DIRS[@]}"; do
        local backup="${BACKUP_DIR}/${item}"
        if [ -e "$backup" ]; then
            local dst="${PROJECT_DIR}/${item}"
            rm -rf "$dst"
            mkdir -p "${PROJECT_DIR}/$(dirname "$item")"
            cp -a "$backup" "$dst"
            log_info "  已恢复: ${item}"
        fi
    done
}

# ==================== 更新回滚 ====================
rollback_update() {
    log_error "部署失败，执行回滚..."
    cd "$PROJECT_DIR"
    # ORIG_HEAD 由 git reset 保存，指向上一次 HEAD
    if git rev-parse --verify ORIG_HEAD >/dev/null 2>&1; then
        log_warn "回退到上一个提交: $(git rev-parse --short ORIG_HEAD)"
        git reset --hard ORIG_HEAD
    else
        log_warn "无 ORIG_HEAD，跳过代码回滚"
    fi
    restore_runtime
    systemctl restart "$SERVICE_NAME" || true
    log_warn "回滚完成，服务已尝试重启，请人工核查"
}

# ==================== 增量更新（CD 调用） ====================
do_update() {
    check_prerequisites

    if [ ! -d "${PROJECT_DIR}/.git" ]; then
        log_error "项目目录未初始化 git: ${PROJECT_DIR}，请先用 install 部署"
        exit 1
    fi

    cd "$PROJECT_DIR"

    # 1. 记录更新前提交（用于回滚）
    local prev_commit
    prev_commit=$(git rev-parse HEAD)
    log_info "当前提交: $(git rev-parse --short HEAD)"

    # 2. 备份运行时数据
    backup_runtime

    # 3. 拉取最新代码（强制对齐远程，避免本地改动冲突）
    log_info "拉取最新代码..."
    git fetch origin main
    git reset --hard origin/main

    # 4. 恢复运行时数据（覆盖被 git 还原的 data/logs/config）
    restore_runtime

    # 5. 更新依赖
    log_info "更新 Python 依赖..."
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    pip install -r requirements.txt

    # 6. 确保单元文件最新（防止 ExecStart 漂移）
    write_systemd_unit

    # 7. 重启并探活；失败则回滚
    if ! restart_and_verify; then
        rollback_update
        exit 1
    fi

    # 8. 清理备份
    rm -rf "$BACKUP_DIR"
    log_info "更新完成: ${prev_commit:0:7} -> $(git rev-parse --short HEAD)"
    print_access_info
}

# ==================== 访问信息 ====================
print_access_info() {
    local server_ip
    server_ip=$(curl -s https://ipinfo.io/ip 2>/dev/null || echo "<服务器IP>")
    echo ""
    echo "========================================"
    log_info "部署完成!"
    echo "========================================"
    echo "Web 管理后台: http://${server_ip}:3231"
    echo "API 文档:     http://${server_ip}:3231/docs"
    echo "健康检查:     http://${server_ip}:3231/api/health"
    echo ""
    echo "常用命令:"
    echo "  查看状态: sudo systemctl status ${SERVICE_NAME}"
    echo "  查看日志: sudo journalctl -u ${SERVICE_NAME} -f"
    echo "  重启服务: sudo systemctl restart ${SERVICE_NAME}"
    echo ""
}

# ==================== 主入口 ====================
main() {
    local mode="${1:-}"
    case "$mode" in
        install) do_install ;;
        update)  do_update ;;
        -h|--help|"") usage ;;
        *)
            log_error "未知子命令: ${mode}"
            usage
            exit 1
            ;;
    esac
}

main "$@"
