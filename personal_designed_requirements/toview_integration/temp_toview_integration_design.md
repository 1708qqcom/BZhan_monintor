# Technical Design

## Overview

基于现有系统架构，扩展"稍后再看"功能模块。主要技术栈：
- **后端**: FastAPI + APScheduler（定时任务）
- **前端**: Jinja2 + Tailwind CSS
- **数据存储**: SQLite（复用现有数据库）
- **外部API**: B站 `api.bilibili.com/x/v2/history/toview`
- **推送**: 飞书Webhook

技术方案：
1. 扩展 `BilibiliClient` 类，新增 `get_toview_list()` 方法
2. 新增数据库表 `toview_videos`、`toview_push_history`
3. 新增定时任务：每天21:00执行推送
4. 新增Web路由和API端点
5. 新增页面模板

## Architecture

### 系统架构图
```
┌─────────────────────────────────────────┐
│            Web Frontend (Jinja2)        │
│  - 用户稍后再看页面                      │
│  - 管理员稍后再看页面                    │
│  - 推送历史页面                          │
└────────────────┬────────────────────────┘
                 │ HTTP
┌────────────────┴────────────────────────┐
│          FastAPI Backend                 │
│  ┌────────────────────────────────────┐ │
│  │ API Routes                         │ │
│  │ - GET  /api/toview                 │ │
│  │ - GET  /api/toview/all (admin)     │ │
│  │ - POST /api/toview/push (admin)    │ │
│  └────────────────────────────────────┘ │
│  ┌────────────────────────────────────┐ │
│  │ Business Logic                     │ │
│  │ - ToViewService                    │ │
│  │ - ToViewPushScheduler              │ │
│  └────────────────────────────────────┘ │
└────────┬───────────────────┬────────────┘
         │                   │
    ┌────┴─────┐        ┌────┴─────┐
    │  SQLite  │        │ B站 API   │
    │  Database│        │ Client   │
    └──────────┘        └────┬─────┘
                             │
                        ┌────┴─────┐
                        │ 飞书API   │
                        │ Webhook  │
                        └──────────┘
```

### 模块影响范围
| 模块 | 变化类型 | 影响范围 |
|------|----------|----------|
| `src/bilibili.py` | 扩展 | 新增 `get_toview_list()` |
| `src/database.py` | 扩展 | 新增表和CRUD方法 |
| `src/scheduler.py` | 扩展 | 新增定时推送任务 |
| `src/web.py` | 无变化 | - |
| `src/api/toview.py` | 新增 | 新API路由模块 |
| `templates/toview.html` | 新增 | 用户查看页面 |
| `templates/admin_toview.html` | 新增 | 管理员查看页面 |

## Data Model

### 新增数据库表

#### 表1: `toview_videos`（稍后再看视频缓存）
```sql
CREATE TABLE toview_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,           -- 用户ID（外键）
    bvid TEXT NOT NULL,                 -- 视频BV号
    title TEXT NOT NULL,                -- 视频标题
    author TEXT,                        -- UP主名称
    mid INTEGER,                        -- UP主ID
    pic TEXT,                           -- 封面URL
    play INTEGER DEFAULT 0,             -- 播放量
    duration TEXT,                      -- 视频时长
    pubdate INTEGER,                    -- 发布时间戳
    added_at INTEGER NOT NULL,          -- 添加到稍后再看的时间戳
    synced_at INTEGER NOT NULL,         -- 最后同步时间戳
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, bvid)               -- 用户+视频唯一
);

CREATE INDEX idx_toview_user ON toview_videos(user_id);
CREATE INDEX idx_toview_synced ON toview_videos(synced_at);
```

#### 表2: `toview_push_history`（推送历史）
```sql
CREATE TABLE toview_push_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,           -- 用户ID
    push_type TEXT NOT NULL,            -- 推送类型：'auto'/'manual'
    pushed_at INTEGER NOT NULL,         -- 推送时间戳
    video_count INTEGER NOT NULL,       -- 推送视频数量
    video_list TEXT NOT NULL,           -- 推送的视频列表（JSON）
    success BOOLEAN NOT NULL,           -- 是否成功
    error_message TEXT,                 -- 错误信息
    pushed_by INTEGER,                  -- 手动推送的操作人ID（管理员）
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (pushed_by) REFERENCES users(id)
);

CREATE INDEX idx_toview_history_user ON toview_push_history(user_id);
CREATE INDEX idx_toview_history_time ON toview_push_history(pushed_at);
```

