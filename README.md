# B站UP主视频监控服务

自动监控B站关注的UP主新视频发布，通过飞书推送通知。

## 功能特性

- 扫码登录B站账号
- 自动同步关注列表
- 定时检查新视频（默认30分钟）
- 飞书群机器人推送通知
- systemd进程守护（崩溃自动重启）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 扫码登录

```bash
python main.py --login
```

终端会显示二维码，用B站App扫码授权。

### 3. 配置飞书Webhook

编辑 `config/settings.yaml`，填入飞书群机器人Webhook地址。

### 4. 启动服务

```bash
python main.py
```

## 部署到服务器

详见 PRD 文档中的部署章节。

## 项目结构

```
monitor_onlineVideo/
├── config/          # 配置文件
├── data/            # 数据存储
├── src/             # 源码模块
├── logs/            # 运行日志
├── Archive/         # 文档归档
├── main.py          # 主入口
└── requirements.txt # 依赖清单
```