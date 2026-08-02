# Technical Design - 简易 Web 管理页面

## Overview

采用 **FastAPI + Jinja2 + Tailwind CSS CDN** 的轻量级方案，为 B站UP主监控服务提供 Web 管理界面。

**技术栈**：
- 模板引擎：Jinja2
- 样式框架：Tailwind CSS CDN（无需构建）
- 交互脚本：原生 JavaScript
- 认证方式：Session + Cookie（密码 `123456`）
- 响应式：移动端优先设计

---

## Architecture

### 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Web 浏览器                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 仪表盘   │ │ UP主管理 │ │ 推送历史 │ │ 配置管理 │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                          ↖ AJAX ↗                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI + Jinja2                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 页面路由     │  │ 认证中间件   │  │ API 路由     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      SQLite 数据库                           │
│         ups        videos        config        auth          │
└─────────────────────────────────────────────────────────────┘
```

### 模块职责

| 模块 | 职责 |
|------|------|
| `src/web.py` | FastAPI 应用配置、Jinja2 模板配置、静态文件挂载、认证中间件 |
| `src/auth_middleware.py` | Session 认证逻辑、密码验证、登录/登出处理 |
| `templates/*.html` | 5 个页面模板 + 1 个基础布局模板 |
| `static/js/main.js` | 前端交互脚本（表单提交、轮询、搜索） |
| `static/css/custom.css` | 自定义样式补充（可选） |

---

## Data Model

### Session 数据

```python
# 存储在服务器端
session_data = {
    "authenticated": True,
    "login_time": "2026-08-02T14:30:00",
}
```

### Cookie 结构

```
session_id=abc123; Path=/; HttpOnly; Max-Age=86400
```

**Session 过期时间**：24 小时

---

## API / Interface

### 新增页面路由

| 端点 | 方法 | 功能 | 模板 |
|------|------|------|------|
| `/` | GET | 仪表盘页面 | `dashboard.html` |
| `/login` | GET | 登录页面 | `login_page.html` |
| `/auth/login` | POST | 处理登录 | - |
| `/auth/logout` | POST | 处理登出 | - |
| `/ups` | GET | UP主管理页面 | `ups.html` |
| `/videos` | GET | 推送历史页面 | `videos.html` |
| `/config` | GET | 配置管理页面 | `config.html` |
| `/bilibili-login` | GET | B站登录管理页面 | `bilibili_login.html` |

### 现有 API 接口（复用）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/ups` | GET | 获取 UP主列表 |
| `/api/ups` | POST | 添加 UP主 |
| `/api/ups/{id}` | DELETE | 移除 UP主 |
| `/api/videos` | GET | 推送历史（分页） |
| `/api/config` | GET/PUT | 配置管理 |
| `/api/login/status` | GET | B站登录状态 |
| `/api/login/qrcode` | GET | B站登录二维码 |
| `/api/health` | GET | 健康检查 |

---

## Frontend Changes

### 目录结构

```
templates/
├── base.html              # 基础布局（header、nav、footer）
├── login.html             # 登录页面
├── dashboard.html         # 仪表盘
├── ups.html               # UP主管理
├── videos.html            # 推送历史
├── config.html            # 配置管理
└── bilibili_login.html    # B站登录管理

static/
├── js/
│   └── main.js            # 前端交互脚本
└── css/
    └── custom.css         # 自定义样式（可选）
```

### base.html 布局结构

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}B站UP主监控{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    {% block head %}{% endblock %}
</head>
<body class="bg-gray-100 min-h-screen">
    <!-- 导航栏 -->
    <nav class="bg-white shadow-md">
        <div class="container mx-auto px-4">
            <!-- 桌面端导航 -->
            <div class="hidden md:flex">...</div>
            <!-- 移动端汉堡菜单 -->
            <div class="md:hidden">...</div>
        </div>
    </nav>
    
    <!-- 主内容 -->
    <main class="container mx-auto px-4 py-6">
        {% block content %}{% endblock %}
    </main>
    
    <!-- 页脚 -->
    <footer class="text-center py-4 text-gray-500 text-sm">
        B站UP主监控服务 v2.1.0
    </footer>
    
    <script src="/static/js/main.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

### 响应式设计要点

| 元素 | 桌面端 | 移动端 |
|------|--------|--------|
| 导航栏 | 横向菜单 | 汉堡菜单（点击展开） |
| 表格 | 标准表格布局 | 卡片列表布局 |
| 表单 | 横向标签 | 纵向堆叠 |
| 分页 | 显示所有按钮 | 显示"上一页/下一页" |

---

## Backend Changes

### src/web.py 修改

```python
# 新增导入
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request, Form
from starlette.middleware.sessions import SessionMiddleware
import secrets

# 配置 Jinja2 模板
templates = Jinja2Templates(directory="templates")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 添加 Session 中间件
app.add_middleware(
    SessionMiddleware,
    secret_key=secrets.token_urlsafe(32),
    session_cookie="session",
    max_age=86400,  # 24小时
)

# 认证中间件
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # 登录页、静态文件、API 不需要认证
    if request.url.path in ['/login', '/auth/login'] or \
       request.url.path.startswith('/static/') or \
       request.url.path.startswith('/api/'):
        return await call_next(request)
    
    # 检查 Session
    if not request.session.get('authenticated'):
        return RedirectResponse(url='/login', status_code=302)
    
    return await call_next(request)

# 页面路由
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# ... 其他页面路由
```

### 认证处理

```python
@app.post("/auth/login")
async def login(request: Request, password: str = Form(...)):
    if password == "123456":
        request.session['authenticated'] = True
        request.session['login_time'] = datetime.now().isoformat()
        return RedirectResponse(url='/', status_code=302)
    else:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "密码错误"}
        )

@app.post("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url='/login', status_code=302)
```

---

## File Changes

### 新增文件

| 文件 | 用途 |
|------|------|
| `templates/base.html` | 基础布局模板 |
| `templates/login.html` | 登录页面 |
| `templates/dashboard.html` | 仪表盘页面 |
| `templates/ups.html` | UP主管理页面 |
| `templates/videos.html` | 推送历史页面 |
| `templates/config.html` | 配置管理页面 |
| `templates/bilibili_login.html` | B站登录管理页面 |
| `static/js/main.js` | 前端交互脚本 |
| `static/css/custom.css` | 自定义样式（可选） |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `src/web.py` | 添加 Jinja2 配置、Session 中间件、认证中间件、页面路由 |
| `requirements.txt` | 添加 `Jinja2>=3.1.0` 依赖 |

---

## Implementation Flow

### 第一阶段：基础设施

1. 更新 `requirements.txt`，添加 `Jinja2>=3.1.0`
2. 创建 `templates/` 和 `static/` 目录
3. 修改 `src/web.py`，配置 Jinja2、Session、认证中间件
4. 创建 `templates/base.html` 基础布局

### 第二阶段：核心页面

1. 创建 `templates/login.html`（登录页）
2. 创建 `templates/dashboard.html`（仪表盘）
3. 创建 `templates/ups.html`（UP主管理）
4. 创建 `templates/videos.html`（推送历史）

### 第三阶段：配置与登录

1. 创建 `templates/config.html`（配置管理）
2. 创建 `templates/bilibili_login.html`（B站登录）

### 第四阶段：交互脚本

1. 创建 `static/js/main.js`（表单提交、轮询、搜索）
2. 测试所有页面功能

---

## Error Handling

### 认证错误

| 场景 | 错误码 | 处理 |
|------|--------|------|
| 密码错误 | 200 | 显示"密码错误"提示 |
| 未登录访问 | 302 | 重定向到登录页 |
| Session 过期 | 302 | 重定向到登录页，提示"登录已过期" |

### API 错误

| 场景 | 错误码 | 前端处理 |
|------|--------|----------|
| Cookie 过期 | 400 | 提示"B站 Cookie 已过期，请前往登录管理" |
| UP主已存在 | 409 | 提示"UP主已存在" |
| 网络错误 | - | 提示"网络请求失败，请重试" |

### 前端错误提示

使用 Tailwind CSS 样式的 Alert 组件：

```html
<div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
    {{ error_message }}
</div>
```

---

## Testing Strategy

### 单元测试

- 认证中间件测试（正确密码、错误密码、Session 过期）
- 页面路由测试（已登录、未登录）

### 集成测试

- 登录 → 访问页面 → 登出 流程
- 添加 UP主 → 列表更新 → 移除 UP主 流程
- 修改配置 → 保存成功 流程

### 手动测试

- 桌面端浏览器测试（Chrome、Firefox）
- 移动端浏览器测试（iOS Safari、Android Chrome）
- 响应式布局测试（缩放浏览器窗口）

### 测试清单

- [ ] 密码 `123456` 认证成功
- [ ] 错误密码显示错误提示
- [ ] 未登录访问跳转到登录页
- [ ] 仪表盘数据正确显示
- [ ] UP主添加/移除功能正常
- [ ] 推送历史分页筛选正常
- [ ] 配置修改保存成功
- [ ] B站二维码显示正常
- [ ] 扫码登录流程正常
- [ ] 移动端导航栏折叠正常
- [ ] 移动端表格自适应正常