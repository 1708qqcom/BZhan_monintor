"""
Pydantic 数据模型定义

功能：
- API 请求/响应模型
- 数据验证
- 序列化配置
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==================== UP主相关模型 ====================

class UpResponse(BaseModel):
    """UP主响应模型"""
    id: int
    mid: int
    name: str
    face: Optional[str] = None
    is_monitoring: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class UpCreateRequest(BaseModel):
    """UP主添加请求模型"""
    mid: int = Field(..., description="B站UP主ID", example="12345678")


class UpListResponse(BaseModel):
    """UP主列表响应模型"""
    items: list[UpResponse]
    total: int


# ==================== 视频历史相关模型 ====================

class VideoResponse(BaseModel):
    """视频历史响应模型"""
    id: int
    up_id: int
    bvid: str
    title: str
    url: Optional[str] = None
    pub_time: Optional[str] = None
    view_count: int = 0
    pushed: bool
    pushed_at: Optional[str] = None
    created_at: str
    up_name: Optional[str] = None
    up_face: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedVideoResponse(BaseModel):
    """分页视频响应模型"""
    items: list[VideoResponse]
    total: int
    page: int
    page_size: int


# ==================== 配置相关模型 ====================

class ConfigResponse(BaseModel):
    """配置响应模型"""
    check_interval_minutes: int = 30
    max_ups: int = 50
    feishu_webhook_url: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    """配置更新请求模型"""
    check_interval_minutes: Optional[int] = Field(
        None,
        ge=5,
        description="检查间隔（分钟），最小5分钟"
    )
    max_ups: Optional[int] = Field(
        None,
        ge=1,
        le=100,
        description="最多监控UP主数量"
    )
    feishu_webhook_url: Optional[str] = Field(
        None,
        description="飞书 Webhook URL"
    )


# ==================== 登录相关模型 ====================

class LoginStatusResponse(BaseModel):
    """登录状态响应模型"""
    is_logged_in: bool
    username: Optional[str] = None
    expires_at: Optional[str] = None
    days_remaining: Optional[int] = None
    message: str = ""


class QrCodeResponse(BaseModel):
    """二维码响应模型"""
    qrcode_url: str
    image_url: str


# ==================== 通用响应模型 ====================

class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str
    detail: Optional[str] = None


class SuccessResponse(BaseModel):
    """成功响应模型"""
    message: str
    data: Optional[dict] = None


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = "ok"
    timestamp: str
    database: str = "connected"
    version: str = "2.1.0"