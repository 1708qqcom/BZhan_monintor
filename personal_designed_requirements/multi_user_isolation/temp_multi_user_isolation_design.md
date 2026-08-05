# Technical Design - 多用户隔离系统

## Overview

将当前单用户架构改造为多用户架构，核心思路：
- 新增 `users` 表存储用户信息
- 改造 `auth`/`ups`/`videos`/`config` 表，增加 `user_id` 字段
- Web 后台从固定密码改为数据库认证
- B站扫码登录关联到当前用户
- 监控线程从单用户改为轮询所有用户

---

## Architecture

### 当前架构（单用户）
```
┌─────────────┐
│    auth     │
│ id=1 (固定) │
│   cookies   │
└──────┬──────┘
       │
       ▼
┌─────────────┐         ┌─────────────┐
│    ups      │────────▶│   videos    │
└─────────────┘         └─────────────┘
```

### 改造后架构（多用户）
```
┌─────────────┐
│    users    │
│ id          │
│ username    │
│ password    │
│ is_admin    │
└──────┬──────┘
       │
       ├─────────────────┐
       │                 │
       ▼                 ▼
┌─────────────┐   ┌─────────────┐
│    auth     │   │    ups      │
│ user_id     │   │ user_id     │
│ cookies     │   │ mid         │
└─────────────┘   └──────┬──────┘
                         │
                         ▼
                  ┌─────────────┐
                  │   videos    │
                  │ (通过up关联)│
                  └─────────────┘
```

---

## Data Model

### 新增 users 表
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,  -- 明文存储
    is_admin INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 改造 auth 表
```sql
-- 当前结构（单条记录）
CREATE TABLE auth (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    cookies TEXT,
    created_at TEXT,
    expires_at TEXT
);

-- 改造后（每用户一条记录）
DROP TABLE auth;
CREATE TABLE auth (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    cookies TEXT,
    created_at TEXT,
    expires_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX idx_auth_user_id ON auth(user_id);
```

### 改造 ups 表
```sql
-- 新增 user_id 字段
ALTER TABLE ups ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX idx_ups_user_id ON ups(user_id);

-- 修改唯一约束：mid 改为 (user_id, mid) 联合唯一
-- SQLite 不支持修改约束，需要重建表
```

### 改造 config 表
```sql
-- 配置也需要按用户隔离（如飞书Webhook可能不同）
ALTER TABLE config ADD COLUMN user_id INTEGER;
CREATE INDEX idx_config_user_id ON config(user_id);

-- 全局配置（如检查间隔）user_id 为 NULL
```

### 数据迁移策略
```sql
-- 1. 创建默认管理员用户
INSERT INTO users (id, username, password, is_admin, created_at, updated_at)
VALUES (1, 'admin', 'Huisec@123', 1, datetime('now'), datetime('now'));

-- 2. 关联现有数据到默认用户
UPDATE ups SET user_id = 1;
UPDATE auth SET user_id = 1 WHERE id = 1;

-- 3. auth 表需要重建（添加 user_id）
-- 临时保存数据 → 删除表 → 重建表 → 恢复数据
```

---

## API / Interface

### 新增接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/auth/register` | POST | 用户注册 |
| `/auth/login` | POST | 用户登录（已存在，需改造） |
| `/auth/logout` | POST | 用户登出（已存在） |
| `/api/users` | GET | 管理员获取用户列表 |
| `/api/users/{id}` | DELETE | 管理员删除用户 |

### 改造接口

| 接口 | 改造内容 |
|------|----------|
| `GET /api/ups` | 增加用户过滤，普通用户只返回自己的数据 |
| `POST /api/ups` | 关联到当前用户 |
| `POST /api/ups/sync` | 使用当前用户的B站Cookie |
| `GET /api/videos` | 增加用户过滤 |
| `GET /api/login/status` | 查询当前用户的B站登录状态 |
| `POST /api/login/qrcode` | 临时状态关联到当前用户 |
| `POST /api/login/poll` | Cookie 保存到当前用户 |
| `GET /api/config` | 返回当前用户的配置 |
| `PUT /api/config` | 更新当前用户的配置 |

