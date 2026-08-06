# Technical Design: User Onboarding Flow

## Overview

### 设计目标

为新用户引导流程提供技术实现方案，包括：
- 数据库进度跟踪
- API接口设计
- 前端引导页面
- 仪表盘进度提示

### 技术方案

采用**独立引导页面**方案：
- 用户注册后跳转到 `/onboarding` 引导页
- 引导页面是单页应用，通过步骤索引切换内容
- 每步完成后调用API更新进度，自动跳转下一步
- 所有步骤完成后跳转到仪表盘

### 架构影响

```
┌─────────────────────────────────────────────────────┐
│                    前端层                            │
├─────────────────────────────────────────────────────┤
│  新增: onboarding.html         │  修改: dashboard.html│
│  新增: onboarding.js           │  修改: login.html    │
│                                │  修改: register.html │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│                    API层                             │
├─────────────────────────────────────────────────────┤
│  新增: GET  /api/onboarding/status                  │
│  新增: POST /api/onboarding/complete-step           │
│  新增: POST /api/onboarding/skip-step               │
│  修改: POST /auth/register (跳转逻辑)               │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│                    数据层                            │
├─────────────────────────────────────────────────────┤
│  新增表: user_onboarding                            │
│  新增方法: Database.init_onboarding_progress()      │
│  新增方法: Database.get_onboarding_progress()       │
│  新增方法: Database.update_onboarding_step()        │
│  新增方法: Database.calculate_progress()            │
└─────────────────────────────────────────────────────┘
```


## Architecture

### 系统架构图

```
┌──────────────┐
│   Browser    │
└──────┬───────┘
       │ HTTP
       ↓
┌──────────────────────────────────────────────────┐
│              FastAPI Application                 │
├──────────────────────────────────────────────────┤
│  AuthMiddleware                                  │
│    ├─ 白名单: /auth/login, /auth/register        │
│    ├─ 检查: user_onboarding 记录                 │
│    └─ 未完成引导 → 重定向到 /onboarding           │
├──────────────────────────────────────────────────┤
│  Routers                                         │
│    ├─ /auth/*     → 认证路由                     │
│    ├─ /onboarding → 引导页面路由                 │
│    ├─ /api/onboarding → 引导API路由              │
│    └─ /api/*      → 业务API路由                  │
└──────────────────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────────┐
│              SQLite Database                     │
├──────────────────────────────────────────────────┤
│  users              用户表                       │
│  user_onboarding    引导进度表（新增）            │
│  auth               B站登录信息表                │
│  config             配置表                       │
│  ups                UP主表                       │
└──────────────────────────────────────────────────┘
```


## Data Model

### 新增表: user_onboarding

```sql
CREATE TABLE user_onboarding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    
    -- 步骤完成状态（0=未完成，1=已完成）
    step1_completed INTEGER DEFAULT 0,  -- B站登录
    step2_completed INTEGER DEFAULT 0,  -- 飞书配置
    step3_completed INTEGER DEFAULT 0,  -- UP主选择
    
    -- 步骤跳过状态（0=未跳过，1=已跳过）
    step1_skipped INTEGER DEFAULT 0,
    step2_skipped INTEGER DEFAULT 0,
    step3_skipped INTEGER DEFAULT 0,
    
    -- 当前步骤（1-3）
    current_step INTEGER DEFAULT 1,
    
    -- 时间戳
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX idx_user_onboarding_user_id ON user_onboarding(user_id);
```

### 数据模型定义

```python
# src/models.py

from pydantic import BaseModel
from typing import Optional

class OnboardingProgress(BaseModel):
    """引导进度响应模型"""
    user_id: int
    current_step: int  # 1-3
    step1_completed: bool
    step1_skipped: bool
    step2_completed: bool
    step2_skipped: bool
    step3_completed: bool
    step3_skipped: bool
    progress_percent: int  # 0-100
    is_completed: bool  # 所有步骤完成或跳过

class OnboardingStepRequest(BaseModel):
    """引导步骤请求模型"""
    step: int  # 1-3

class OnboardingStatusResponse(BaseModel):
    """引导状态响应模型"""
    has_onboarding_record: bool  # 是否有引导记录
    progress: Optional[OnboardingProgress] = None
```


## API / Interface

### 新增API

#### GET /api/onboarding/status

**功能**：获取当前用户的引导进度

**请求**：无（从Session获取user_id）

**响应**：
```json
{
  "has_onboarding_record": true,
  "progress": {
    "user_id": 1,
    "current_step": 2,
    "step1_completed": true,
    "step1_skipped": false,
    "step2_completed": false,
    "step2_skipped": false,
    "step3_completed": false,
    "step3_skipped": false,
    "progress_percent": 33,
    "is_completed": false
  }
}
```

