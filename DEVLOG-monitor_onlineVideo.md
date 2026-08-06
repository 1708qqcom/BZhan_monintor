# DEVLOG - B站UP主视频监控服务

开发过程日记，记录决策上下文和技术细节。

---

## 2026-08-06

### 实现：用户引导流程（v2.3）

**做了什么**
- 新增 `user_onboarding` 数据库表及完整 CRUD 方法（`init_onboarding_progress`、`get_onboarding_progress`、`update_onboarding_step`）
- 新增引导流程 API 模块 `src/api/onboarding.py`（3个端点：获取状态、完成步骤、跳过步骤）
- 新增引导页面模板 `templates/onboarding.html`（3步向导 + 进度指示器）
- 新增前端交互脚本 `static/js/onboarding.js`（步骤切换、B站扫码轮询、飞书配置保存、UP主批量选择）
- 新增数据模型 `OnboardingProgress`、`OnboardingStepRequest`、`OnboardingStatusResponse`
- 注册流程集成：新用户注册后自动初始化引导进度并重定向到 `/onboarding`
- 仪表盘集成：查询引导进度，未完成时显示进度提示卡片（带百分比进度条）
- 编写测试：`test_onboarding_api.py`（API接口测试）、`test_onboarding_db.py`（数据库方法测试）

**为什么这样做**
- 新用户注册后面对空白仪表盘缺乏引导，不知道第一步该做什么
- 3步向导覆盖核心配置路径：B站绑定 → 飞书推送 → UP主选择，降低上手成本
- 每步可跳过，不强制的设计降低用户抵触
- 仪表盘进度卡片作为轻量提醒，避免打断用户正常使用

**技术决策**
- 引导状态存 SQLite 而非 session：跨设备/清除Cookie后仍保留进度，适合长周期使用
- 前端 Vanilla JS 而非框架：页面简单，无构建步骤，与项目整体风格一致
- 步骤完成计算逻辑：`completed or skipped` 都算该步已处理，进度 = 已处理/3 × 100
- 注册时引导初始化失败不阻断注册流程（try-except 包裹），保障核心流程可用

**关键文件**
- `src/database.py` — 新增 user_onboarding 表 + 3个CRUD方法
- `src/api/onboarding.py` — 引导流程 API 端点
- `src/models.py` — 新增引导相关 Pydantic 模型
- `src/web.py` — 注册重定向、仪表盘进度查询、onboarding 页面路由
- `templates/onboarding.html` — 引导页面模板
- `static/js/onboarding.js` — 引导流程交互脚本
- `templates/dashboard.html` — 仪表盘引导进度卡片
- `templates/base.html` — 导航栏登录链接

---

### 实现：飞书推送格式优化

**做了什么**
- 单视频推送：标题从纯文本改为可点击的 markdown 链接格式 `[视频标题](视频链接)`
- 单视频推送和每日摘要列表项添加 🎬 emoji

**为什么这样做**
- 原格式标题不可点击，用户需要手动复制BV号到浏览器打开，体验不流畅
- emoji 前缀增强视觉识别度，与通知内容调性一致

---

### 实现：导航栏未登录状态优化

**做了什么**
- `templates/base.html` 中未登录用户显示"登录"导航链接

**为什么这样做**
- 原实现在未登录状态下用户菜单完全空白，新用户不知道该点哪里登录

---

### 清理：删除废弃临时文档

**做了什么**
- 删除 `temp_video_stats_tracking_design.md`、`temp_video_stats_tracking_requirements.md`、`temp_video_stats_tracking_todo.md`

**为什么这样做**
- 播放量追踪曲线功能未实施，临时设计文档已无参考价值

---

## 2026-08-02

### 实现：完成部署准备工作（v2.2）

**做了什么**
- 创建一键部署脚本 `deploy/deploy.sh`
- 编写详细部署文档 `deploy/DEPLOY.md`
- 更新 systemd 服务配置支持 Web 服务模式
- 更新 README 部署说明

**为什么这样做**
- 一键部署脚本简化服务器安装流程，降低部署门槛
- 详细部署文档覆盖各种场景（手动部署、安全配置、故障排查）
- Web 服务模式提供完整管理界面，无需额外启动监控进程
- systemd 服务使用虚拟环境 Python，避免系统依赖冲突

**技术决策**
- 服务模式选择 Web 而非纯监控：Web 模式集成监控调度器，提供管理界面
- 使用虚拟环境：隔离项目依赖，避免系统 Python 包冲突
- 日志输出到文件：便于排查问题，支持日志轮转

**关键文件**
- `deploy/deploy.sh` — 一键部署脚本
- `deploy/DEPLOY.md` — 部署文档
- `deploy/bilibili-monitor.service` — systemd 服务配置

---

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