### 数据流转
```
B站API → BilibiliClient.get_toview_list()
       → Database.save_toview_videos()
       → Web界面展示

定时任务 → Database.get_users_with_valid_auth()
        → BilibiliClient.get_toview_list()
        → FeishuClient.send_toview_notification()
        → Database.save_push_history()
```

## API / Interface

### 新增API端点

#### 1. 获取当前用户的稍后再看列表
```
GET /api/toview

Request:
  Headers: Cookie (session)

Response: {
  "success": true,
  "data": {
    "count": 10,
    "videos": [
      {
        "bvid": "BV1...",
        "title": "视频标题",
        "author": "UP主名",
        "play": 12000,
        "duration": "12:34",
        "pubdate": 1234567890,
        "added_at": 1234567890
      }
    ]
  }
}

Error: {
  "success": false,
  "error": "Cookie已过期，请重新登录"
}
```

#### 2. 获取所有用户的稍后再看列表（管理员）
```
GET /api/toview/all

Request:
  Headers: Cookie (session, admin required)
  Query: ?user_id=1 (可选)

Response: {
  "success": true,
  "data": [
    {
      "user_id": 1,
      "username": "user1",
      "count": 5,
      "videos": [...]
    }
  ]
}
```

#### 3. 手动推送稍后再看（管理员）
```
POST /api/toview/push

Request:
  Headers: Cookie (session, admin required)
  Body: {
    "user_id": 1,        // 可选，不填则推送自己的
    "count": 3           // 可选，推送数量，默认3
  }

Response: {
  "success": true,
  "message": "推送成功",
  "pushed_videos": [...]
}

Error: {
  "success": false,
  "error": "用户未配置飞书Webhook"
}
```

#### 4. 获取推送历史
```
GET /api/toview/history

Request:
  Headers: Cookie (session)
  Query: ?user_id=1 (可选，管理员可查看所有)

Response: {
  "success": true,
  "data": [
    {
      "id": 1,
      "push_type": "auto",
      "pushed_at": 1234567890,
      "video_count": 3,
      "success": true
    }
  ]
}
```

### BilibiliClient 新增方法签名

```python
# src/bilibili.py
class BilibiliClient:
    # 新增常量
    TOVIEW_API = "https://api.bilibili.com/x/v2/history/toview"

    def get_toview_list(self, page: int = 1, page_size: int = 30) -> list[dict]:
        """
        获取稍后再看列表

        Args:
            page: 页码（从1开始）
            page_size: 每页数量（最大30）

        Returns:
            视频列表 [{
                "bvid": "BV1...",
                "title": "标题",
                "author": "UP主",
                "mid": UP主ID,
                "pic": "封面URL",
                "play": 播放量,
                "duration": "12:34",
                "pubdate": 时间戳
            }]

        Raises:
            BilibiliAPIError: API调用失败
            CookieExpiredError: Cookie过期
        """
```

## Frontend Changes

### 新增页面模板

#### 1. 用户稍后再看页面 (`templates/toview.html`)
```html
<!-- 继承 base.html -->
{% extends "base.html" %}

{% block content %}
<div class="container mx-auto px-4 py-8">
  <h1>我的稍后再看</h1>

  <!-- 视频列表 -->
  <div class="grid gap-4">
    {% for video in videos %}
    <div class="card">
      <img src="{{ video.pic }}" />
      <div class="content">
        <h3>{{ video.title }}</h3>
        <p>UP主: {{ video.author }}</p>
        <p>播放: {{ video.play }}</p>
        <a href="https://www.bilibili.com/video/{{ video.bvid }}"
           target="_blank" class="btn">
          前往观看
        </a>
      </div>
    </div>
    {% endfor %}
  </div>
</div>
{% endblock %}
```

