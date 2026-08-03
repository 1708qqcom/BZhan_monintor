# Technical Design

## Overview

本功能为现有 B站监控系统添加手动视频推送能力。用户可在 UP主管理页面手动推送视频到飞书。

**技术方案**：
- 后端新增 REST API：`POST /api/videos/{bvid}/push`
- 前端在视频卡片上添加推送按钮
- 新建数据库表 `push_history` 记录推送历史
- 复用现有的 `FeishuNotifier` 推送能力
- 视频信息缺失时调用 `BilibiliClient` 补全


## Architecture

### 系统模块图

```
┌─────────────────────────────────────────────────────────┐
│                      前端 (ups.html)                      │
│  - 视频卡片渲染                                           │
│  - 推送按钮                                               │
│  - 推送确认对话框                                         │
│  - 推送状态提示                                           │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP POST
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  后端 API (videos.py)                     │
│  - POST /api/videos/{bvid}/push                          │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┬─────────────────┐
        ▼              ▼              ▼                 ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Database   │ │   Bilibili  │ │   Feishu    │ │   Logger    │
 │   (SQLite)  │ │   Client    │ │  Notifier   │ │             │
│             │ │             │ │             │ │             │
│ - videos    │ │ - get_video │ │ - send_msg  │ │ - 推送日志  │
│ - push_     │ │   _detail   │ │             │ │ - 错误日志  │
│   history   │ │             │ │             │ │             │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

### 调用流程

```
前端点击推送
  ↓
POST /api/videos/{bvid}/push
  ↓
1. 根据 bvid 查询数据库获取视频记录
  ↓
2. 检查字段完整性（title, url, pub_time, view_count）
  ↓
3. 如果缺失 → 调用 B站 API 补全 → 更新数据库
  ↓
4. 查询 UP主信息（获取 up_name）
  ↓
5. 初始化 FeishuNotifier（读取 webhook_url）
  ↓
6. 调用 feishu.send_new_video_notification()
  ↓
7. 记录推送历史到 push_history 表
  ↓
8. 返回推送结果
```


## Data Model

### 新增表：push_history

```sql
CREATE TABLE push_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,              -- 关联 videos.id
    pushed_at TEXT NOT NULL,                -- 推送时间 (ISO 8601)
    push_type TEXT NOT NULL DEFAULT 'manual', -- 推送类型: auto/manual
    success INTEGER NOT NULL DEFAULT 0,     -- 是否成功: 0=失败, 1=成功
    error_message TEXT,                     -- 失败原因
    created_at TEXT NOT NULL,               -- 记录创建时间
    FOREIGN KEY (video_id) REFERENCES videos(id)
);

-- 索引
CREATE INDEX idx_push_history_video_id ON push_history(video_id);
CREATE INDEX idx_push_history_pushed_at ON push_history(pushed_at);
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `video_id` | INTEGER | 关联 videos.id |
| `pushed_at` | TEXT | 推送时间，ISO 8601 格式 |
| `push_type` | TEXT | 推送类型：`auto`（自动）/ `manual`（手动） |
| `success` | INTEGER | 是否成功：0=失败，1=成功 |
| `error_message` | TEXT | 失败原因（如失败） |
| `created_at` | TEXT | 记录创建时间 |

### 已有表变更

**videos 表**：无需变更（已包含所需字段）

**ups 表**：无需变更


## API / Interface

### 新增 API：POST /api/videos/{bvid}/push

**请求**：

```http
POST /api/videos/{bvid}/push
Content-Type: application/json
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `bvid` | string | 是 | 视频BV号 |

**请求体**：无

**响应（成功）**：

```json
{
  "message": "视频推送成功",
  "data": {
    "bvid": "BV1xx411c7mD",
    "title": "视频标题",
    "pushed_at": "2026-08-03T14:30:00"
  }
}
```

**响应（失败）**：

```json
{
  "error": "推送失败",
  "detail": "请先在配置页面设置飞书 Webhook"
}
```

**HTTP 状态码**：

| 状态码 | 说明 |
|--------|------|
| 200 | 推送成功 |
| 400 | 参数错误 / Webhook 未配置 |
| 404 | 视频不存在 |
| 500 | 推送失败（网络错误、飞书 API 错误等） |


## Frontend Changes

### 文件：templates/ups.html

#### 1. 修改 renderLatestVideos() 函数

**位置**：[ups.html:368-381](templates/ups.html#L368-L381)

**修改内容**：

```javascript
function renderLatestVideos(videos) {
    if (!videos || videos.length === 0) {
        return '<p class="text-xs text-gray-400">暂无视频记录</p>';
    }

    return `<div class="grid grid-cols-1 md:grid-cols-5 gap-2">
        ${videos.map(video => `
            <div class="relative p-2 bg-white rounded border border-gray-200 hover:border-blue-300 hover:shadow-sm transition-all">
                <!-- 视频链接 -->
                <a href="${video.url || '#'}" target="_blank" class="block pr-10">
                    <p class="text-xs text-gray-900 font-medium truncate" title="${escapeHtml(video.title)}">${escapeHtml(video.title)}</p>
                    <p class="text-xs text-gray-400 mt-1">${formatDateTime(video.pushed_at || video.created_at)}</p>
                </a>
                <!-- 推送按钮 -->
                <button
                    onclick="event.stopPropagation(); pushVideoToFeishu('${video.bvid}', '${escapeHtml(video.title)}')"
                    class="absolute top-1 right-1 text-xs text-bilibili-pink hover:text-pink-600 font-medium"
                    title="推送到飞书"
                >
                    推送
                </button>
            </div>
        `).join('')}
    </div>`;
}
```

#### 2. 新增 pushVideoToFeishu() 函数

**位置**：在 `<script>` 标签内添加

```javascript
/**
 * 推送视频到飞书
 * 
 * @param {string} bvid - 视频BV号
 * @param {string} title - 视频标题（用于确认对话框）
 */
