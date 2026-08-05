"""
FastAPI Web 应用

功能：
- 创建 FastAPI 应用实例
- 配置 CORS 中间件
- 配置日志中间件
- 配置 Session 中间件
- 配置 Jinja2 模板引擎
- 挂载静态文件
- 注册路由
- 配置 Swagger 文档
- 启动监控调度器线程
"""
import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.api import ups_router, videos_router, config_router, login_router
from src.database import Database
from src.models import HealthResponse, ErrorResponse
from src.scheduler import MonitorScheduler
from src.bilibili import BilibiliClient
from src.feishu import FeishuNotifier

logger = logging.getLogger("monitor.web")

# ==================== 模板配置 ====================

TEMPLATES_DIR = Path("templates")
STATIC_DIR = Path("static")

# 创建 Jinja2 环境
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
)

logger.info(f"Jinja2 模板目录: {TEMPLATES_DIR.absolute()}")
logger.info(f"静态文件目录: {STATIC_DIR.absolute()}")


# ==================== 监控线程状态 ====================

_monitor_state = {
    "is_running": False,
    "last_check_time": None,
    "next_check_time": None,
    "check_interval_minutes": 10,
    "scheduler": None,
    "error_message": None,
}


def _start_monitor_thread(db: Database) -> None:
    """
    启动监控调度器线程

    Args:
        db: 数据库实例
    """
    global _monitor_state

    logger.info("准备启动监控调度器线程...")

    try:
        # 1. 获取B站Cookie
        auth = db.get_auth()
        if not auth or not auth.get("cookies"):
            logger.warning("未登录B站账号，监控调度器不启动")
            _monitor_state["error_message"] = "未登录B站账号"
            return

        cookies = auth["cookies"]

        # 2. 验证Cookie有效性
        bilibili_client = BilibiliClient(cookies)
        if not bilibili_client.check_cookie_valid():
            logger.warning("B站Cookie已过期，监控调度器不启动")
            _monitor_state["error_message"] = "B站Cookie已过期"
            return

        logger.info("B站Cookie验证通过")

        # 3. 获取飞书Webhook配置
        webhook_url = db.get_config_value("feishu_webhook_url", default="")
        feishu_notifier = None
        if webhook_url:
            feishu_notifier = FeishuNotifier(webhook_url)
            logger.info(f"飞书推送器已初始化: {webhook_url[:50]}...")
        else:
            logger.warning("未配置飞书Webhook，将不发送推送通知")

        # 4. 获取检查间隔配置
        check_interval_str = db.get_config_value("check_interval_minutes", default="10")
        try:
            check_interval_minutes = int(check_interval_str)
        except (ValueError, TypeError):
            check_interval_minutes = 10

        # 5. 初始化调度器
        scheduler = MonitorScheduler(
            bilibili_client=bilibili_client,
            feishu_notifier=feishu_notifier,
            check_interval_minutes=check_interval_minutes,
            max_ups=50,
            database=db,
        )

        # 6. 设置状态回调
        def _on_state_change(**kwargs):
            global _monitor_state
            _monitor_state.update(kwargs)
            _monitor_state["error_message"] = None  # 清除错误信息
            # 确保 is_checking 有默认值
            if "is_checking" not in kwargs:
                _monitor_state["is_checking"] = False

        scheduler.set_state_callback(_on_state_change)

        # 7. 更新状态
        _monitor_state["is_running"] = True
        _monitor_state["scheduler"] = scheduler
        _monitor_state["check_interval_minutes"] = check_interval_minutes

        # 8. 启动后台线程
        def _run_scheduler():
            """调度器线程入口"""
            try:
                logger.info("监控调度器线程开始运行")
                scheduler.start(skip_signals=True)  # 后台线程模式跳过信号注册
            except Exception as e:
                logger.error(f"监控调度器线程异常退出: {e}", exc_info=True)
                _monitor_state["is_running"] = False
                _monitor_state["error_message"] = f"调度器异常: {str(e)}"

        thread = threading.Thread(
            target=_run_scheduler,
            name="MonitorScheduler",
            daemon=True,  # 守护线程，主线程退出时自动终止
        )
        thread.start()

        logger.info("监控调度器已启动（后台线程）")

    except Exception as e:
        logger.error(f"启动监控调度器失败: {e}", exc_info=True)
        _monitor_state["is_running"] = False
        _monitor_state["error_message"] = f"启动失败: {str(e)}"


