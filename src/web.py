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
"""
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from jinja2 import Environment, FileSystemLoader

from src.api import ups_router, videos_router, config_router, login_router
from src.database import Database
from src.models import HealthResponse, ErrorResponse

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


# ==================== 应用生命周期 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时：初始化数据库
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
    "/static",
    "/api/health",
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

        # 检查 Session 中的认证状态
        authenticated = request.session.get("authenticated", False)

        if not authenticated:
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
        logger.debug(f"认证通过: {path}")
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
async def login_submit(request: Request, password: str = Form(...)):
    """
    处理登录表单提交

    Args:
        request: 请求对象
        password: 密码
    """
    logger.info("收到登录请求")

    # 验证密码
    correct_password = "Huisec@123"

    if password == correct_password:
        # 设置 Session
        request.session["authenticated"] = True
        logger.info("登录成功，跳转首页")
        return RedirectResponse(url="/", status_code=302)
    else:
        logger.warning("登录失败: 密码错误")
        # 返回登录页并显示错误
        template = jinja_env.get_template("login.html")
        return HTMLResponse(
            content=template.render(error="密码错误，请重试"),
            status_code=401
        )


@app.post("/auth/logout", tags=["认证"])
async def logout(request: Request):
    """
    登出

    清除 Session 并重定向到登录页
    """
    logger.info("用户登出")
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
    return HTMLResponse(content=template.render())


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
    return HTMLResponse(content=template.render())


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
    return HTMLResponse(content=template.render())


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
    return HTMLResponse(content=template.render())


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
    return HTMLResponse(content=template.render())


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