# CHANGELOG - B站UP主视频监控服务

所有用户可感知的变更记录。

---

## 2026-08-02 — 扫码登录功能实现（v2.1）

**新增**
- 终端二维码显示功能（支持 terminal 和 web 两种模式）
- 扫码状态轮询与 Cookie 自动提取
- Cookie 本地存储与有效性检查

**修改**
- 二维码库从 `qrcode + pillow` 改为 `segno`
- B站扫码登录 API 端点修正为 Web 端接口
- 轮询逻辑改用 `time.monotonic()` 计时，状态变化时才输出日志

**修复**
- 修正扫码成功后无法获取 Cookie 的问题（API 端点错误、Cookie 提取方式错误）

---

## 2026-08-02 — 新增Web管理后台（v2.0）

**新增**
- Web管理后台功能模块（仪表盘、UP主管理、推送历史、配置管理、登录管理）
- Web后端技术栈：FastAPI
- Web前端技术栈：React + TypeScript + Tailwind CSS
- 数据库存储：SQLite（替代JSON文件）
- Web后端API接口定义（UP主、视频、配置、登录等）
- 数据库表结构设计（ups、videos、config、auth）
- Web界面原型设计

**修改**
- 架构设计从单进程改为前后端分离架构
- 数据存储从JSON文件改为SQLite数据库
- 技术栈新增FastAPI、React、SQLite、Tailwind CSS
- 开发计划调整为5个Phase（新增Web后端、Web前端阶段）
- PRD版本从v1.0升级到v2.0
- 范围外功能移除"Web管理界面"和"数据库存储"

---

## 2026-08-02 — 项目初始化（v1.0）

**新增**
- 项目代码框架：main.py 入口 + src 模块结构
- 配置管理：config/settings.yaml + YAML加载逻辑
- B站登录模块骨架：扫码登录接口定义
- B站API模块骨架：关注列表、视频列表接口定义
- 飞书推送模块骨架：Webhook推送接口定义
- 定时调度模块骨架：监控循环逻辑框架
- systemd服务配置：bilibili-monitor.service
- 项目文档：README.md + PRD

**待办**
- 实现扫码登录逻辑
- 实现B站API调用
- 实现飞书推送
- 实现定时调度
- SQLite数据库集成
- FastAPI后端开发
- React前端开发
- 服务器部署测试