# ==================== 应用生命周期 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时：初始化数据库、启动监控线程
    关闭时：清理资源
    """
    logger.info("=" * 50)
    logger.info("Web 应用启动中...")
    logger.info("=" * 50)

    # 初始化数据库
    try:
        db = Database()
        db.init_db()
        logger.info("数据库初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

    # 启动监控调度器线程
    try:
        _start_monitor_thread(db)
    except Exception as e:
        logger.error(f"启动监控线程失败: {e}", exc_info=True)
        # 不抛出异常，允许Web服务继续运行

    yield

    logger.info("Web 应用关闭")


# ==================== 创建应用实例 ====================

app = FastAPI(
    title="B站UP主监控服务",
    description="自动监控B站关注的UP主新视频发布，通过飞书推送通知",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ==================== 中间件配置 ====================
# 注意：BaseHTTPMiddleware 的执行顺序与注册顺序相同（FIFO）
# 注册顺序：Auth → Log → Session → CORS
# 实际执行顺序：Auth → Log → Session → CORS

from starlette.middleware.base import BaseHTTPMiddleware

# 认证白名单
AUTH_WHITELIST = [
    "/auth/login",
    "/auth/register",  # 注册不需要登录
    "/static",
    "/api/health",
    "/api/monitor/status",  # 监控状态API不需要Web后台登录
    "/api/login",      # B站登录相关API不需要Web后台登录
    "/api/ups/sync",   # 同步API只需B站登录
    "/docs",
    "/redoc",
    "/openapi.json",
]

# 认证中间件（最先执行）
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 白名单路径跳过认证
        path = request.url.path
        is_whitelisted = any(path.startswith(white) for white in AUTH_WHITELIST)

        if is_whitelisted:
            logger.debug(f"跳过认证: {path}")
            return await call_next(request)

        # 检查 Session 中的用户信息
        user_id = request.session.get("user_id")

        if not user_id:
            logger.info(f"未认证访问: {path}, 跳转登录页")
            # 如果是 API 请求，返回 401
            if path.startswith("/api/"):
                return JSONResponse(
                    status_code=401,
                    content={"error": "Unauthorized", "detail": "请先登录"}
                )
            # 否则重定向到登录页
            return RedirectResponse(url="/auth/login", status_code=302)

        # 已认证，继续处理
        logger.debug(f"认证通过: {path}, user_id={user_id}")
        return await call_next(request)

app.add_middleware(AuthMiddleware)
logger.info("认证中间件已配置")


# 日志中间件
class LogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # 记录请求
        logger.info(
            f"请求: {request.method} {request.url.path} "
            f"客户端: {request.client.host if request.client else 'unknown'}"
        )

        try:
            response = await call_next(request)

            # 计算耗时
            duration = (time.time() - start_time) * 1000

            # 记录响应
            logger.info(
                f"响应: {request.method} {request.url.path} "
                f"状态码: {response.status_code} "
                f"耗时: {duration:.2f}ms"
            )

            return response

        except Exception as e:
            logger.error(f"请求处理异常: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": "Internal Server Error", "detail": str(e)}
            )

app.add_middleware(LogMiddleware)
logger.info("日志中间件已配置")


# Session 中间件
SECRET_KEY = "your-secret-key-change-in-production-12345"
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=86400,  # 24小时
    same_site="lax",
)
logger.info("Session 中间件已配置，max_age=86400秒")


# CORS 中间件（最后执行）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORS 中间件已配置")


# ==================== 认证路由 ====================

@app.get("/auth/login", response_class=HTMLResponse, tags=["认证"])
async def login_page(request: Request, error: str = None):
    """
    登录页面

    Args:
        request: 请求对象
        error: 错误消息
    """
    logger.debug("渲染登录页面")

    template = jinja_env.get_template("login.html")
    return HTMLResponse(
        content=template.render(error=error)
    )


@app.post("/auth/login", tags=["认证"])
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    """
    处理登录表单提交

    Args:
        request: 请求对象
        username: 用户名
        password: 密码
    """
    logger.info(f"收到登录请求: username={username}")

    # 从数据库验证用户
    db = Database()
    user = db.get_user_by_username(username)

    if not user:
        logger.warning(f"登录失败: 用户不存在, username={username}")
        template = jinja_env.get_template("login.html")
        return HTMLResponse(
            content=template.render(error="用户名或密码错误"),
            status_code=401
        )

    # 验证密码
    if user["password"] != password:
        logger.warning(f"登录失败: 密码错误, username={username}")
        template = jinja_env.get_template("login.html")
        return HTMLResponse(
            content=template.render(error="用户名或密码错误"),
            status_code=401
        )

    # 设置 Session
    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["is_admin"] = bool(user["is_admin"])

    logger.info(f"登录成功: username={username}, is_admin={user['is_admin']}")
    return RedirectResponse(url="/", status_code=302)


@app.get("/auth/register", response_class=HTMLResponse, tags=["认证"])
async def register_page(request: Request, error: str = None):
    """
    注册页面

    Args:
        request: 请求对象
        error: 错误消息
    """
    logger.debug("渲染注册页面")

    template = jinja_env.get_template("register.html")
    return HTMLResponse(
        content=template.render(error=error)
    )


@app.post("/auth/register", tags=["认证"])
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    """
    处理注册表单提交

    Args:
        request: 请求对象
        username: 用户名
        password: 密码
        confirm_password: 确认密码
    """
    logger.info(f"收到注册请求: username={username}")

    # 1. 验证密码一致性
    if password != confirm_password:
        logger.warning("注册失败: 密码不一致")
        template = jinja_env.get_template("register.html")
        return HTMLResponse(
            content=template.render(error="两次输入的密码不一致"),
            status_code=400
        )

    # 2. 检查用户名是否已存在
    db = Database()
    existing_user = db.get_user_by_username(username)

    if existing_user:
        logger.warning(f"注册失败: 用户名已存在, username={username}")
        template = jinja_env.get_template("register.html")
        return HTMLResponse(
            content=template.render(error="用户名已存在，请更换"),
            status_code=400
        )

    # 3. 创建用户
    try:
        user_id = db.add_user(username, password, is_admin=False)
        logger.info(f"用户注册成功: id={user_id}, username={username}")
    except Exception as e:
        logger.error(f"注册失败: {e}", exc_info=True)
        template = jinja_env.get_template("register.html")
        return HTMLResponse(
            content=template.render(error="注册失败，请稍后重试"),
            status_code=500
        )

    # 4. 自动登录
    request.session["user_id"] = user_id
    request.session["username"] = username
    request.session["is_admin"] = False

    logger.info(f"自动登录成功: username={username}")
    return RedirectResponse(url="/", status_code=302)


@app.post("/auth/logout", tags=["认证"])
async def logout(request: Request):
    """
    登出

    清除 Session 并重定向到登录页
    """
    username = request.session.get("username", "unknown")
    logger.info(f"用户登出: username={username}")
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)


# ==================== 异常处理 ====================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理器

    Args:
        request: 请求对象
        exc: 异常对象
    """
    logger.error(f"未捕获异常: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Server Error",
            detail=str(exc)
        ).model_dump()
    )