#### 2. 管理员稍后再看管理页面 (`templates/admin_toview.html`)
```html
<!-- 继承 base.html -->
{% extends "base.html" %}

{% block content %}
<div class="container mx-auto px-4 py-8">
  <h1>稍后再看管理</h1>

  <!-- 用户筛选 -->
  <select id="user-filter">
    <option value="">全部用户</option>
    {% for user in users %}
    <option value="{{ user.id }}">{{ user.username }}</option>
    {% endfor %}
  </select>

  <!-- 用户列表 -->
  <div id="user-toview-list">
    {% for user_data in all_toview %}
    <div class="user-section">
      <h2>{{ user_data.username }} ({{ user_data.count }}个)</h2>

      <!-- 手动推送按钮 -->
      <button onclick="pushToview({{ user_data.user_id }})"
              class="btn btn-primary">
        立即推送前3个
      </button>

      <!-- 视频列表 -->
      <div class="video-grid">
        {% for video in user_data.videos %}
        <div class="card">{{ video.title }}</div>
        {% endfor %}
      </div>
    </div>
    {% endfor %}
  </div>
</div>

<script>
function pushToview(userId) {
  fetch('/api/toview/push', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({user_id: userId, count: 3})
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      alert('推送成功');
    } else {
      alert('推送失败: ' + data.error);
    }
  });
}
</script>
{% endblock %}
```

#### 3. 推送历史页面 (`templates/toview_history.html`)
```html
<!-- 继承 base.html -->
{% extends "base.html" %}

{% block content %}
<div class="container mx-auto px-4 py-8">
  <h1>推送历史</h1>

  <table class="table">
    <thead>
      <tr>
        <th>推送时间</th>
        <th>类型</th>
        <th>视频数量</th>
        <th>状态</th>
        <th>操作</th>
      </tr>
    </thead>
    <tbody>
      {% for history in histories %}
      <tr>
        <td>{{ history.pushed_at }}</td>
        <td>{{ history.push_type }}</td>
        <td>{{ history.video_count }}</td>
        <td>
          {% if history.success %}
          <span class="badge-success">成功</span>
          {% else %}
          <span class="badge-error">失败</span>
          {% endif %}
        </td>
        <td>
          <button onclick="showDetail({{ history.id }})">查看详情</button>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

### 导航栏更新
在 `templates/base.html` 的导航栏中添加：
```html
<a href="/toview" class="nav-link">稍后再看</a>
{% if user.is_admin %}
<a href="/admin/toview" class="nav-link">稍后再看管理</a>
{% endif %}
```

## Backend Changes

### 文件1: `src/bilibili.py`（扩展）

**新增方法**:
```python
def get_toview_list(self, page: int = 1, page_size: int = 30) -> list[dict]:
    """获取稍后再看列表"""
    params = {"pn": page, "ps": page_size}
    data = self._make_request(self.TOVIEW_API, params, use_wbi=False)

    # 解析返回数据
    videos = data.get("list", [])
    result = []

    for item in videos:
        result.append({
            "bvid": item.get("bvid"),
            "title": item.get("title"),
            "author": item.get("author"),
            "mid": item.get("mid"),
            "pic": item.get("pic"),
            "play": item.get("play", 0),
            "duration": item.get("duration", ""),
            "pubdate": item.get("pubdate", 0)
        })

    return result
```

### 文件2: `src/database.py`（扩展）

**新增方法**:
```python
def save_toview_videos(self, user_id: int, videos: list[dict]) -> None:
    """保存稍后再看视频列表"""

def get_toview_videos(self, user_id: int, limit: int = 30) -> list[dict]:
    """获取用户的稍后再看视频"""

def get_all_toview_videos(self, user_id: Optional[int] = None) -> list[dict]:
    """获取所有用户的稍后再看视频（管理员用）"""

def save_toview_push_history(self, user_id: int, push_type: str,
                             videos: list[dict], success: bool,
                             error: str = None, pushed_by: int = None) -> None:
    """保存推送历史"""

def get_toview_push_history(self, user_id: Optional[int] = None,
                            limit: int = 100) -> list[dict]:
    """获取推送历史"""