---

## Frontend Changes

### 新增页面/组件

| 文件 | 说明 |
|------|------|
| `templates/register.html` | 注册页面 |
| `templates/users.html` | 用户管理页面（管理员） |

### 改造页面

| 文件 | 改造内容 |
|------|----------|
| `templates/login.html` | 增加注册入口 |
| `templates/base.html` | 显示当前用户名、退出按钮、管理员入口 |
| `templates/dashboard.html` | 普通用户只显示自己的统计，管理员显示全局统计 |
| `templates/ups.html` | 管理员增加用户筛选下拉框 |
| `templates/videos.html` | 管理员增加用户筛选下拉框 |

### Session 存储

```python
# 当前
request.session["authenticated"] = True

# 改造后
request.session["user_id"] = 1
request.session["username"] = "admin"
request.session["is_admin"] = True
```

---

## Backend Changes

### src/database.py

**新增方法**：
```python
def add_user(username: str, password: str, is_admin: bool = False) -> int
def get_user_by_username(username: str) -> Optional[dict]
def get_user_by_id(user_id: int) -> Optional[dict]
def get_all_users() -> list[dict]
def delete_user(user_id: int) -> bool

# 改造方法签名
def get_ups(user_id: int = None, is_monitoring: Optional[bool] = None) -> list[dict]
def get_up_by_mid(user_id: int, mid: int) -> Optional[dict]
def add_up(user_id: int, mid: int, name: str, face: str = "") -> int
def get_auth(user_id: int) -> Optional[dict]
def save_auth(user_id: int, cookies: dict, expires_at: Optional[str] = None)
```

### src/web.py

**改造认证中间件**：
```python
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 从 Session 读取 user_id
        user_id = request.session.get("user_id")
        if not user_id:
            # 未登录，跳转登录页
            return RedirectResponse(url="/auth/login", status_code=302)
        
        # 已登录，继续处理
        return await call_next(request)
```

**新增注册路由**：
```python
@app.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request):
    # 渲染注册页面

@app.post("/auth/register")
async def register_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    # 处理注册逻辑
    # 检查用户名是否存在
    # 创建用户
    # 自动登录
```

### src/api/login.py

**改造B站登录**：
```python
# 临时状态存储改为用户级别
_auth_code_store = {}  # {user_id: auth_code}

@router.get("/qrcode")
async def get_qrcode(request: Request):
    user_id = request.session.get("user_id")
    # 生成二维码
    # 保存到 _auth_code_store[user_id] = auth_code

@router.post("/poll")
async def poll_scan_result(request: Request, db: Database = Depends(get_db)):
    user_id = request.session.get("user_id")
    auth_code = _auth_code_store.get(user_id)
    # 轮询扫码结果
    # Cookie 保存到 db.save_auth(user_id, cookies, expires_at)
```

### src/api/ups.py

**改造查询接口**：
```python
@router.get("")
async def get_ups(request: Request, db: Database = Depends(get_db)):
    user_id = request.session.get("user_id")
    is_admin = request.session.get("is_admin")
    
    if is_admin:
        # 管理员可查看所有用户，增加筛选参数
        filter_user_id = request.query_params.get("user_id")
        ups = db.get_ups(user_id=filter_user_id)
    else:
        # 普通用户只查看自己的
        ups = db.get_ups(user_id=user_id)
```

### src/scheduler.py

**改造监控线程**：
```python
def check_all_users(self):
    """轮询所有用户检查新视频"""
    users = self.db.get_all_users_with_valid_auth()
    
    for user in users:
        try:
            # 获取该用户的 UP 主列表
            ups = self.db.get_ups(user_id=user.id, is_monitoring=True)
            
            # 检查新视频
            for up in ups:
                videos = self.bilibili_client.get_up_videos(up.mid)
                # ...
                
                # 推送时使用该用户的飞书Webhook
                feishu_webhook = self.db.get_config_value(
                    "feishu_webhook_url", 
                    user_id=user.id
                )
                
        except Exception as e:
            logger.error(f"用户 {user.username} 检查失败: {e}")
            # 不影响其他用户
```