# ==================== 挂载静态文件 ====================

# 挂载静态文件目录
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.info(f"静态文件已挂载: /static -> {STATIC_DIR.absolute()}")
else:
    logger.warning(f"静态文件目录不存在: {STATIC_DIR.absolute()}")


# ==================== 注册路由 ====================

logger.debug("注册API路由...")

app.include_router(ups_router)
app.include_router(videos_router)
app.include_router(config_router)
app.include_router(login_router)

logger.debug("API路由注册完成")


# ==================== 健康检查端点 ====================

@app.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["系统"],
    summary="健康检查",
    description="检查服务运行状态"
)
async def health_check():
    """
    健康检查端点

    Returns:
        服务状态信息
    """
    logger.debug("API调用: GET /api/health")

    return HealthResponse(
        status="ok",
        timestamp=datetime.now().isoformat(),
        database="connected",
        version="2.1.0"
    )


# ==================== 监控状态端点 ====================

def update_next_check_time() -> None:
    """
    更新下次检查时间（配置变更时调用）

    根据当前时间和新的检查间隔重新计算 next_check_time
    """
    global _monitor_state

    scheduler = _monitor_state.get("scheduler")
    if scheduler and _monitor_state.get("is_running"):
        # 使用调度器中的最新间隔
        from datetime import timedelta
        next_check = datetime.now() + timedelta(seconds=scheduler.check_interval)
        _monitor_state["next_check_time"] = next_check.isoformat()
        _monitor_state["check_interval_minutes"] = scheduler.check_interval // 60
        logger.info(f"已更新下次检查时间: {next_check.strftime('%H:%M:%S')}")


