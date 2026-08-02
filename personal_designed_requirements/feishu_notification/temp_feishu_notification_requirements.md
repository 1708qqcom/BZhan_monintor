# Feature Requirements - 飞书推送通知

## Background

B站UP主视频监控服务需要将检测到的新视频信息及时推送给用户。飞书作为主要通知渠道，需要实现群机器人Webhook推送功能。

当前 `src/feishu.py` 模块已搭建类框架，但核心方法 `send_new_video_notification()`、`send_error_notification()`、`_send_webhook()` 均未实现（抛出 `NotImplementedError`）。

## Goal

实现飞书群机器人消息推送功能，支持：
1. 新视频通知推送
2. 错误告警推送
3. 完善的异常处理和日志记录

## User Story

**As a** B站重度用户

**I want** 当关注的UP主发布新视频时，能在飞书群收到及时通知

**So that** 我不会错过任何感兴趣的视频更新

## Functional Requirements

### FR-001: Webhook请求发送

- 使用 HTTP POST 请求发送消息
- 请求体为 JSON 格式
- 超时时间设置为 10 秒
- 返回布尔值表示发送成功/失败

### FR-002: 新视频通知推送

消息内容包含：
- UP主名称
- 视频标题
- 视频链接（可点击）
- 发布时间（格式：YYYY-MM-DD HH:MM）
- 播放量（格式化显示，如 1.2万）

消息格式符合 PRD 定义：
```
📺 【UP主名称】发布了新视频

标题：视频标题
链接：https://www.bilibili.com/video/BVxxxx
发布时间：2026-08-02 14:30
当前播放量：1.2万
```

### FR-003: 错误告警推送

- 使用红色主题区分告警消息
- 包含错误发生时间
- 包含错误简要描述

### FR-004: 异常处理

处理以下异常情况：
- 网络连接失败
- 请求超时
- 飞书API返回错误
- Webhook地址无效

所有异常应：
- 记录到日志
- 不中断主流程
- 返回 False 表示失败

### FR-005: 日志记录

- 发送成功：记录 INFO 日志
- 发送失败：记录 ERROR 日志，包含失败原因

## User Flow

```
监控服务检测到新视频
       ↓
调用 FeishuNotifier.send_new_video_notification()
       ↓
构造飞书交互式卡片 JSON
       ↓
调用 _send_webhook() 发送 POST 请求
       ↓
检查响应状态码和 API code
       ↓
成功：记录日志，返回 True
失败：记录错误日志，返回 False
```

## Edge Cases

| 场景 | 处理方式 |
|------|----------|
| Webhook URL 为空 | 初始化时允许为空，发送时检查并返回 False |
| 播放量为 0 | 显示 "0" 而非空值 |
| 视频标题过长 | 不截断，飞书会自动处理 |
| 网络断开 | 捕获异常，记录日志，返回 False |
| 飞书限流（code: 10049） | 记录警告日志，返回 False |

## Acceptance Criteria

- [ ] `_send_webhook()` 方法可成功发送 POST 请求并处理响应
- [ ] `send_new_video_notification()` 可构造正确的消息卡片并发送
- [ ] `send_error_notification()` 可发送红色主题告警消息
- [ ] 所有网络异常被捕获，不抛出到调用方
- [ ] 日志记录完整（成功/失败都有记录）
- [ ] 可通过单元测试验证核心逻辑