---

## File Changes

### 新增文件
- `templates/register.html` - 注册页面
- `templates/users.html` - 用户管理页面（管理员）
- `scripts/migrate_to_multi_user.py` - 数据迁移脚本

### 核心修改文件
- `src/database.py` - 新增用户表，改造所有查询方法
- `src/models.py` - 新增用户相关模型
- `src/web.py` - 改造认证流程，新增注册路由
- `src/api/login.py` - 改造B站登录关联用户
- `src/api/ups.py` - 增加用户过滤
- `src/api/videos.py` - 增加用户过滤
- `src/api/config.py` - 增加用户过滤
- `src/sync_service.py` - 同步时关联用户
- `src/scheduler.py` - 改为多用户轮询

### 前端修改文件
- `templates/login.html` - 增加注册入口
- `templates/base.html` - 显示用户信息
- `static/js/main.js` - 适配新API

---

## Implementation Flow

### 阶段1：数据库改造（Day 1）
1. 编写数据迁移脚本 `scripts/migrate_to_multi_user.py`
2. 新增 `users` 表
3. 改造 `auth` 表（重建）
4. 改造 `ups` 表（添加 `user_id`）
5. 改造 `config` 表（添加 `user_id`）
6. 创建默认管理员用户
7. 关联现有数据到默认用户

### 阶段2：用户系统（Day 1-2）
1. 在 `src/database.py` 新增用户相关方法
2. 在 `src/models.py` 新增用户模型
3. 在 `src/web.py` 实现注册/登录功能
4. 创建 `templates/register.html`
5. 改造认证中间件
6. 测试用户注册/登录

### 阶段3：API 改造（Day 2-3）
1. 改造 `src/api/login.py`（B站登录关联用户）
2. 改造 `src/api/ups.py`（用户过滤）
3. 改造 `src/api/videos.py`（用户过滤）
4. 改造 `src/api/config.py`（用户过滤）
5. 改造 `src/sync_service.py`（同步关联用户）
6. 测试 API 隔离效果

### 阶段4：监控线程改造（Day 3）
1. 改造 `src/scheduler.py`（多用户轮询）
2. 测试多用户监控

### 阶段5：前端改造（Day 3-4）
1. 改造 `templates/base.html`（显示用户信息）
2. 改造 `templates/ups.html`（管理员筛选）
3. 改造 `templates/videos.html`（管理员筛选）
4. 改造 `static/js/main.js`（适配新 API）
5. 测试前端交互

### 阶段6：测试与优化（Day 4-5）
1. 编写测试用例
2. 端到端测试
3. 性能测试（监控线程）
4. Bug 修复

---

## Error Handling

### 用户名已存在
```python
try:
    db.add_user(username, password)
except sqlite3.IntegrityError:
    raise HTTPException(status_code=400, detail="用户名已存在")
```

### 用户未绑定B站账号
```python
auth = db.get_auth(user_id)
if not auth or not auth.get("cookies"):
    raise HTTPException(status_code=400, detail="请先绑定B站账号")
```

### B站账号过期
```python
if auth.expires_at and datetime.fromisoformat(auth.expires_at) < datetime.now():
    # 标记过期，跳过监控
    logger.warning(f"用户 {user_id} B站账号已过期")
    continue
```

---

## Testing Strategy

### 单元测试
- 测试用户注册/登录
- 测试用户数据隔离（UP主、视频、配置）
- 测试 B站登录关联用户

### 集成测试
- 测试多用户同步关注列表
- 测试多用户监控线程
- 测试管理员权限

### 端到端测试
```bash
# 1. 注册两个用户
curl -X POST /auth/register -d "username=user1&password=123"
curl -X POST /auth/register -d "username=user2&password=123"

# 2. 分别登录并绑定B站账号
# 3. 分别同步关注列表
# 4. 验证用户1看不到用户2的UP主
# 5. 管理员登录，验证可以看到所有用户数据
```