def update_feishu_notifier(webhook_url: str) -> bool:
    """
    更新飞书推送器（配置变更时调用）

    Args:
        webhook_url: 飞书 Webhook URL，空字符串表示禁用推送

    Returns:
        更新成功返回 True
    """
    global _monitor_state

    scheduler = _monitor_state.get("scheduler")
    if not scheduler:
        logger.warning("调度器未运行，无法更新飞书推送器")
        return False

    success = scheduler.update_feishu_notifier(webhook_url)
    if success:
        logger.info(f"飞书推送器热更新成功: {webhook_url[:50] if webhook_url else '(已禁用)'}")
    else:
        logger.error("飞书推送器热更新失败")

    return success


@app.get(
    "/api/monitor/status",
    tags=["监控"],
    summary="获取监控状态",
    description="获取监控调度器的运行状态"
)
async def get_monitor_status():
    """
    获取监控状态

    Returns:
        监控状态信息：
        - is_running: 是否运行中
        - last_check_time: 上次检查时间
        - next_check_time: 下次检查时间
        - check_interval_minutes: 检查间隔（分钟）
        - error_message: 错误信息（如果有）
    """
    logger.debug("API调用: GET /api/monitor/status")

    return {
        "is_running": _monitor_state.get("is_running", False),
        "is_checking": _monitor_state.get("is_checking", False),
        "last_check_time": _monitor_state.get("last_check_time"),
        "next_check_time": _monitor_state.get("next_check_time"),
        "check_interval_minutes": _monitor_state.get("check_interval_minutes", 30),
        "error_message": _monitor_state.get("error_message"),
    }


@app.post(
    "/api/monitor/refresh",
    tags=["监控"],
    summary="手动触发刷新",
    description="触发监控调度器立即执行一次检查"
)
async def trigger_monitor_refresh():
    """
    手动触发刷新

    Returns:
        触发结果：
        - message: 结果消息
        - triggered: 是否触发成功

    Raises:
        HTTPException:
            - 400: 监控调度器未运行
            - 409: 正在检查中，请稍后
    """
    logger.info("API调用: POST /api/monitor/refresh")

    scheduler = _monitor_state.get("scheduler")
    if not scheduler:
        logger.warning("触发刷新失败：监控调度器未运行")
        raise HTTPException(
            status_code=400,
            detail="监控调度器未运行"
        )

    success = scheduler.trigger_refresh()
    if not success:
        logger.info("触发刷新失败：正在检查中")
        raise HTTPException(
            status_code=409,
            detail="正在检查中，请稍后"
        )

    logger.info("触发刷新成功")
    return {"message": "已触发刷新", "triggered": True}


# ==================== 根路径 ====================

@app.get("/", response_class=HTMLResponse, tags=["系统"])
async def root(request: Request):
    """
    根路径，显示仪表盘页面

    Args:
        request: 请求对象
    """
    logger.debug("渲染仪表盘页面")

    template = jinja_env.get_template("dashboard.html")
    return HTMLResponse(content=template.render(
        username=request.session.get("username", ""),
        is_admin=request.session.get("is_admin", False)
    ))


# ==================== UP主管理页面 ====================

@app.get("/ups", response_class=HTMLResponse, tags=["页面"])
async def ups_page(request: Request):
    """
    UP主管理页面

    Args:
        request: 请求对象
    """
    logger.debug("渲染UP主管理页面")

    template = jinja_env.get_template("ups.html")
    return HTMLResponse(content=template.render(
        username=request.session.get("username", ""),
        is_admin=request.session.get("is_admin", False)
    ))


