# CHANGELOG - B站UP主视频监控服务

所有用户可感知的变更记录。

---

## 2026-08-06 — 新增用户引导流程 + 推送格式优化（v2.3）

**新增**
- 新用户3步引导流程：B站扫码登录 → 飞书Webhook配置 → UP主监控选择
- 引导进度API：`GET /api/onboarding/status`、`POST /api/onboarding/complete-step`、`POST /api/onboarding/skip-step`
- `/onboarding` 引导页面（步骤指示器、二维码登录、飞书测试推送、UP主全选）
- 仪表盘引导进度提示卡片（未完成时显示，含百分比进度条）
- 新用户注册后自动跳转引导页面
- 引导流程数据库测试和API测试

**修改**
- 飞书推送通知：视频标题改为可点击链接 + 🎬 emoji
- 飞书每日摘要：列表项添加 🎬 emoji 前缀
- 导航栏：未登录用户显示"登录"链接（替代空白菜单）
- PRD 技术栈修正：React → Jinja2 模板 + Vanilla JS

**修复**
- （无）

**待办**
- 部署上线测试

---

## 2026-08-02 — 完成部署准备工作（v2.2）

**新增**
- 一键部署脚本 `deploy/deploy.sh`（自动化安装流程）
- 详细部署文档 `deploy/DEPLOY.md`（包含完整部署步骤）
- systemd服务配置更新（支持Web服务模式）

**修改**
- README补充部署说明和快速开始指南
- systemd服务从监控模式改为Web服务模式

---

## 2026-08-02 — 完成初步功能开发（v2.2）

**新增**
- 完整的Web管理后台（仪表盘、UP主管理、推送历史、配置管理、登录管理）
- FastAPI后端服务（CORS、日志中间件、Swagger文档）
- Jinja2模板前端（Tailwind CSS CDN、响应式布局）
- Session认证中间件（密码保护）
- SQLite数据库集成（WAL模式、完整CRUD）
- 数据库迁移脚本（JSON历史数据 → SQLite）
- UP主头像更新脚本（从B站API获取最新头像）
- 视频统计更新脚本（从B站API获取播放量）
- 前端交互脚本（main.js）
- 单元测试（feishu、scheduler模块）

**修改**
- 技术栈调整：React SPA → FastAPI + Jinja2 简易页面（个人工具无需复杂前端）
- 数据存储从JSON文件改为SQLite数据库
- Web后端API完整实现（UP主、视频、配置、登录）
- 前端页面完整实现（6个页面模板）

**修复**
- 推送历史页面播放量和推送时间无法显示（数据迁移脚本补全）
- B站图片防盗链导致前端无法渲染头像（添加 referrerpolicy="no-referrer"）
- 飞书测试推送报错（新增 send_message 方法）

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