"""
API 路由模块
"""
from src.api.ups import router as ups_router
from src.api.videos import router as videos_router
from src.api.config import router as config_router
from src.api.login import router as login_router
from src.api.toview import router as toview_router

__all__ = [
    "ups_router",
    "videos_router",
    "config_router",
    "login_router",
    "toview_router",
]