```

### 文件3: `src/scheduler.py`（扩展）

**新增定时任务**:
```python
from apscheduler.triggers.cron import CronTrigger

def setup_toview_push_scheduler(self):
    """设置稍后再看定时推送"""
    self.scheduler.add_job(
        func=self._push_toview_all_users,
        trigger=CronTrigger(hour=21, minute=0),  # 每天21:00
        id='toview_push',
        name='稍后再看定时推送',
        replace_existing=True
    )

def _push_toview_all_users(self):
    """推送所有用户的稍后再看"""
    # 1. 获取所有有效用户
    users = self.db.get_all_users_with_valid_auth()

    for user in users:
        try:
            # 2. 获取稍后再看列表
            client = BilibiliClient(cookies=user['cookies'])
            videos = client.get_toview_list(page_size=3)

            if not videos:
                logger.info(f"用户 {user['username']} 稍后再看为空，跳过")
                continue

            # 3. 获取飞书Webhook
            webhook = self.db.get_config_value("feishu_webhook_url", user_id=user['id'])
            if not webhook:
                logger.warning(f"用户 {user['username']} 未配置飞书Webhook")
                continue

            # 4. 推送
            feishu = FeishuClient(webhook_url=webhook)
            feishu.send_toview_notification(user['username'], videos)

            # 5. 记录历史
            self.db.save_toview_push_history(
                user_id=user['id'],
                push_type='auto',
                videos=videos,
                success=True
            )

        except Exception as e:
            logger.error(f"用户 {user['username']} 推送失败: {e}")
            self.db.save_toview_push_history(
                user_id=user['id'],
                push_type='auto',
                videos=[],
                success=False,
                error=str(e)
            )
