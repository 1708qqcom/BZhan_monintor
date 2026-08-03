# Feature Requirements

## Background

当前项目的Web服务模式（`python main.py --web`）只提供了管理界面和API功能，缺少后台监控调度器。用户通过Web界面管理监控的UP主，但UP主发布新视频后不会收到飞书推送通知。

核心问题：
- Web服务启动时没有启动 `MonitorScheduler` 调度器
- 监控任务（检查新视频、推送通知）没有运行
- 飞书推送功能完全未生效

## Goal

在Web服务启动时自动启动后台监控任务，实现：

1. Web服务启动后，自动开始监控UP主新视频
2. 检测到新视频时，自动发送飞书推送通知
3. Web服务和监控任务在同一进程运行，共享数据库
4. Web界面可以查看监控状态（上次检查时间、下次检查时间）

## User Story

**As a** 用户

**I want** 启动Web服务后自动监控UP主新视频并推送通知

**So that** 我不需要手动启动两个进程，只需要运行 `python main.py --web` 就能同时获得Web管理界面和推送通知功能

## Functional Requirements

### FR-001: Web服务启动时自动启动监控调度器

**描述**：Web应用生命周期中，在数据库初始化完成后，自动启动监控调度器。

**行为**：
- 检查B站Cookie是否存在且有效
- 如果Cookie无效，记录警告日志，调度器不启动，Web服务正常运行
- 如果Cookie有效，在后台线程中启动 `MonitorScheduler`

### FR-002: 监控调度器在后台线程运行

**描述**：监控任务不能阻塞Web服务的主线程。

**行为**：
- 使用 `threading.Thread` 创建后台线程
- 线程设置为 `daemon=True`，Web服务退出时线程自动终止
- 调度器在后台线程中执行 `scheduler.start()` 的无限循环

### FR-003: 从数据库读取配置

**描述**：监控调度器的配置（检查间隔、飞书Webhook等）从数据库或配置文件读取。

**行为**：
- 飞书Webhook URL优先从数据库 `config` 表读取
- 如果数据库没有，回退到 `config/settings.yaml`
- 检查间隔从数据库配置读取，支持热更新

### FR-004: Web服务关闭时优雅停止调度器

**描述**：Web服务关闭时，调度器需要保存历史记录并退出。

**行为**：
- 监听 `SIGTERM` 信号
- 调用 `scheduler._running = False` 停止循环
- 保存历史记录到数据库
- 记录关闭日志

### FR-005: 增加监控状态API

**描述**：提供API端点查询监控调度器的运行状态。

**行为**：
- `GET /api/monitor/status` 返回：
  - `is_running`: boolean - 调度器是否运行中
  - `last_check_time`: string - 上次检查时间（ISO格式）
  - `next_check_time`: string - 下次检查时间（ISO格式）
  - `check_interval_minutes`: int - 检查间隔（分钟）

## User Flow

### 正常启动流程

1. 用户运行 `python main.py --web`
2. Web服务启动，初始化数据库
3. 检查B站Cookie是否有效
4. 有效：启动后台监控线程
5. 无效：记录警告日志，Web服务正常启动
6. 用户访问 `http://127.0.0.1:3231` 管理UP主
7. 后台线程定时检查新视频并推送

### Cookie过期场景

1. Web服务启动时Cookie有效，监控线程启动
2. 运行一段时间后Cookie过期
3. 监控循环检测到Cookie过期
4. 发送飞书告警通知
5. 监控线程退出，Web服务继续运行
6. 用户重新扫码登录后，需要重启Web服务

## Edge Cases

### EC-001: 未登录B站账号

**场景**：数据库中没有B站Cookie

**处理**：
- Web服务正常启动
- 记录警告日志："未登录B站账号，监控调度器不启动"
- 用户可以访问Web界面，但不会收到推送

### EC-002: Cookie已过期

**场景**：启动时Cookie已过期

**处理**：
- Web服务正常启动
- 调度器验证Cookie失败，记录错误日志
- 监控线程不启动或立即退出

### EC-003: 飞书Webhook未配置

**场景**：飞书Webhook URL为空

**处理**：
- 监控调度器正常启动
- 检测到新视频时，记录警告日志："飞书推送器未初始化，跳过推送"
- 不发送通知，但视频记录保存到数据库

### EC-004: Web服务频繁重启

**场景**：用户频繁重启Web服务

**处理**：
- 每次重启都会重新启动监控线程
- 利用数据库中的历史记录去重，避免重复推送
- 上次检查时间从数据库恢复

## Acceptance Criteria

### AC-001: 启动验证

**Given** 数据库中有有效的B站Cookie
**When** 启动Web服务 `python main.py --web`
**Then** 日志中显示"监控调度器已启动（后台线程）"
**And** 调度器开始定时检查UP主新视频

### AC-002: 推送验证

**Given** 监控的UP主发布了新视频
**And** 监控调度器正在运行
**When** 到达检查时间
**Then** 检测到新视频
**And** 发送飞书推送通知
**And** 数据库中记录 `pushed=true`

### AC-003: 状态查询验证

**Given** 监控调度器正在运行
**When** 访问 `GET /api/monitor/status`
**Then** 返回 `is_running=true`
**And** 返回上次检查时间和下次检查时间

### AC-004: 未登录场景验证

**Given** 数据库中没有B站Cookie
**When** 启动Web服务
**Then** Web服务正常启动
**And** 日志显示"未登录B站账号，监控调度器不启动"
**And** Web界面可以正常访问

### AC-005: 优雅关闭验证

**Given** 监控调度器正在运行
**When** 用户按 `Ctrl+C` 停止Web服务
**Then** 调度器停止当前循环
**And** 保存历史记录到数据库
**And** 日志显示"调度器已停止"