# Technical Design - Web Backend

## Overview

将当前的命令行监控工具扩展为 Web 服务，采用 **FastAPI + SQLite** 架构。

**核心设计决策**：
- Web 服务与监控进程**独立运行**，通过数据库解耦
- 监控进程每次循环从数据库**读取最新配置**实现热更新
- UP主添加时调用 B站 API 验证有效性

## Architecture

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Web 前端 (Jinja2模板)                     │
│         仪表盘 | UP主管理 | 推送历史 | 配置管理               │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Web 服务 (独立进程)                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ UP主API  │ │ 视频API  │ │ 配置API  │ │ 登录API  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │   SQLite DB  │
                   │  (统一存储)   │
                   └───────┬──────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                监控进程 (独立运行)                            │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ MonitorScheduler│  │ BilibiliClient  │                  │
│  │  (定时循环)      │  │  (API调用)      │                  │
│  └─────────────────┘  └─────────────────┘                  │
│           ↓                                                  │
│  每次循环开始时读取数据库配置                                 │
└─────────────────────────────────────────────────────────────┘
```

### 进程关系

| 进程 | 职责 | 启动方式 |
|------|------|---------|
| **监控进程** | 定时检查新视频、推送通知 | `python main.py` |
| **Web 服务** | 提供 API、管理界面 | `uvicorn src.web:app` |

两个进程通过 SQLite 数据库通信，互不干扰。

## Data Model

### 数据库表结构

**UP主表 (ups)**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 内部ID |
| mid | INTEGER | UNIQUE NOT NULL | B站UP主ID |
| name | TEXT | NOT NULL | UP主名称 |
| face | TEXT | | 头像URL |
| is_monitoring | BOOLEAN | DEFAULT 1 | 是否监控中 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 添加时间 |

**视频历史表 (videos)**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 内部ID |
| up_id | INTEGER | NOT NULL | 关联UP主 |
| bvid | TEXT | UNIQUE NOT NULL | 视频BV号 |
| title | TEXT | NOT NULL | 视频标题 |
| url | TEXT | | 视频链接 |
| pub_time | DATETIME | | 发布时间 |
| view_count | INTEGER | DEFAULT 0 | 播放量 |
| pushed | BOOLEAN | DEFAULT 0 | 是否已推送 |
| pushed_at | DATETIME | | 推送时间 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 记录创建时间 |

外键：`FOREIGN KEY (up_id) REFERENCES ups(id)`

**配置表 (config)**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| key | TEXT | PRIMARY KEY | 配置项键 |
| value | TEXT | NOT NULL | 配置项值（JSON格式） |
| updated_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

预设配置项：
- `check_interval_minutes`: 检查间隔（分钟）
- `max_ups`: 最多监控UP主数
- `feishu_webhook_url`: 飞书 Webhook 地址

**登录信息表 (auth)**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY CHECK (id = 1) | 单行约束 |
| cookies | TEXT | NOT NULL | Cookie JSON |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| expires_at | DATETIME | | 预计过期时间 |

### 数据迁移映射

**video_history.json → SQLite**

```json
{
  "videos": {
    "BV123456": {
      "title": "标题",
      "up_id": 123456,
      "up_name": "UP主名",
      "pubdate": 1234567890,
      "pushed": false
    }
  }
}
```

↓ 映射到 ↓

**ups 表**（去重）
```sql
INSERT INTO ups (mid, name) VALUES (123456, 'UP主名');
```

**videos 表**
```sql
INSERT INTO videos (up_id, bvid, title, pub_time, pushed)
VALUES (1, 'BV123456', '标题', datetime(1234567890, 'unixepoch'), 0);
```

## API / Interface

### REST API 设计

#### UP主管理

**GET /api/ups**

Query 参数：
- `is_monitoring` (optional): 筛选状态 (true/false)

Response:
```json
{
  "data": [
    {
      "id": 1,
      "mid": 123456,
      "name": "UP主名",
      "face": "https://...",
      "is_monitoring": true,
      "created_at": "2026-08-02T10:00:00"
    }
  ],
  "total": 10
}
```

**POST /api/ups**

Request:
```json
{
  "mid": 123456
}
```

Response:
```json
{
  "id": 1,
  "mid": 123456,
  "name": "UP主名",
  "face": "https://...",
  "is_monitoring": true,
  "created_at": "2026-08-02T10:00:00"
}
```

Error:
```json
{
  "error": "UP主不存在",
  "code": "UP_NOT_FOUND"
}
```

**DELETE /api/ups/{id}**

Response:
```json
{
  "success": true
}
```

#### 推送历史

**GET /api/videos**

Query 参数：
- `page` (default: 1)
- `page_size` (default: 20, max: 100)
- `up_id` (optional): 筛选UP主
- `start_date` (optional): 开始日期 (YYYY-MM-DD)
- `end_date` (optional): 结束日期 (YYYY-MM-DD)
- `pushed` (optional): 是否已推送

Response:
```json
{
  "data": [
    {
      "id": 1,
      "bvid": "BV123456",
      "title": "视频标题",
      "url": "https://www.bilibili.com/video/BV123456",
      "pub_time": "2026-08-02T10:00:00",
      "view_count": 10000,
      "pushed": true,
      "pushed_at": "2026-08-02T10:30:00",
      "up": {
        "id": 1,
        "mid": 123456,
        "name": "UP主名"
      }
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

#### 配置管理

**GET /api/config**

Response:
```json
{
  "check_interval_minutes": 30,
  "max_ups": 50,
  "feishu_webhook_url": "https://open.feishu.cn/..."
}
```

**PUT /api/config**

Request:
```json
{
  "check_interval_minutes": 60,
  "feishu_webhook_url": "https://open.feishu.cn/new-webhook"
}
```

Response:
```json
{
  "success": true,
  "updated_keys": ["check_interval_minutes", "feishu_webhook_url"]
}
```

#### 登录状态

**GET /api/login/status**

Response:
```json
{
  "is_logged_in": true,
  "username": "用户名",
  "expires_at": "2026-09-01T00:00:00",
  "days_until_expire": 30
}
```

**GET /api/login/qrcode**

Response:
```json
{
  "qrcode_url": "https://passport.bilibili.com/...",
  "auth_code": "xxx",
  "expires_in": 180
}
```

#### 健康检查

**GET /api/health**

Response:
```json
{
  "status": "ok",
  "database": "connected",
  "version": "2.1.0"
}
```

### 数据库操作接口

```python
# src/database.py

class Database:
    def init_db() -> None:
        """初始化数据库表结构"""
    
    def get_ups(is_monitoring: bool = None) -> list[dict]:
        """获取UP主列表"""
    
    def add_up(mid: int, name: str, face: str = None) -> dict:
        """添加UP主"""
    
    def remove_up(up_id: int) -> bool:
        """移除UP主（软删除）"""
    
    def get_videos(page: int, page_size: int, filters: dict) -> dict:
        """获取视频历史（分页）"""
    
    def add_video(up_id: int, bvid: str, title: str, ...) -> dict:
        """添加视频记录"""
    
    def get_config() -> dict:
        """获取配置"""
    
    def update_config(key: str, value: str) -> bool:
        """更新配置"""
    
    def get_auth() -> dict:
        """获取登录信息"""
    
    def save_auth(cookies: dict) -> bool:
        """保存登录信息"""
```

## Backend Changes

### 新增模块

```
src/
├── database.py        # SQLite 数据库管理
├── models.py          # Pydantic 数据模型
├── web.py             # FastAPI 应用入口
└── api/
    ├── __init__.py
    ├── ups.py         # UP主管理路由
    ├── videos.py      # 推送历史路由
    ├── config.py      # 配置管理路由
    └── login.py       # 登录状态路由
```

### 修改模块

**src/scheduler.py**

当前直接读写 JSON 文件：
```python
def load_history(self):
    with open(self.history_file, "r") as f:
        self.video_history = json.load(f)
```

改造为数据库访问：
```python
def load_history(self):
    # 从数据库加载
    videos = self.db.get_all_videos()
    self.video_history = {"videos": {v["bvid"]: v for v in videos}}
```

**main.py**

增加 Web 服务启动模式：
```python
if args.web:
    import uvicorn
    from src.web import app
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

## File Changes

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/database.py` | 数据库连接、表结构、CRUD 操作 |
| `src/models.py` | Pydantic 请求/响应模型 |
| `src/web.py` | FastAPI 应用配置、路由注册 |
| `src/api/__init__.py` | API 路由模块 |
| `src/api/ups.py` | UP主管理 API |
| `src/api/videos.py` | 推送历史 API |
| `src/api/config.py` | 配置管理 API |
| `src/api/login.py` | 登录状态 API |
| `scripts/migrate_json_to_sqlite.py` | 数据迁移脚本 |

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `src/scheduler.py` | 数据访问从 JSON 改为 SQLite |
| `main.py` | 增加 `--web` 启动模式 |
| `requirements.txt` | 新增 FastAPI、uvicorn、aiosqlite、pydantic 依赖 |
| `config/settings.yaml` | 新增数据库路径配置 |

## Implementation Flow

### Phase 1: 数据库层

1. 创建 `src/database.py`
   - SQLite 连接管理（WAL 模式）
   - 表结构 DDL
   - CRUD 操作封装

2. 编写数据迁移脚本
   - 备份 JSON 文件
   - 解析 UP主 去重
   - 插入数据库
   - 校验记录数

### Phase 2: FastAPI 框架

1. 创建 `src/web.py`
   - FastAPI 应用实例
   - CORS 中间件
   - 日志中间件
   - 路由注册

2. 创建 `src/models.py`
   - UP主请求/响应模型
   - 视频历史响应模型
   - 配置请求/响应模型
   - 错误响应模型

### Phase 3: API 实现

1. UP主管理 API (`src/api/ups.py`)
   - 复用 `BilibiliClient.get_user_info()` 验证 UP主

2. 推送历史 API (`src/api/videos.py`)
   - 分页查询
   - 多条件筛选

3. 配置管理 API (`src/api/config.py`)
   - 参数验证

4. 登录状态 API (`src/api/login.py`)
   - 复用 `BilibiliLogin` 模块

### Phase 4: 调度器改造

1. 修改 `MonitorScheduler`
   - 注入 Database 实例
   - 改写历史记录读写方法
   - 每次循环开始时读取配置

## Error Handling

### 错误码定义

| 错误码 | HTTP状态码 | 说明 |
|--------|-----------|------|
| `UP_NOT_FOUND` | 404 | UP主不存在 |
| `INVALID_MID` | 400 | mid 格式无效 |
| `BILIBILI_API_ERROR` | 502 | B站 API 调用失败 |
| `RATE_LIMITED` | 429 | 请求过于频繁 |
| `DATABASE_ERROR` | 500 | 数据库操作失败 |
| `CONFIG_VALIDATION_ERROR` | 400 | 配置参数无效 |

### 错误响应格式

```json
{
  "error": "错误描述",
  "code": "ERROR_CODE",
  "details": {}
}
```

### SQLite 并发处理

1. 启用 WAL 模式
   ```python
   conn.execute("PRAGMA journal_mode=WAL")
   ```

2. 写入重试机制
   ```python
   @retry_on_sqlite_busy(max_retries=3, delay=0.1)
   def write_to_db():
       ...
   ```

## Testing Strategy

### 单元测试

- `tests/test_database.py` - 数据库 CRUD 操作测试
- `tests/test_api_ups.py` - UP主 API 测试
- `tests/test_api_videos.py` - 视频历史 API 测试
- `tests/test_api_config.py` - 配置 API 测试
- `tests/test_api_login.py` - 登录 API 测试

### 集成测试

- 完整 API 流程测试
- 数据迁移脚本测试
- 并发写入测试

### 测试数据库

使用内存数据库 `:memory:` 运行测试，隔离生产数据。

### API 测试示例

```python
def test_add_up(client):
    response = client.post("/api/ups", json={"mid": 123456})
    assert response.status_code == 200
    data = response.json()
    assert data["mid"] == 123456
    assert "name" in data
```

## Deployment

### 启动方式

**监控进程**：
```bash
python main.py
```

**Web 服务**：
```bash
uvicorn src.web:app --host 127.0.0.1 --port 8000
```

### systemd 服务配置

**监控服务** (`monitor.service`)：
```ini
[Unit]
Description=B站UP主监控服务

[Service]
ExecStart=/path/to/python main.py
WorkingDirectory=/path/to/project
```

**Web 服务** (`monitor-web.service`)：
```ini
[Unit]
Description=B站UP主监控 Web 服务

[Service]
ExecStart=/path/to/uvicorn src.web:app --host 127.0.0.1 --port 8000
WorkingDirectory=/path/to/project
```
