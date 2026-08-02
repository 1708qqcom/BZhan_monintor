# Implementation Todo - 飞书推送通知

## Preparation

- [x] 分析现有代码结构
- [x] 理解飞书 Webhook API 文档
- [x] 确认消息卡片格式设计
- [x] 确认配置文件中 Webhook URL 已配置

## Development Tasks

### Task 1: 新增异常类

**文件**: `src/exceptions.py`

- [ ] 在文件末尾添加 `FeishuAPIError` 异常类
- [ ] 包含 message 属性和 `__str__` 方法

### Task 2: 实现核心发送方法

**文件**: `src/feishu.py`

- [ ] 添加 import 语句
  - `import requests`
  - `import logging`
  - `from datetime import datetime`
- [ ] 在 `__init__` 中初始化 logger
- [ ] 实现 `_send_webhook(payload: dict) -> bool`
  - [ ] 检查 webhook_url 是否为空
  - [ ] 发送 POST 请求，设置 timeout=10
  - [ ] 验证 HTTP 状态码（200）
  - [ ] 解析 JSON 响应
  - [ ] 检查飞书返回的 code 字段
  - [ ] 捕获网络异常并记录日志
  - [ ] 返回布尔值表示成功/失败

### Task 3: 实现新视频通知方法

**文件**: `src/feishu.py`

- [ ] 实现 `send_new_video_notification()`
  - [ ] 构造飞书交互式卡片 JSON 结构
  - [ ] 填充 UP主名称、视频标题、链接、发布时间、播放量
  - [ ] 添加"观看视频"按钮链接
  - [ ] 调用 `_send_webhook()` 发送
  - [ ] 记录发送日志
  - [ ] 返回结果

### Task 4: 实现错误告警方法

**文件**: `src/feishu.py`

- [ ] 实现 `send_error_notification()`
  - [ ] 构造红色主题告警卡片 JSON
  - [ ] 填充错误信息和时间戳
  - [ ] 调用 `_send_webhook()` 发送
  - [ ] 记录发送日志
  - [ ] 返回结果

### Task 5: 集成到主程序（可选）

**文件**: `main.py`

- [ ] 在 `start_monitor()` 中导入 FeishuNotifier
- [ ] 从配置读取 webhook_url
- [ ] 初始化 FeishuNotifier 实例
- [ ] 添加测试推送调用（仅用于验证）

## Testing Tasks

### Unit Tests

**文件**: `tests/test_feishu.py`（新建）

- [ ] 创建测试文件
- [ ] 测试 `_format_view_count()` 播放量格式化
  - [ ] 测试小于 10000 的数字
  - [ ] 测试大于 10000 的数字
- [ ] 测试 `_send_webhook()` 使用 mock
  - [ ] 测试成功响应
  - [ ] 测试网络异常
  - [ ] 测试飞书返回错误码
- [ ] 测试消息构造逻辑

### Integration Test

- [ ] 使用真实 Webhook 发送测试消息
- [ ] 验证飞书群收到正确格式的消息
- [ ] 验证按钮链接可正常跳转

## Completion Checklist

- [ ] 代码实现完成，无语法错误
- [ ] 所有方法有正确的类型注解
- [ ] 所有异常被捕获，不会抛出到调用方
- [ ] 日志记录完整（INFO/WARNING/ERROR）
- [ ] 单元测试通过
- [ ] 真实 Webhook 测试通过
- [ ] 更新 TODO-monitor_onlineVideo.md 标记完成
