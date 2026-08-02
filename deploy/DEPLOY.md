# 部署指南

B站UP主视频监控服务 - 服务器部署完整流程。

---

## 一、环境要求

### 服务器配置

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | 1核 | 2核+ |
| 内存 | 512MB | 1GB+ |
| 磁盘 | 10GB | 20GB+ |
| 系统 | Ubuntu 20.04+ | Ubuntu 22.04 LTS |

### 软件依赖

- Python 3.10+
- Git
- systemd

---

## 二、部署方式

### 方式一：一键部署脚本（推荐）

```bash
# 下载部署脚本
curl -O https://your-domain.com/deploy.sh

# 执行部署
bash deploy.sh
```

### 方式二：手动部署

#### 1. 安装系统依赖

```bash
# 更新软件包索引
sudo apt update

# 安装 Python 3.10+ 和 pip
sudo apt install -y python3 python3-pip python3-venv git
```

#### 2. 克隆项目

```bash
# 克隆到 /opt 目录
sudo git clone <repository-url> /opt/monitor_onlineVideo

# 进入项目目录
cd /opt/monitor_onlineVideo
```

#### 3. 创建 Python 虚拟环境

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 4. 配置服务

```bash
# 复制 systemd 服务配置
sudo cp deploy/bilibili-monitor.service /etc/systemd/system/

# 重新加载 systemd 配置
sudo systemctl daemon-reload
```

#### 5. 启动服务

```bash
# 启动服务
sudo systemctl start bilibili-monitor

# 设置开机自启
sudo systemctl enable bilibili-monitor

# 查看服务状态
sudo systemctl status bilibili-monitor
```

---

## 三、服务管理

### 基础命令

```bash
# 启动服务
sudo systemctl start bilibili-monitor

# 停止服务
sudo systemctl stop bilibili-monitor

# 重启服务
sudo systemctl restart bilibili-monitor

# 查看服务状态
sudo systemctl status bilibili-monitor

# 查看日志
sudo journalctl -u bilibili-monitor -f
```

### 日志文件

日志文件位置：`/opt/monitor_onlineVideo/logs/monitor.log`

```bash
# 实时查看日志
tail -f /opt/monitor_onlineVideo/logs/monitor.log

# 查看最近100行
tail -n 100 /opt/monitor_onlineVideo/logs/monitor.log
```

---

## 四、首次配置

### 1. B站账号登录

服务启动后，需要扫码登录B站账号：

#### 方式一：Web界面登录（推荐）

1. 访问 `http://<服务器IP>:3231`
2. 使用管理密码登录（默认：`123456`）
3. 进入"登录管理"页面
4. 点击"获取二维码"
5. 使用B站App扫描二维码
6. 等待登录成功提示

#### 方式二：命令行登录

```bash
# 进入项目目录
cd /opt/monitor_onlineVideo

# 激活虚拟环境
source venv/bin/activate

# 执行登录
python main.py --login
```

### 2. 飞书Webhook配置

1. 在飞书群中添加群机器人
   - 群设置 → 群机器人 → 添加机器人 → 自定义机器人
   - 设置机器人名称和描述
   - 复制 Webhook 地址

2. 在Web管理后台配置
   - 访问 `http://<服务器IP>:3231`
   - 进入"配置管理"页面
   - 填入飞书Webhook地址
   - 点击"测试推送"验证配置
   - 点击"保存配置"

### 3. 同步关注列表

登录成功后，在"UP主管理"页面点击"同步关注"按钮，自动从B站账号同步关注列表。

---

## 五、安全配置

### 1. 修改管理密码

编辑 `src/web.py`，修改 `AUTH_PASSWORD` 变量：

```python
AUTH_PASSWORD = "your-strong-password"
```

### 2. 配置防火墙

```bash
# 开放 Web 服务端口
sudo ufw allow 3231/tcp

# 启用防火墙
sudo ufw enable
```

