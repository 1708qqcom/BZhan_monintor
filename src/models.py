"""
Pydantic 数据模型定义

功能：
- API 请求/响应模型
- 数据验证
- 序列化配置
"""
from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, Field


# ==================== 用户相关模型 ====================

class UserResponse(BaseModel):
    """用户响应模型"""
    id: int
    username: str
    is_admin: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class UserCreateRequest(BaseModel):
    """用户注册请求模型"""
    username: str = Field(
        ...,
        min_length=2,
        max_length=32,
        description="用户名（2-32字符）",
        examples=["myname"]
    )
    password: str = Field(
        ...,
        min_length=1,
        description="密码",
        examples=["123456"]
    )


class UserListResponse(BaseModel):
    """用户列表响应模型"""
    items: list[UserResponse]
    total: int


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
    latest_videos: Optional[List[Any]] = []

    class Config:
        from_attributes = True


class UpCreateRequest(BaseModel):
    """UP主添加请求模型"""
    mid: int = Field(..., description="B站UP主ID", example="12345678")


class UpListResponse(BaseModel):
    """UP主列表响应模型（已废弃，保留兼容）"""
    items: list[UpResponse]
    total: int


class PaginatedUpResponse(BaseModel):
    """分页 UP主响应模型"""
    items: list[UpResponse]
    total: int
    page: int
    page_size: int


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
        le=250,
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


# ==================== 引导流程相关模型 ====================

class OnboardingProgress(BaseModel):
    """引导进度数据模型"""
    user_id: int
    current_step: int = Field(ge=1, le=3, description="当前步骤（1-3）")
    step1_completed: bool = False
    step1_skipped: bool = False
    step2_completed: bool = False
    step2_skipped: bool = False
    step3_completed: bool = False
    step3_skipped: bool = False
    progress_percent: int = Field(ge=0, le=100, description="进度百分比（0-100）")
    is_completed: bool = Field(description="是否已完成所有步骤或全部跳过")


class OnboardingStepRequest(BaseModel):
    """引导步骤请求模型"""
    step: int = Field(ge=1, le=3, description="步骤编号（1-3）")


class OnboardingStatusResponse(BaseModel):
    """引导状态响应模型"""
    has_onboarding_record: bool = Field(description="是否存在引导记录")
    progress: Optional[OnboardingProgress] = None


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