async function pushVideoToFeishu(bvid, title) {
    // 确认对话框
    const confirmed = confirm(`确定推送视频 "${title}" 到飞书？`);
    if (!confirmed) {
        return;
    }

    console.log(`[Ups] 开始推送视频: ${bvid}`);

    try {
        // 调用后端 API
        const response = await fetchAPI(`/api/videos/${bvid}/push`, {
            method: 'POST'
        });

        // 成功提示
        showSuccess(response.message || '推送成功');
        console.log(`[Ups] 推送成功: ${bvid}`);

    } catch (error) {
        // 失败提示
        console.error('[Ups] 推送失败:', error);
        showError('推送失败: ' + error.message);
    }
}
```


## Backend Changes

### 文件：src/api/videos.py

#### 新增端点：POST /{bvid}/push

```python
@router.post(
    "/{bvid}/push",
    response_model=SuccessResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="手动推送视频到飞书",
    description="将指定视频推送到飞书 Webhook"
)
async def push_video(
    bvid: str,
    db: Database = Depends(get_db),
):
    """
    手动推送视频到飞书
    
    流程：
    1. 根据 bvid 查询视频记录
    2. 检查视频信息完整性，缺失时调用 B站 API 补全
    3. 获取 UP主信息
    4. 初始化飞书推送器
    5. 发送推送消息
    6. 记录推送历史
    
    Args:
        bvid: 视频BV号
        
    Returns:
        推送结果
    """
```

#### 实现要点

1. **查询视频记录**：
   ```python
   video = db.get_video_by_bvid(bvid)
   if not video:
       raise HTTPException(status_code=404, detail="视频不存在")
   ```

2. **补全视频信息**：
   ```python
   # 检查字段完整性
   if not video.get('view_count'):
       # 从数据库获取 Cookie
       auth = db.get_auth()
       client = BilibiliClient(cookies=auth['cookies'])
       
       # 调用 B站 API
       video_detail = client.get_video_detail(bvid)
       
       # 更新数据库
       db.update_video(bvid, video_detail)
   ```

3. **获取 UP主信息**：
   ```python
   up = db.get_up_by_id(video['up_id'])
   up_name = up.get('name', '未知UP主') if up else '未知UP主'
   ```

4. **初始化推送器**：
   ```python
   webhook_url = db.get_config_value('feishu_webhook')
   if not webhook_url:
       raise HTTPException(status_code=400, detail="请先在配置页面设置飞书 Webhook")
   
   feishu = FeishuNotifier(webhook_url)
   ```

5. **发送推送**：
   ```python
   success = feishu.send_new_video_notification(
       up_name=up_name,
       video_title=video['title'],
       video_url=video['url'],
       pub_time=video['pub_time'],
       view_count=video.get('view_count', 0)
   )
   ```

6. **记录推送历史**：
   ```python
   db.add_push_history(
       video_id=video['id'],
       push_type='manual',
       success=success
   )
   ```

### 文件：src/database.py

#### 新增方法：get_video_by_bvid()

```python
def get_video_by_bvid(self, bvid: str) -> Optional[dict]:
    """
    根据 BV号查询视频记录
    
    Args:
        bvid: 视频BV号
        
    Returns:
        视频记录字典，不存在返回 None
    """
```

#### 新增方法：update_video()

```python
def update_video(self, bvid: str, video_data: dict) -> bool:
    """
    更新视频记录
    
    Args:
        bvid: 视频BV号
        video_data: 更新数据字典
        
    Returns:
        是否更新成功
    """