```

### 文件4: `src/api/toview.py`（新增）

**完整代码**:
```python
"""稍后再看API路由"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from src.bilibili import BilibiliClient
from src.feishu import FeishuClient
from src.database import Database

router = APIRouter(prefix="/api/toview", tags=["toview"])
db = Database()

class PushRequest(BaseModel):
    user_id: Optional[int] = None
    count: int = 3

@router.get("")
async def get_toview(request: Request):
    """获取当前用户的稍后再看列表"""
    user = request.state.user

    try:
        # 获取用户的B站Cookie
        auth = db.get_auth(user_id=user['id'])
        if not auth:
            raise HTTPException(401, "未登录B站账号")

        # 调用B站API
        client = BilibiliClient(cookies=auth['cookies'])
        videos = client.get_toview_list()

        # 保存到数据库（缓存）
        db.save_toview_videos(user['id'], videos)

        return {"success": True, "data": {"count": len(videos), "videos": videos}}

    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/all")
async def get_all_toview(request: Request, user_id: Optional[int] = None):
    """获取所有用户的稍后再看列表（管理员）"""
    user = request.state.user

    if not user.get('is_admin'):
        raise HTTPException(403, "无权限")

    try:
        data = db.get_all_toview_videos(user_id=user_id)
        return {"success": True, "data": data}

    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/push")
async def push_toview(request: Request, body: PushRequest):
    """手动推送稍后再看（管理员）"""
    user = request.state.user

    if not user.get('is_admin'):
        raise HTTPException(403, "无权限")

    target_user_id = body.user_id or user['id']

    try:
        # 获取目标用户信息
        auth = db.get_auth(user_id=target_user_id)
        if not auth:
            raise HTTPException(404, "用户未登录B站")

        # 获取飞书Webhook
        webhook = db.get_config_value("feishu_webhook_url", user_id=target_user_id)
        if not webhook:
            raise HTTPException(400, "用户未配置飞书Webhook")

        # 获取稍后再看列表
        client = BilibiliClient(cookies=auth['cookies'])
        videos = client.get_toview_list(page_size=body.count)

        if not videos:
            return {"success": True, "message": "稍后再看列表为空"}

        # 推送
        feishu = FeishuClient(webhook_url=webhook)
        feishu.send_toview_notification(
            username=db.get_user_by_id(target_user_id)['username'],
            videos=videos
        )

        # 记录历史
        db.save_toview_push_history(
            user_id=target_user_id,
            push_type='manual',
            videos=videos,
            success=True,
            pushed_by=user['id']
        )

        return {"success": True, "pushed_videos": videos}

    except Exception as e:
        db.save_toview_push_history(
            user_id=target_user_id,
            push_type='manual',
            videos=[],
            success=False,
            error=str(e),
            pushed_by=user['id']
        )
        raise HTTPException(500, str(e))

@router.get("/history")
async def get_history(request: Request, user_id: Optional[int] = None):
    """获取推送历史"""
    user = request.state.user

    # 权限检查
    if user_id and not user.get('is_admin'):
        raise HTTPException(403, "无权限")

    target_user_id = user_id if user.get('is_admin') and user_id else user['id']

    histories = db.get_toview_push_history(user_id=target_user_id)
    return {"success": True, "data": histories}
```

### 文件5: `src/feishu.py`（扩展）

**新增方法**:
```python
def send_toview_notification(self, username: str, videos: list[dict]) -> bool:
    """发送稍后再看推送通知"""
    # 构造视频列表内容
    video_items = []
    for i, video in enumerate(videos, 1):
        video_items.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**{i}. [{video['title']}](https://www.bilibili.com/video/{video['bvid']})**\nUP主: {video.get('author', '未知')} | 播放: {self._format_play_count(video.get('play', 0))}"
            }
        })

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"📺 {username}的稍后再看提醒"},
                "template": "blue"
            },
            "elements": video_items + [
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": f"共 {len(videos)} 个视频待观看"}
                    ]
                }
            ]
        }
    }

    return self._send_card(card)
```

## File Changes

### 需要修改的文件
1. `src/bilibili.py` - 新增 `get_toview_list()` 方法
2. `src/database.py` - 新增数据库表和CRUD方法
3. `src/scheduler.py` - 新增定时推送任务
4. `src/feishu.py` - 新增稍后再看推送模板
5. `src/web.py` - 注册新的路由和页面

### 需要新增的文件
1. `src/api/toview.py` - 稍后再看API路由
2. `templates/toview.html` - 用户查看页面
3. `templates/admin_toview.html` - 管理员管理页面
4. `templates/toview_history.html` - 推送历史页面

### 数据库迁移
需要创建迁移脚本：
- `scripts/migrate_add_toview_tables.py`

## Implementation Flow

### Phase 1: 数据层（Day 1）
1. 创建数据库表（`toview_videos`、`toview_push_history`）
2. 在 `Database` 类中新增CRUD方法
3. 编写单元测试验证数据库操作

### Phase 2: B站API集成（Day 1）
1. 在 `BilibiliClient` 中新增 `get_toview_list()` 方法
2. 测试API调用
3. 处理错误情况（Cookie失效、API超时）

### Phase 3: 推送功能（Day 2）
1. 在 `FeishuClient` 中新增稍后再看推送模板
2. 测试推送消息格式
3. 在 `Scheduler` 中新增定时任务

### Phase 4: Web API开发（Day 2）
1. 创建 `src/api/toview.py`
2. 实现4个API端点
3. 添加权限验证
4. 编写API测试

### Phase 5: 前端页面（Day 3）
1. 创建用户稍后再看页面
2. 创建管理员管理页面
3. 创建推送历史页面
4. 更新导航栏

### Phase 6: 集成测试（Day 3）
1. 测试定时推送流程
2. 测试手动推送流程
3. 测试权限控制
4. 测试异常情况

## Error Handling

### 错误类型和处理策略

#### 1. Cookie失效错误
```python
try:
    videos = client.get_toview_list()
except CookieExpiredError:
    # 返回友好提示
    return {"success": False, "error": "B站登录已过期，请重新扫码登录"}
```

#### 2. API请求失败
```python
# 在 BilibiliClient._make_request() 中已实现重试机制
# 重试3次，指数退避（1s, 2s, 4s）
```

#### 3. 飞书推送失败
```python
try:
    feishu.send_toview_notification(username, videos)
except Exception as e:
    logger.error(f"飞书推送失败: {e}")
    # 记录失败历史
    db.save_toview_push_history(user_id, 'manual', videos, False, str(e))
```

#### 4. 数据库错误
```python
try:
    db.save_toview_videos(user_id, videos)
except Exception as e:
    logger.error(f"数据库保存失败: {e}")
    # 不影响用户查看，继续返回数据
```

### 日志规范
```python
# 成功
logger.info(f"用户 {user_id} 成功获取稍后再看列表，共 {len(videos)} 个视频")

# 警告
logger.warning(f"用户 {user_id} 未配置飞书Webhook，跳过推送")

# 错误
logger.error(f"用户 {user_id} 获取稍后再看失败: {e}", exc_info=True)
```

## Testing Strategy

### 单元测试

#### 1. B站API测试 (`tests/test_bilibili_toview.py`)
```python
def test_get_toview_list_success():
    """测试成功获取稍后再看列表"""
    client = BilibiliClient(cookies=test_cookies)
    videos = client.get_toview_list()
    assert isinstance(videos, list)
    assert len(videos) > 0
    assert 'bvid' in videos[0]

def test_get_toview_list_cookie_expired():
    """测试Cookie失效"""
    client = BilibiliClient(cookies=invalid_cookies)
    with pytest.raises(CookieExpiredError):
        client.get_toview_list()
```

#### 2. 数据库测试 (`tests/test_database_toview.py`)
```python
def test_save_toview_videos():
    """测试保存稍后再看视频"""
    db.save_toview_videos(user_id=1, videos=test_videos)

    saved = db.get_toview_videos(user_id=1)
    assert len(saved) == len(test_videos)

def test_save_push_history():
    """测试保存推送历史"""
    db.save_toview_push_history(
        user_id=1,
        push_type='auto',
        videos=test_videos,
        success=True
    )

    history = db.get_toview_push_history(user_id=1)
    assert history[0]['push_type'] == 'auto'
```

#### 3. 推送测试 (`tests/test_feishu_toview.py`)
```python
def test_send_toview_notification():
    """测试稍后再看推送"""
    feishu = FeishuClient(webhook_url=test_webhook)
    result = feishu.send_toview_notification("测试用户", test_videos)
    assert result == True
```

### 集成测试

#### 1. 定时推送流程测试
```python
def test_auto_push_workflow():
    """测试自动推送完整流程"""
    # 1. 模拟21:00触发
    scheduler._push_toview_all_users()

    # 2. 检查推送历史
    history = db.get_toview_push_history(user_id=1)
    assert history[0]['push_type'] == 'auto'
    assert history[0]['success'] == True
```

#### 2. 手动推送测试
```python
def test_manual_push_api():
    """测试手动推送API"""
    response = client.post("/api/toview/push", json={"user_id": 1, "count": 3})
    assert response.status_code == 200
    assert response.json()['success'] == True
```

### 手动测试清单

#### 功能测试
- [ ] 用户登录后可以查看自己的稍后再看列表
- [ ] 管理员可以查看所有用户的稍后再看
- [ ] 管理员可以手动推送指定用户的稍后再看
- [ ] 每天21:00自动推送（模拟测试）

#### 异常测试
- [ ] Cookie失效时显示友好提示
- [ ] 未配置Webhook时跳过推送
- [ ] API超时时重试成功
- [ ] 推送失败时记录日志

#### 权限测试
- [ ] 普通用户无法查看其他用户数据
- [ ] 普通用户无法调用手动推送API
- [ ] 管理员可以查看所有数据
- [ ] 管理员可以推送任意用户

## Deployment Notes

### 数据库迁移
```bash
# 执行迁移脚本
python scripts/migrate_add_toview_tables.py
```

### 配置更新
无需修改 `config/settings.yaml`

### 服务重启
```bash
sudo systemctl restart monitor-onlinevideo
```

### 监控验证
```bash
# 查看定时任务日志
tail -f logs/monitor.log | grep toview

# 查看推送历史
sqlite3 data/monitor.db "SELECT * FROM toview_push_history ORDER BY pushed_at DESC LIMIT 10;"
```