**逻辑**：
1. 从Session获取user_id
2. 查询user_onboarding表
3. 如果不存在记录，返回 `has_onboarding_record: false`
4. 计算progress_percent = (完成步骤数 / 3) * 100


#### POST /api/onboarding/complete-step

**功能**：标记某一步骤为"已完成"

**请求**：
```json
{
  "step": 1  // 1-3
}
```

**响应**：
```json
{
  "message": "步骤1已完成",
  "progress": {
    "current_step": 2,
    "progress_percent": 33
  }
}
```

**逻辑**：
1. 验证step参数（1-3）
2. 更新user_onboarding表：step{N}_completed = 1
3. 更新current_step = step + 1
4. 返回最新进度


#### POST /api/onboarding/skip-step

**功能**：标记某一步骤为"已跳过"

**请求**：
```json
{
  "step": 2
}
```

**响应**：
```json
{
  "message": "步骤2已跳过",
  "progress": {
    "current_step": 3,
    "progress_percent": 33
  }
}
```

**逻辑**：
1. 验证step参数（1-3）
2. 更新user_onboarding表：step{N}_skipped = 1
3. 更新current_step = step + 1
4. 返回最新进度


### 修改API

#### POST /auth/register

**修改点**：注册成功后创建引导进度记录

```python
# 原代码（web.py:452-458）
request.session["user_id"] = user_id
request.session["username"] = username
request.session["is_admin"] = False
return RedirectResponse(url="/", status_code=302)

# 修改后
request.session["user_id"] = user_id
request.session["username"] = username
request.session["is_admin"] = False

# 创建引导进度记录
db.init_onboarding_progress(user_id)

return RedirectResponse(url="/onboarding", status_code=302)
```


## Frontend Changes

### 新增页面: templates/onboarding.html

**结构**：
```html
{% extends "base.html" %}

{% block content %}
<!-- 顶部进度条 -->
<div class="progress-bar">
  <div class="step active">步骤1</div>
  <div class="step">步骤2</div>
  <div class="step">步骤3</div>
</div>

<!-- 内容区 -->
<div id="step-content">
  <!-- 动态加载步骤内容 -->
</div>

<!-- 底部按钮 -->
<div class="actions">
  <button id="btn-prev">上一步</button>
  <button id="btn-next">下一步</button>
  <button id="btn-skip">跳过</button>
  <button id="btn-complete">完成</button>
</div>
{% endblock %}
```

**步骤内容**：
- 步骤1：复用 [bilibili_login.html](templates/bilibili_login.html) 的二维码组件
- 步骤2：复用 [config.html](templates/config.html) 的飞书配置表单
- 步骤3：改造 [ups.html](templates/ups.html) 的UP主列表为批量勾选


### 新增脚本: static/js/onboarding.js

**核心逻辑**：
```javascript
class OnboardingManager {
  constructor() {
    this.currentStep = 1;
    this.progress = null;
  }

  // 加载进度
  async loadProgress() {
    const response = await fetchAPI('/api/onboarding/status');
    this.progress = response.progress;
    this.currentStep = response.progress?.current_step || 1;
    this.renderStep(this.currentStep);
  }

  // 渲染步骤
  renderStep(step) {
    const stepContents = {
      1: this.renderStep1,
      2: this.renderStep2,
      3: this.renderStep3
    };
    stepContents[step]?.();
    this.updateProgressBar();
  }

  // 完成步骤
  async completeStep(step) {
    await fetchAPI('/api/onboarding/complete-step', {
      method: 'POST',
      body: JSON.stringify({ step })
    });
    
    if (step < 3) {
      this.currentStep = step + 1;
      this.renderStep(this.currentStep);
    } else {
      window.location.href = '/';
    }
  }

  // 跳过步骤
  async skipStep(step) {
    await fetchAPI('/api/onboarding/skip-step', {
      method: 'POST',
      body: JSON.stringify({ step })
    });
    
    if (step < 3) {
      this.currentStep = step + 1;
      this.renderStep(this.currentStep);
    } else {
      window.location.href = '/';
    }
  }
}
```


### 修改页面: templates/dashboard.html

**新增引导进度卡片**：
```html
{% if not onboarding_completed %}
<div class="onboarding-reminder-card">
  <div class="icon">📋</div>
  <div class="content">
    <h3>配置进度 {{ onboarding_progress }}%</h3>
    <p>完成配置以开始使用监控功能</p>
  </div>
  <a href="/onboarding" class="btn">继续配置</a>
</div>
{% endif %}
```