```

#### 新增方法：add_push_history()

```python
def add_push_history(
    self,
    video_id: int,
    push_type: str,
    success: bool,
    error_message: str = None
) -> int:
    """
    添加推送历史记录
    
    Args:
        video_id: 视频ID
        push_type: 推送类型 (auto/manual)
        success: 是否成功
        error_message: 失败原因
        
    Returns:
        记录ID
    """
```

#### 新增方法：init_push_history_table()

```python
def init_push_history_table(self) -> None:
    """
    初始化 push_history 表
    """
```

### 文件：src/bilibili.py

#### 新增方法：get_video_detail()

```python
def get_video_detail(self, bvid: str) -> dict:
    """
    获取视频详细信息
    
    Args:
        bvid: 视频BV号
        
    Returns:
        视频信息字典（包含 title, view_count, pub_time 等）
    """
```

**实现**：调用 B站 API `https://api.bilibili.com/x/web-interface/view?bvid={bvid}`


## File Changes

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `src/api/videos.py` | 新增 | 添加 `POST /{bvid}/push` 端点 |
| `src/database.py` | 新增 | 添加 `push_history` 表和相关方法 |
| `src/bilibili.py` | 新增 | 添加 `get_video_detail()` 方法 |
| `templates/ups.html` | 修改 | 修改视频卡片渲染，添加推送按钮 |


## Implementation Flow

### 阶段 1：数据库层（后端基础）

1. 在 `src/database.py` 添加 `init_push_history_table()` 方法
2. 在 `Database.__init__()` 调用建表方法
3. 添加 `get_video_by_bvid()` 方法
4. 添加 `update_video()` 方法
5. 添加 `add_push_history()` 方法
6. 测试数据库操作


### 阶段 2：B站 API 扩展

1. 在 `src/bilibili.py` 添加 `get_video_detail()` 方法
2. 测试 API 调用
3. 处理异常情况（Cookie 过期、网络错误）


### 阶段 3：后端 API

1. 在 `src/api/videos.py` 添加 `POST /{bvid}/push` 端点
2. 实现视频查询逻辑
3. 实现信息补全逻辑
4. 实现飞书推送逻辑
5. 实现推送历史记录
6. 添加异常处理和日志
7. 测试 API 接口


### 阶段 4：前端交互

1. 修改 `templates/ups.html` 的 `renderLatestVideos()` 函数
2. 添加推送按钮 HTML
3. 添加 `pushVideoToFeishu()` 函数
4. 测试前端交互


### 阶段 5：集成测试

1. 端到端测试推送流程
2. 测试异常情况
3. 测试重复推送
4. 测试信息补全


## Error Handling

### 错误类型和处理

| 错误类型 | HTTP 状态码 | 错误消息 | 日志级别 |
|----------|------------|----------|----------|
| 视频不存在 | 404 | "视频不存在" | WARNING |
| Webhook 未配置 | 400 | "请先在配置页面设置飞书 Webhook" | WARNING |
| B站 API 调用失败 | - | 使用默认值继续推送 | WARNING |
| 飞书推送失败 | 500 | "推送失败，请稍后重试" | ERROR |
| 数据库异常 | 500 | "系统错误，请稍后重试" | ERROR |

### 日志记录

**成功推送**：
```
[INFO] 手动推送视频成功: bvid=BV1xx..., title=视频标题, up_name=UP主名称
```

**推送失败**：
```
[ERROR] 手动推送视频失败: bvid=BV1xx..., error=飞书API返回错误: code=190001, msg=invalid webhook
[ERROR] 堆栈跟踪: Traceback (most recent call last): ...
```

**信息补全**：
```
[WARNING] 视频信息不完整，调用B站API补全: bvid=BV1xx...
[INFO] 视频信息补全成功: bvid=BV1xx..., view_count=12345
[WARNING] 视频信息补全失败，使用默认值: bvid=BV1xx..., error=网络超时
```


## Testing Strategy

### 单元测试

1. **Database 层测试**：
   - 测试 `get_video_by_bvid()` 查询
   - 测试 `update_video()` 更新
   - 测试 `add_push_history()` 插入

2. **Bilibili API 测试**：
   - 测试 `get_video_detail()` 正常调用
   - 测试网络异常处理

3. **Feishu 推送测试**：
   - 测试 `send_new_video_notification()` 调用
   - 测试异常情况


### 集成测试

1. **API 测试**：
   - 测试成功推送流程
   - 测试视频不存在
   - 测试 Webhook 未配置
   - 测试推送失败

2. **前端测试**：
   - 测试按钮显示
   - 测试点击确认流程
   - 测试成功/失败提示


### 手动测试

1. 访问 `/ups` 页面
2. 展开某个 UP主的视频列表
3. 点击"推送"按钮
4. 确认推送
5. 检查飞书群消息
6. 检查数据库 `push_history` 表

**测试用例**：
- 正常推送
- 重复推送
- 未配置 Webhook
- 网络断开
- Cookie 过期