"""
配置管理 API

端点：
- GET /api/config - 获取配置
- PUT /api/config - 更新配置
- POST /api/config/test-push - 测试飞书推送

配置分类：
- 全局配置（所有用户共享）：check_interval_minutes, max_ups
- 用户配置（每个用户独立）：feishu_webhook_url
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.database import Database
from src.models import ConfigResponse, ConfigUpdateRequest, SuccessResponse
from src.feishu import FeishuNotifier

logger = logging.getLogger("monitor.api.config")

router = APIRouter(prefix="/api/config", tags=["配置管理"])


# ==================== 配置分类 ====================

# 全局配置键（所有用户共享，只有管理员可以修改）
GLOBAL_CONFIG_KEYS = {"check_interval_minutes", "max_ups"}

# 用户配置键（每个用户独立）
USER_CONFIG_KEYS = {"feishu_webhook_url"}


# ==================== 依赖注入 ====================

def get_db() -> Database:
    """获取数据库实例（依赖注入）"""
    return Database()


# ==================== API 端点 ====================

@router.get(
    "",
    response_model=ConfigResponse,
    summary="获取配置",
    description="获取当前用户的配置（合并全局配置和用户配置）"
)
async def get_config(request: Request, db: Database = Depends(get_db)):
    """
    获取配置

    Returns:
        当前配置（用户配置覆盖全局配置）
    """
    user_id = request.session.get("user_id")
    is_admin = request.session.get("is_admin", False)

    logger.info(f"API调用: GET /api/config, user_id={user_id}, is_admin={is_admin}")

    try:
        # 获取配置（合并全局和用户配置）
        config = db.get_config(user_id=user_id)

        # 转换为响应模型
        response = ConfigResponse(
            check_interval_minutes=int(config.get("check_interval_minutes", "30")),
            max_ups=int(config.get("max_ups", "50")),
            feishu_webhook_url=config.get("feishu_webhook_url"),
        )

        logger.info(f"返回配置: check_interval={response.check_interval_minutes}, max_ups={response.max_ups}")
        return response

    except Exception as e:
        logger.error(f"获取配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "",
    response_model=SuccessResponse,
    summary="更新配置",
    description="更新配置，全局配置只有管理员可以修改，用户配置每个用户独立"
)
async def update_config(
    request: Request,
    body: ConfigUpdateRequest,
    db: Database = Depends(get_db),
):
    """
    更新配置

    Args:
        body: 配置更新请求

    Returns:
        成功消息
    """
    user_id = request.session.get("user_id")
    is_admin = request.session.get("is_admin", False)

    logger.info(f"API调用: PUT /api/config, user_id={user_id}, is_admin={is_admin}, body={body}")

    try:
        config_changed = False

        # 更新全局配置（只有管理员可以修改）
        if body.check_interval_minutes is not None:
            if not is_admin:
                raise HTTPException(status_code=403, detail="只有管理员可以修改检查间隔")
            db.update_config("check_interval_minutes", str(body.check_interval_minutes), user_id=None)
            logger.info(f"更新全局配置 - 检查间隔: {body.check_interval_minutes}分钟")
            config_changed = True

        if body.max_ups is not None:
            if not is_admin:
                raise HTTPException(status_code=403, detail="只有管理员可以修改最大UP主数")
            db.update_config("max_ups", str(body.max_ups), user_id=None)
            logger.info(f"更新全局配置 - 最大UP主数: {body.max_ups}")
            config_changed = True

        # 更新用户配置（每个用户独立）
        if body.feishu_webhook_url is not None:
            db.update_config("feishu_webhook_url", body.feishu_webhook_url, user_id=user_id)
            logger.info(f"更新用户配置 - 飞书Webhook: user_id={user_id}")

            # 热更新飞书推送器（仅对当前用户的监控线程生效）
            # 注意：多用户模式下，每个用户有自己的Webhook，监控线程会按用户获取
            config_changed = True

        # 其他配置变更后，更新下次检查时间
        if config_changed and body.feishu_webhook_url is None:
            from src.web import update_next_check_time
            update_next_check_time()

        logger.info("配置更新成功")
        return SuccessResponse(message="配置更新成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 测试推送模型 ====================

class TestPushRequest(BaseModel):
    """测试推送请求模型"""
    message: str = "这是一条测试消息"


# ==================== 测试推送接口 ====================

@router.post(
    "/test-push",
    response_model=SuccessResponse,
    summary="测试飞书推送",
    description="发送测试消息到飞书群，验证当前用户的Webhook配置"
)
async def test_push(
    request: Request,
    body: TestPushRequest,
    db: Database = Depends(get_db),
):
    """
    测试飞书推送（使用当前用户的Webhook）

    Args:
        body: 测试推送请求

    Returns:
        成功消息
    """
    user_id = request.session.get("user_id")

    logger.info(f"API调用: POST /api/config/test-push, user_id={user_id}")

    try:
        # 获取当前用户的飞书 Webhook URL
        webhook_url = db.get_config_value("feishu_webhook_url", user_id=user_id)

        if not webhook_url:
            logger.warning(f"用户未配置飞书Webhook: user_id={user_id}")
            raise HTTPException(
                status_code=400,
                detail="未配置飞书 Webhook URL，请先在配置页面填写"
            )

        # 创建飞书推送器
        notifier = FeishuNotifier(webhook_url)
        logger.debug(f"飞书推送器初始化成功: {webhook_url[:50]}...")

        # 发送测试消息
        success = notifier.send_message(body.message)

        if success:
            logger.info(f"测试消息发送成功: user_id={user_id}")
            return SuccessResponse(message="测试消息发送成功")
        else:
            logger.error(f"测试消息发送失败: user_id={user_id}")
            raise HTTPException(
                status_code=500,
                detail="测试消息发送失败，请检查 Webhook URL 是否正确"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试推送异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))