**后端传递数据**：
```python
# web.py 的 root() 函数
@app.get("/")
async def root(request: Request):
    # 查询引导进度
    db = Database()
    progress = db.get_onboarding_progress(user_id)
    onboarding_completed = progress and progress.get("is_completed", True)
    onboarding_progress = progress.get("progress_percent", 100) if progress else 100
    
    return HTMLResponse(content=template.render(
        username=request.session.get("username", ""),
        is_admin=request.session.get("is_admin", False),
        active_page="dashboard",
        onboarding_completed=onboarding_completed,
        onboarding_progress=onboarding_progress
    ))
```


## Backend Changes

### 新增路由: src/api/onboarding.py

```python
"""
引导流程 API

端点：
- GET /api/onboarding/status - 获取引导进度
- POST /api/onboarding/complete-step - 完成步骤
- POST /api/onboarding/skip-step - 跳过步骤
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from src.database import Database
from src.models import OnboardingStatusResponse, OnboardingStepRequest, SuccessResponse

logger = logging.getLogger("monitor.api.onboarding")
router = APIRouter(prefix="/api/onboarding", tags=["引导流程"])

def get_db() -> Database:
    return Database()

@router.get("/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(request: Request, db: Database = Depends(get_db)):
    """获取引导进度"""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    
    progress = db.get_onboarding_progress(user_id)
    
    if not progress:
        return OnboardingStatusResponse(
            has_onboarding_record=False,
            progress=None
        )
    
    # 计算进度百分比
    completed_steps = sum([
        progress["step1_completed"] or progress["step1_skipped"],
        progress["step2_completed"] or progress["step2_skipped"],
        progress["step3_completed"] or progress["step3_skipped"]
    ])
    progress_percent = int((completed_steps / 3) * 100)
    
    # 判断是否完成
    is_completed = completed_steps == 3
    
    return OnboardingStatusResponse(
        has_onboarding_record=True,
        progress={
            "user_id": user_id,
            "current_step": progress["current_step"],
            "step1_completed": bool(progress["step1_completed"]),
            "step1_skipped": bool(progress["step1_skipped"]),
            "step2_completed": bool(progress["step2_completed"]),
            "step2_skipped": bool(progress["step2_skipped"]),
            "step3_completed": bool(progress["step3_completed"]),
            "step3_skipped": bool(progress["step3_skipped"]),
            "progress_percent": progress_percent,
            "is_completed": is_completed
        }
    )

@router.post("/complete-step", response_model=SuccessResponse)
async def complete_onboarding_step(
    request: Request,
    body: OnboardingStepRequest,
    db: Database = Depends(get_db)
):
    """完成步骤"""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    
    if body.step not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="步骤编号无效")
    
    db.update_onboarding_step(user_id, body.step, completed=True)
    logger.info(f"用户完成步骤{body.step}: user_id={user_id}")
    
    return SuccessResponse(message=f"步骤{body.step}已完成")

@router.post("/skip-step", response_model=SuccessResponse)
async def skip_onboarding_step(
    request: Request,
    body: OnboardingStepRequest,
    db: Database = Depends(get_db)
):
    """跳过步骤"""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    
    if body.step not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="步骤编号无效")
    
    db.update_onboarding_step(user_id, body.step, skipped=True)
    logger.info(f"用户跳过步骤{body.step}: user_id={user_id}")
    
    return SuccessResponse(message=f"步骤{body.step}已跳过")
```

### 新增数据库方法: src/database.py

