# B站UP主视频监控服务

自动监控B站关注的UP主新视频发布，通过飞书推送通知，提供Web管理后台。

## 功能特性

### 核心功能
- 扫码登录B站账号
- 自动同步关注列表
- 定时检查新视频（默认30分钟）
- 飞书群机器人推送通知
- systemd进程守护（崩溃自动重启）

### Web管理后台
- **仪表盘**：监控状态概览、最近推送记录
- **UP主管理**：查看、添加、移除监控UP主
- **推送历史**：历史推送记录查询
- **配置管理**：修改检查间隔、飞书Webhook等
- **登录管理**：查看登录状态、重新登录

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+ / FastAPI |
| 前端 | Jinja2模板 / Tailwind CSS CDN / 原生JavaScript |
| 数据库 | SQLite (WAL模式) |
| 推送 | 飞书群机器人 Webhook |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

#### 方式一：Web服务模式（推荐）

```bash
# 启动Web服务
python main.py --web

# 访问 http://localhost:8000
# 默认密码: 123456
```

#### 方式二：监控服务模式

```bash
# 首次使用需要扫码登录
python main.py --login

# 启动监控服务
python main.py
```

### 3. 配置飞书Webhook

1. 在飞书群中添加群机器人
2. 获取Webhook地址
3. 在Web管理后台的"配置管理"页面填入Webhook地址
4. 点击"测试推送"验证配置

## Web管理后台使用指南

### 登录

- 访问 `http://localhost:8000`
- 输入管理密码：`123456`（可在代码中修改）

### 仪表盘

- 查看监控UP主数量
- 查看今日推送数量
- 查看最近推送记录

### UP主管理

- 查看所有监控中的UP主
- 搜索UP主（按名称或ID）
- 添加新的UP主到监控列表
- 移除不需要的UP主

### 推送历史

- 查看历史推送记录
- 按UP主筛选
- 按日期范围筛选
- 分页浏览

### 配置管理

- 修改检查间隔（最小5分钟）
- 修改最大监控UP主数量
- 配置飞书Webhook地址
- 测试推送功能

### B站登录管理

- 查看当前登录状态
- 查看Cookie过期时间
- 扫码重新登录

## 项目结构

```
monitor_onlineVideo/
├── config/              # 配置文件
│   └── settings.yaml    # 系统配置
├── data/                # 数据文件
│   ├── monitor.db       # SQLite数据库
│   └── video_history.json
├── src/                 # Python源码模块
│   ├── bilibili.py      # B站API封装
│   ├── feishu.py        # 飞书推送
│   ├── scheduler.py     # 定时调度
│   ├── login.py         # 扫码登录
│   ├── database.py      # 数据库管理
│   ├── models.py        # 数据模型
│   ├── exceptions.py    # 异常定义
│   ├── web.py           # FastAPI应用
│   └── api/             # API路由
│       ├── ups.py       # UP主管理API
│       ├── videos.py    # 视频历史API
│       ├── config.py    # 配置管理API
│       └── login.py     # 登录管理API
├── templates/           # Jinja2模板
│   ├── base.html        # 基础布局
│   ├── login.html       # 登录页面
│   ├── dashboard.html   # 仪表盘
│   ├── ups.html         # UP主管理
│   ├── videos.html      # 推送历史
│   ├── config.html      # 配置管理
│   └── bilibili_login.html # B站登录
├── static/              # 静态文件
│   ├── js/
│   │   └── main.js      # 前端交互脚本
│   └── css/
├── logs/                # 运行日志
├── main.py              # 主入口
└── requirements.txt     # Python依赖
```

## API文档

启动Web服务后，访问以下地址查看API文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 部署到服务器

### 快速部署（推荐）

使用一键部署脚本：

```bash
# 下载部署脚本
curl -O https://your-domain.com/deploy.sh

# 执行部署
sudo bash deploy.sh
```

### 手动部署

详细部署步骤请参考：[部署指南](deploy/DEPLOY.md)

### 部署后配置

1. **B站账号登录**
   - 访问 Web 管理后台
   - 进入"登录管理"页面
   - 扫码登录B站账号

2. **配置飞书推送**
   - 在飞书群添加群机器人
   - 复制 Webhook 地址
   - 在"配置管理"页面填入并测试

3. **同步关注列表**
   - 在"UP主管理"页面点击"同步关注"

### 服务管理

```bash
# 查看服务状态
sudo systemctl status bilibili-monitor

# 查看日志
sudo journalctl -u bilibili-monitor -f

# 重启服务
sudo systemctl restart bilibili-monitor
```