# ==================== 推送历史页面 ====================

@app.get("/videos", response_class=HTMLResponse, tags=["页面"])
async def videos_page(request: Request):
    """
    推送历史页面

    Args:
        request: 请求对象
    """
    logger.debug("渲染推送历史页面")

    template = jinja_env.get_template("videos.html")
    return HTMLResponse(content=template.render(
        username=request.session.get("username", ""),
        is_admin=request.session.get("is_admin", False)
    ))


# ==================== 配置管理页面 ====================

@app.get("/config", response_class=HTMLResponse, tags=["页面"])
async def config_page(request: Request):
    """
    配置管理页面

    Args:
        request: 请求对象
    """
    logger.debug("渲染配置管理页面")

    template = jinja_env.get_template("config.html")
    return HTMLResponse(content=template.render(
        username=request.session.get("username", ""),
        is_admin=request.session.get("is_admin", False)
    ))


# ==================== B站登录管理页面 ====================

@app.get("/bilibili-login", response_class=HTMLResponse, tags=["页面"])
async def bilibili_login_page(request: Request):
    """
    B站登录管理页面

    Args:
        request: 请求对象
    """
    logger.debug("渲染B站登录管理页面")

    template = jinja_env.get_template("bilibili_login.html")
    return HTMLResponse(content=template.render(
        username=request.session.get("username", ""),
        is_admin=request.session.get("is_admin", False)
    ))


# ==================== 用户管理页面（管理员） ====================

@app.get("/users", response_class=HTMLResponse, tags=["页面"])
async def users_page(request: Request):
    """
    用户管理页面（管理员专属）

    Args:
        request: 请求对象
    """
    # 权限检查
    is_admin = request.session.get("is_admin", False)
    if not is_admin:
        return HTMLResponse(
            content="<h1>403 禁止访问</h1><p>只有管理员可以访问此页面</p>",
            status_code=403
        )

    logger.debug("渲染用户管理页面")

    template = jinja_env.get_template("users.html")
    return HTMLResponse(content=template.render(
        username=request.session.get("username", ""),
        is_admin=True
    ))


# ==================== 用户管理 API（管理员） ====================

@app.get("/api/users", tags=["用户管理"])
async def get_users(request: Request):
    """
    获取用户列表（管理员专属）

    Returns:
        用户列表
    """
    # 权限检查
    is_admin = request.session.get("is_admin", False)
    if not is_admin:
        raise HTTPException(status_code=403, detail="只有管理员可以访问")

    logger.info("API调用: GET /api/users")

    try:
        db = Database()
        users = db.get_all_users()

        # 移除密码字段
        for user in users:
            user.pop("password", None)

        logger.info(f"返回 {len(users)} 个用户")
        return {"items": users, "total": len(users)}

    except Exception as e:
        logger.error(f"获取用户列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/users/{user_id}", tags=["用户管理"])
async def delete_user(user_id: int, request: Request):
    """
    删除用户（管理员专属）

    Args:
        user_id: 用户ID

    Returns:
        成功消息
    """
    # 权限检查
    is_admin = request.session.get("is_admin", False)
    current_user_id = request.session.get("user_id")

    if not is_admin:
        raise HTTPException(status_code=403, detail="只有管理员可以访问")

    # 禁止删除自己
    if user_id == current_user_id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    logger.info(f"API调用: DELETE /api/users/{user_id}")

    try:
        db = Database()

        # 检查用户是否存在
        user = db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 删除用户（外键级联删除关联数据）
        success = db.delete_user(user_id)

        if success:
            logger.info(f"用户已删除: user_id={user_id}, username={user['username']}")
            return {"message": "用户已删除", "username": user["username"]}
        else:
            raise HTTPException(status_code=500, detail="删除失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除用户失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 启动函数 ====================

def run_web_server(host: str = "0.0.0.0", port: int = 3231):
    """
    启动Web服务器

    Args:
        host: 监听地址
        port: 监听端口
    """
    import uvicorn

    logger.info(f"启动Web服务器: http://{host}:{port}")
    logger.info(f"API文档: http://{host}:{port}/docs")

    uvicorn.run(
        "src.web:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


# 导入datetime用于health_check
from datetime import datetime