```python
def init_onboarding_progress(self, user_id: int) -> int:
    """
    初始化引导进度
    
    Args:
        user_id: 用户ID
    
    Returns:
        新记录的ID
    """
    logger.info(f"初始化引导进度: user_id={user_id}")
    
    now = datetime.now().isoformat()
    
    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_onboarding 
            (user_id, step1_completed, step1_skipped, step2_completed, step2_skipped, 
             step3_completed, step3_skipped, current_step, created_at, updated_at)
            VALUES (?, 0, 0, 0, 0, 0, 0, 1, ?, ?)
        """, (user_id, now, now))
        
        conn.commit()
        onboarding_id = cursor.lastrowid
        
        logger.info(f"引导进度初始化成功: id={onboarding_id}, user_id={user_id}")
        return onboarding_id

def get_onboarding_progress(self, user_id: int) -> Optional[dict]:
    """
    获取引导进度
    
    Args:
        user_id: 用户ID
    
    Returns:
        引导进度字典，不存在返回None
    """
    logger.debug(f"查询引导进度: user_id={user_id}")
    
    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, step1_completed, step1_skipped, 
                   step2_completed, step2_skipped, step3_completed, step3_skipped,
                   current_step, created_at, updated_at
            FROM user_onboarding
            WHERE user_id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        else:
            logger.debug(f"引导进度不存在: user_id={user_id}")
            return None

def update_onboarding_step(
    self, 
    user_id: int, 
    step: int, 
    completed: bool = False, 
    skipped: bool = False
) -> bool:
    """
    更新引导步骤状态
    
    Args:
        user_id: 用户ID
        step: 步骤编号（1-3）
        completed: 是否完成
        skipped: 是否跳过
    
    Returns:
        成功返回True
    """
    logger.info(f"更新引导步骤: user_id={user_id}, step={step}, completed={completed}, skipped={skipped}")
    
    now = datetime.now().isoformat()
    
    with self._get_connection() as conn:
        cursor = conn.cursor()
        
        # 构造更新字段
        if completed:
            update_field = f"step{step}_completed = 1"
        elif skipped:
            update_field = f"step{step}_skipped = 1"
        else:
            raise ValueError("必须指定completed或skipped")
        
        # 计算下一步
        next_step = step + 1 if step < 3 else 3
        
        cursor.execute(f"""
            UPDATE user_onboarding
            SET {update_field}, current_step = ?, updated_at = ?
            WHERE user_id = ?
        """, (next_step, now, user_id))
        
        conn.commit()
        affected = cursor.rowcount
        
        if affected > 0:
            logger.info(f"引导步骤更新成功: user_id={user_id}")
            return True
        else:
            logger.warning(f"引导进度不存在: user_id={user_id}")
            return False
```

### 修改注册流程: src/web.py

```python
# 在 register_submit() 函数中添加

# 原代码（web.py:452-458）
request.session["user_id"] = user_id
request.session["username"] = username
request.session["is_admin"] = False
logger.info(f"自动登录成功: username={username}")
return RedirectResponse(url="/", status_code=302)

# 修改后
request.session["user_id"] = user_id
request.session["username"] = username
request.session["is_admin"] = False

# 创建引导进度记录
try:
    db.init_onboarding_progress(user_id)
    logger.info(f"引导进度已初始化: user_id={user_id}")
except Exception as e:
    logger.error(f"初始化引导进度失败: {e}")

logger.info(f"自动登录成功: username={username}")
return RedirectResponse(url="/onboarding", status_code=302)
```


## File Changes

### 新增文件

| 文件路径 | 说明 |
|---------|------|
| `templates/onboarding.html` | 引导主页面模板 |
| `static/js/onboarding.js` | 引导流程交互逻辑 |
| `src/api/onboarding.py` | 引导API路由 |
| `docs/onboarding_guide.md` | 引导流程使用文档（可选） |

### 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `src/web.py` | 添加引导页面路由、修改注册跳转逻辑 |
| `src/database.py` | 添加user_onboarding表、新增引导相关方法 |
| `src/models.py` | 添加引导相关数据模型 |
| `templates/dashboard.html` | 添加引导进度提示卡片 |
| `templates/base.html` | 添加引导进度全局样式（可选） |


## Implementation Flow

### 阶段一：数据库设计（30分钟）

1. 在 `src/database.py` 的 `init_db()` 中添加 `user_onboarding` 表创建逻辑
2. 添加 `init_onboarding_progress()` 方法
3. 添加 `get_onboarding_progress()` 方法
4. 添加 `update_onboarding_step()` 方法
5. 编写单元测试验证数据库操作

### 阶段二：API开发（1小时）

1. 创建 `src/api/onboarding.py` 文件
2. 实现 `GET /api/onboarding/status` 接口
3. 实现 `POST /api/onboarding/complete-step` 接口
4. 实现 `POST /api/onboarding/skip-step` 接口
5. 在 `src/web.py` 中注册路由
6. 使用 Swagger UI 测试接口

### 阶段三：前端页面（2小时）

1. 创建 `templates/onboarding.html` 基础结构
2. 实现步骤1内容（复用B站登录组件）
3. 实现步骤2内容（复用飞书配置表单）
4. 实现步骤3内容（UP主批量勾选）
5. 创建 `static/js/onboarding.js` 交互逻辑
6. 测试步骤切换和API调用

### 阶段四：流程集成（1小时）

1. 修改 `src/web.py` 的注册流程，创建引导记录
2. 修改 `templates/dashboard.html`，添加进度提示卡片
3. 测试完整引导流程
4. 测试老用户兼容性

### 阶段五：测试与优化（1小时）