### 3. 配置HTTPS（可选）

推荐使用 Nginx 反向代理 + Let's Encrypt 证书：

```bash
# 安装 Nginx
sudo apt install -y nginx certbot python3-certbot-nginx

# 配置 Nginx 反向代理
sudo nano /etc/nginx/sites-available/monitor

# 内容：
# server {
#     listen 80;
#     server_name your-domain.com;
#
#     location / {
#         proxy_pass http://127.0.0.1:3231;
#         proxy_set_header Host $host;
#         proxy_set_header X-Real-IP $remote_addr;
#     }
# }

# 启用配置
sudo ln -s /etc/nginx/sites-available/monitor /etc/nginx/sites-enabled/

# 获取 SSL 证书
sudo certbot --nginx -d your-domain.com

# 重启 Nginx
sudo systemctl restart nginx
```

---

## 六、监控与维护

### 健康检查

```bash
# 健康检查接口
curl http://localhost:3231/api/health
```

### 数据库备份

```bash
# 备份数据库
cp /opt/monitor_onlineVideo/data/monitor.db /opt/monitor_onlineVideo/data/monitor.db.backup

# 或使用定时任务自动备份
# 编辑 crontab
crontab -e

# 添加每天凌晨3点备份
0 3 * * * cp /opt/monitor_onlineVideo/data/monitor.db /opt/monitor_onlineVideo/data/backup/monitor-$(date +\%Y\%m\%d).db
```

### 日志清理

日志文件自动轮转，保留最近5个文件（可在 `config/settings.yaml` 修改）。

手动清理：

```bash
# 清理7天前的日志
find /opt/monitor_onlineVideo/logs -name "*.log" -mtime +7 -delete
```

---

## 七、故障排查

### 服务无法启动

```bash
# 查看详细错误日志
sudo journalctl -u bilibili-monitor -n 50

# 检查Python依赖
cd /opt/monitor_onlineVideo
source venv/bin/activate
pip list
```

### Cookie过期

现象：推送停止，日志提示"Cookie已过期"

解决：
1. 访问Web管理后台
2. 进入"登录管理"页面
3. 点击"重新登录"
4. 扫码授权

### 飞书推送失败

1. 检查Webhook地址是否正确
2. 检查网络是否能访问飞书API
3. 在配置管理页面点击"测试推送"验证

### 数据库锁定

现象：日志提示"database is locked"

解决：
```bash
# 重启服务
sudo systemctl restart bilibili-monitor
```

---

## 八、更新升级

### 手动更新

```bash
# 进入项目目录
cd /opt/monitor_onlineVideo

# 停止服务
sudo systemctl stop bilibili-monitor

# 拉取最新代码
git pull origin main

# 激活虚拟环境
source venv/bin/activate

# 更新依赖
pip install -r requirements.txt

# 启动服务
sudo systemctl start bilibili-monitor
```

---

## 九、卸载

```bash
# 停止并禁用服务
sudo systemctl stop bilibili-monitor
sudo systemctl disable bilibili-monitor

# 删除服务配置
sudo rm /etc/systemd/system/bilibili-monitor.service

# 删除项目目录
sudo rm -rf /opt/monitor_onlineVideo

# 重新加载 systemd
sudo systemctl daemon-reload
```

---

## 十、常见问题

**Q: 服务启动后访问不了Web界面？**
A: 检查防火墙是否开放3231端口，检查服务状态 `systemctl status bilibili-monitor`

**Q: Cookie多久过期？**
A: B站Cookie有效期约30天，过期前会有飞书告警提醒重新登录

**Q: 支持多账号吗？**
A: 当前版本仅支持单个B站账号监控

**Q: 数据库会很大吗？**
A: 50个UP主、每天10条视频记录，一年约18万条记录，数据库约20MB

---

## 十一、技术支持

- GitHub Issues: <repository-url>/issues
- 文档：项目根目录 PRD、README