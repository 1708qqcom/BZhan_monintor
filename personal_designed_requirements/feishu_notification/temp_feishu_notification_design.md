# Technical Design - 飞书推送通知

## Overview

实现 `src/feishu.py` 中未完成的三个方法，使用 `requests` 库发送飞书群机器人 Webhook 请求，采用交互式卡片（Interactive Card）消息格式。

## Architecture

### 模块依赖关系

```
src/feishu.py
    ├── requests (HTTP请求)
    ├── json (JSON序列化)
    └── logging (日志记录)

src/exceptions.py
    └── 新增 FeishuAPIError 异常类
```

### 调用链

```
MonitorScheduler (未来)
       ↓
FeishuNotifier.send_new_video_notification()
       ↓
FeishuNotifier._send_webhook()
       ↓
飞书 Webhook API
```

## Data Model

### 飞书消息卡片结构

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": {
        "tag": "plain_text",
        "content": "📺 【UP主名称】发布了新视频"
      },
      "template": "blue"
    },
    "elements": [
      {
        "tag": "div",
        "fields": [
          {
            "is_short": true,
            "text": {
              "tag": "lark_md",
              "content": "**标题**\n视频标题"
            }
          },
          {
            "is_short": true,
            "text": {
              "tag": "lark_md",
              "content": "**发布时间**\n2026-08-02 14:30"
            }
          }
        ]
      },
      {
        "tag": "div",
        "fields": [
          {
            "is_short": true,
            "text": {
              "tag": "lark_md",
              "content": "**播放量**\n1.2万"
            }
          }
        ]
      },
      {
        "tag": "action",
        "actions": [
          {
            "tag": "button",
            "text": {
              "tag": "plain_text",
              "content": "观看视频"
            },
            "type": "primary",
            "url": "https://www.bilibili.com/video/BVxxxx"
          }
        ]
      }
    ]
  }
}
```

### 错误告警卡片结构

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": {
        "tag": "plain_text",
        "content": "⚠️ 监控服务告警"
      },
      "template": "red"
    },
    "elements": [
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**错误信息**\n具体错误内容"
        }
      },
      {
        "tag": "note",
        "elements": [
          {
            "tag": "plain_text",
            "content": "时间：2026-08-02 14:30:00"
          }
        ]
      }
    ]
  }
}
```

### 飞书API响应结构

成功响应：
```json
{
  "code": 0,
  "msg": "success",
  "data": {}
}
```

失败响应示例：
```json
{
  "code": 10049,
  "msg": "rate limit exceeded"
}
```

## API / Interface

### FeishuNotifier 类接口

```python
class FeishuNotifier:
    def __init__(self, webhook_url: str):
        """初始化推送器"""

    def send_new_video_notification(
        self,
        up_name: str,
        video_title: str,
        video_url: str,
        pub_time: str,
        view_count: int
    ) -> bool:
        """发送新视频通知，成功返回 True"""

    def send_error_notification(self, error_msg: str) -> bool:
        """发送错误告警，成功返回 True"""

    def _format_view_count(self, view_count: int) -> str:
        """格式化播放量（已实现）"""

    def _send_webhook(self, payload: dict) -> bool:
        """发送 Webhook 请求，成功返回 True"""
```

## Frontend Changes

无前端变更。

## Backend Changes

### 修改文件

**src/feishu.py**

1. 新增导入：
   - `import requests`
   - `import logging`
   - `from datetime import datetime`

2. 实现 `_send_webhook()` 方法：
   - 检查 webhook_url 是否有效
   - 发送 POST 请求（timeout=10）
   - 验证 HTTP 状态码
   - 解析 JSON 响应
   - 检查飞书 code 字段
   - 异常捕获和日志记录

3. 实现 `send_new_video_notification()` 方法：
   - 构造交互式卡片 JSON
   - 调用 `_send_webhook()`
   - 返回结果

4. 实现 `send_error_notification()` 方法：
   - 构造红色主题告警卡片
   - 调用 `_send_webhook()`
   - 返回结果

**src/exceptions.py**

新增异常类：
```python
class FeishuAPIError(Exception):
    """飞书推送失败"""
    def __init__(self, message: str = "飞书推送失败"):
        self.message = message
        super().__init__(self.message)
```

## File Changes

| 文件 | 操作 | 说明 |
|------|------|------|
| src/feishu.py | 修改 | 实现三个未完成方法 |
| src/exceptions.py | 修改 | 新增 FeishuAPIError 异常类 |

## Implementation Flow

```
1. 在 exceptions.py 添加 FeishuAPIError 异常类
       ↓
2. 在 feishu.py 添加必要的 import
       ↓
3. 实现 _send_webhook() 核心方法
       ↓
4. 实现 send_new_video_notification()
       ↓
5. 实现 send_error_notification()
       ↓
6. 添加日志记录
       ↓
7. 测试验证
```

## Error Handling

### 异常处理策略

| 异常类型 | 处理方式 | 日志级别 |
|----------|----------|----------|
| requests.Timeout | 返回 False | WARNING |
| requests.ConnectionError | 返回 False | ERROR |
| requests.RequestException | 返回 False | ERROR |
| JSON解析错误 | 返回 False | ERROR |
| 飞书 code != 0 | 返回 False | WARNING |

### 错误响应码处理

| 飞书 code | 含义 | 处理 |
|-----------|------|------|
| 0 | 成功 | 返回 True |
| 10049 | 限流 | 记录警告，返回 False |
| 其他 | 其他错误 | 记录错误信息，返回 False |

## Testing Strategy

### 单元测试

创建 `tests/test_feishu.py`：

1. 测试 `_format_view_count()` 格式化逻辑
2. 测试 `_send_webhook()` 成功场景（mock requests）
3. 测试 `_send_webhook()` 网络异常处理
4. 测试 `send_new_video_notification()` 消息构造
5. 测试 `send_error_notification()` 消息构造

### 集成测试

使用真实 Webhook URL 发送测试消息，验证：
- 消息格式正确
- 飞书群能收到消息
- 按钮链接可点击

### 测试命令

```bash
# 运行单元测试
pytest tests/test_feishu.py -v

# 手动测试（使用真实Webhook）
python -c "
from src.feishu import FeishuNotifier
notifier = FeishuNotifier('your_webhook_url')
notifier.send_new_video_notification(
    up_name='测试UP主',
    video_title='测试视频标题',
    video_url='https://www.bilibili.com/video/BV1test',
    pub_time='2026-08-02 14:30',
    view_count=12345
)
"
```
