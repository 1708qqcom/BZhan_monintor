# DEVLOG - B站UP主视频监控服务

开发过程日记，记录决策上下文和技术细节。

---

## 2026-08-02

### 实现：完成初步功能开发（v2.2）

**做了什么**
- 完成Web管理后台开发（FastAPI + Jinja2）
- 实现所有Web后端API（UP主、视频、配置、登录）
- 实现所有前端页面（仪表盘、UP主管理、推送历史、配置管理、登录管理）
- 集成SQLite数据库（WAL模式）
- 编写数据库迁移脚本（JSON → SQLite）
- 编写数据更新脚本（头像、播放量）
- 编写单元测试（feishu、scheduler）

**为什么这样做**
- 个人工具无需React复杂前端，Jinja2模板足够
- SQLite轻量级数据库，WAL模式支持并发读写
- Swagger UI提供API文档，无需单独维护
- 数据迁移脚本确保历史数据不丢失

**技术决策**
- 选择Jinja2而非React：开发速度快、无需构建、个人使用足够
- 选择SQLite WAL模式：支持并发读写、性能优秀
- 选择Tailwind CSS CDN：无需构建、快速开发

**关键文件**
- `src/web.py` — FastAPI应用主文件
- `src/api/*.py` — API路由模块
- `src/database.py` — 数据库管理模块
- `templates/*.html` — Jinja2模板文件
- `static/js/main.js` — 前端交互脚本
- `scripts/migrate_json_to_sqlite.py` — 数据迁移脚本

---

### 实现：扫码登录功能（v2.1）

**做了什么**
- 参考 yutto 项目重构扫码登录实现
- 替换二维码库：`qrcode + pillow` → `segno`
- 修正 B站扫码登录 API 端点：`/check` → `/poll`
- 添加必要参数：`source=main-fe-header`
- 重构 Cookie 提取流程：请求 redirect_url → 从 cookie jar 提取
- 优化轮询逻辑：使用 `time.monotonic()` 计时，状态变化时才输出日志

**为什么这样做**
- yutto 是成熟的 B站下载工具，其扫码登录实现经过验证
- segno 库的终端二维码输出更紧凑，一行代码即可完成
- Web 端 API 比 TV 端 API 更稳定，返回数据更完整
- 请求 redirect_url 是必要的，让服务器在响应中设置 Cookie

**踩坑**
- 初始使用 `/qrcode/check` 端点，登录成功后无法获取 Cookie
- 直接从响应体解析 Cookie 字符串失败，B站实际不返回该字段
- 需要请求 redirect_url 让 Cookie 写入 session.cookies

**参考**
- yutto 源码：`E:\python3\Lib\site-packages\yutto\login.py`
- 关键状态码：`86101`(未扫描) / `86090`(已扫描) / `0`(成功) / `86038`(过期)

---

### 实现：新增Web管理后台功能（v2.0）

**做了什么**
- PRD升级到v2.0，新增Web管理后台功能规格
- 技术栈新增：FastAPI（后端）、React + TypeScript（前端）、SQLite（数据库）、Tailwind CSS（样式）
- 架构设计改为前后端分离架构
- 数据存储从JSON文件改为SQLite数据库
- 定义Web后端API接口（UP主、视频、配置、登录等）
- 设计数据库表结构（ups、videos、config、auth）
- 设计Web界面原型（仪表盘、UP主管理、推送历史、配置管理、登录管理）
- 更新开发计划为5个Phase

**为什么这样做**
- 用户需要可视化管理界面，便于查看监控状态、管理UP主、查看推送历史
- 前后端分离架构便于独立开发和部署
- SQLite轻量级数据库足够支撑个人使用场景，无需引入MySQL等重型数据库
- FastAPI性能优秀、开发效率高、自带API文档
- React生态成熟，组件化开发便于维护

**技术决策**
- 选择SQLite而非JSON：支持复杂查询、事务、并发访问
- 选择FastAPI而非Flask：自带OpenAPI文档、性能更好、类型提示友好
- 选择React而非Vue：生态更丰富、TypeScript支持更好
- 选择Tailwind CSS：快速开发、无需手写CSS

---

### 实现：项目代码框架搭建

**做了什么**
- 创建项目目录结构：config/data/src/logs/Archive/
- 创建配置文件模板：config/settings.yaml
- 创建Python模块骨架：src/login.py, bilibili.py, feishu.py, scheduler.py
- 创建主入口：main.py（含命令行参数解析）
- 创建systemd服务配置：bilibili-monitor.service
- 创建项目文档：README.md

**为什么这样做**
- 遵循Python项目标准结构，便于后续扩展
- 配置与代码分离，便于部署时修改配置
- 模块化设计，各司其职，降低耦合
- systemd作为进程守护，确保服务稳定性

**技术决策**
- 选择Python而非Node.js：requests库调用HTTP API更简洁，B站相关生态更成熟
- 选择JSON文件存储而非数据库：数据量小（<50人，<1000条历史记录），无需引入数据库复杂度
- 选择飞书群机器人Webhook而非开放平台应用：个人使用场景，无需企业权限申请流程

---

### 文档：Structured Vibe 初始化

**做了什么**
- 创建PRD v1.0草案：完整功能规格和技术方案
- 创建CHANGELOG初始版本
- 创建DEVLOG本条记录
- 创建TODO初始清单

**为什么这样做**
- 遵循Structured Vibe规范，确保文档体系完整
- PRD草案供用户审阅，确认需求理解无误
- 为后续开发提供清晰的任务清单