1. 测试新用户注册 → 引导流程
2. 测试引导中断 → 恢复流程
3. 测试跳过功能
4. 测试老用户登录（无引导记录）
5. 移动端适配测试
6. 性能优化


## Error Handling

### 错误场景与处理

| 错误场景 | HTTP状态码 | 错误信息 | 处理方案 |
|---------|-----------|---------|---------|
| 用户未登录 | 401 | "请先登录" | 前端跳转到登录页 |
| 步骤编号无效 | 400 | "步骤编号无效" | 前端校验步骤编号（1-3） |
| 引导进度不存在 | 200 | `has_onboarding_record: false` | 老用户兼容处理 |
| 数据库操作失败 | 500 | "操作失败" | 前端显示错误提示，记录日志 |

### 老用户兼容性处理

```python
# 在 AuthMiddleware 中添加逻辑

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # ... 现有逻辑 ...
        
        # 检查引导进度（仅对新用户）
        if user_id and not is_whitelisted:
            db = Database()
            progress = db.get_onboarding_progress(user_id)
            
            # 如果没有引导记录，说明是老用户，跳过引导
            if not progress and not request.url.path.startswith("/onboarding"):
                # 可选：为老用户创建"已完成"的引导记录
                db.init_onboarding_progress(user_id)
                db.update_onboarding_step(user_id, 1, completed=True)
                db.update_onboarding_step(user_id, 2, completed=True)
                db.update_onboarding_step(user_id, 3, completed=True)
        
        return await call_next(request)
```


## Testing Strategy

### 单元测试

**文件**：`tests/test_onboarding.py`

```python
import pytest
from src.database import Database

def test_init_onboarding_progress():
    """测试引导进度初始化"""
    db = Database()
    db.init_db()
    
    # 创建测试用户
    user_id = db.add_user("test_user", "password123")
    
    # 初始化引导进度
    onboarding_id = db.init_onboarding_progress(user_id)
    
    # 验证
    assert onboarding_id is not None
    
    progress = db.get_onboarding_progress(user_id)
    assert progress["current_step"] == 1
    assert progress["step1_completed"] == 0

def test_update_onboarding_step():
    """测试引导步骤更新"""
    db = Database()
    db.init_db()
    
    user_id = db.add_user("test_user2", "password123")
    db.init_onboarding_progress(user_id)
    
    # 完成步骤1
    success = db.update_onboarding_step(user_id, 1, completed=True)
    assert success is True
    
    progress = db.get_onboarding_progress(user_id)
    assert progress["step1_completed"] == 1
    assert progress["current_step"] == 2

def test_skip_onboarding_step():
    """测试跳过步骤"""
    db = Database()
    db.init_db()
    
    user_id = db.add_user("test_user3", "password123")
    db.init_onboarding_progress(user_id)
    
    # 跳过步骤2
    success = db.update_onboarding_step(user_id, 2, skipped=True)
    assert success is True
    
    progress = db.get_onboarding_progress(user_id)
    assert progress["step2_skipped"] == 1
```

### 集成测试

**测试场景**：
1. 新用户注册 → 自动跳转引导页
2. 完成所有步骤 → 跳转仪表盘
3. 跳过某一步骤 → 状态正确记录
4. 中断引导 → 下次登录继续
5. 老用户登录 → 不触发引导

### 性能测试

**测试指标**：
- 引导页面加载时间 < 2秒
- API响应时间 < 500ms
- 数据库查询时间 < 100ms


## Deployment Notes

### 数据库迁移

**方式1：自动迁移**
- 在 `Database.init_db()` 中添加表创建逻辑
- 重启服务自动创建新表

**方式2：手动迁移**
```sql
-- 执行SQL脚本
CREATE TABLE user_onboarding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    step1_completed INTEGER DEFAULT 0,
    step1_skipped INTEGER DEFAULT 0,
    step2_completed INTEGER DEFAULT 0,
    step2_skipped INTEGER DEFAULT 0,
    step3_completed INTEGER DEFAULT 0,
    step3_skipped INTEGER DEFAULT 0,
    current_step INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_user_onboarding_user_id ON user_onboarding(user_id);

-- 为现有用户创建引导记录（可选）
INSERT INTO user_onboarding (user_id, step1_completed, step2_completed, step3_completed, current_step, created_at, updated_at)
SELECT id, 1, 1, 1, 4, datetime('now'), datetime('now')
FROM users;
```

### 回滚方案

如果引导功能出现问题：
1. 移除 `/onboarding` 路由
2. 注释注册流程中的引导初始化代码
3. 隐藏仪表盘进度卡片
4. 删除 `user_onboarding` 表（可选）
