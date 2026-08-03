"""
配置管理 API

端点：
- GET /api/config - 获取配置
- PUT /api/config - 更新配置
- POST /api/config/test-push - 测试飞书推送
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.database import Database
from src.models import ConfigResponse, ConfigUpdateRequest, SuccessResponse
from src.feishu import FeishuNotifier

logger = logging.getLogger("monitor.api.config")

router = APIRouter(prefix="/api/config", tags=["配置管理"])


# ==================== 依赖注入 ====================

def get_db() -> Database:
    """获取数据库实例（依赖注入）"""
    return Database()


# ==================== API 端点 ====================

@router.get(
    "",
    response_model=ConfigResponse,
    summary="获取配置",
    description="获取当前系统配置"
)
async def get_config(db: Database = Depends(get_db)):
    """
    获取配置

    Returns:
        当前配置
    """
    logger.info("API调用: GET /api/config")

    try:
        config = db.get_config()

        # 转换为响应模型
        response = ConfigResponse(
            check_interval_minutes=int(config.get("check_interval_minutes", "30")),
            max_ups=int(config.get("max_ups", "50")),
            feishu_webhook_url=config.get("feishu_webhook_url"),
        )

        logger.info(f"返回配置: {response}")
        return response

    except Exception as e:
        logger.error(f"获取配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "",
    response_model=SuccessResponse,
    summary="更新配置",
    description="更新系统配置，配置会立即生效"
)
async def update_config(
    request: ConfigUpdateRequest,
    db: Database = Depends(get_db),
):
    """
    更新配置

    Args:
        request: 配置更新请求

    Returns:
        成功消息
    """
    logger.info(f"API调用: PUT /api/config, request={request}")

    try:
        # 更新配置项
        config_changed = False

        if request.check_interval_minutes is not None:
            db.update_config(
                "check_interval_minutes",
                str(request.check_interval_minutes)
            )
            logger.info(f"更新检查间隔: {request.check_interval_minutes}分钟")
            config_changed = True

        if request.max_ups is not None:
            db.update_config("max_ups", str(request.max_ups))
            logger.info(f"更新最大UP主数: {request.max_ups}")
            config_changed = True

        if request.feishu_webhook_url is not None:
            db.update_config("feishu_webhook_url", request.feishu_webhook_url)
            logger.info("更新飞书Webhook")

            # 热更新飞书推送器
            from src.web import update_feishu_notifier
            success = update_feishu_notifier(request.feishu_webhook_url)
            if not success:
                logger.warning("飞书推送器热更新失败，配置已保存但推送功能可能不生效")

            config_changed = True

        # 其他配置变更后，更新下次检查时间
        if config_changed and request.feishu_webhook_url is None:
            from src.web import update_next_check_time
            update_next_check_time()

        logger.info("配置更新成功")
        return SuccessResponse(message="配置更新成功")

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
    description="发送测试消息到飞书群，验证Webhook配置"
)
async def test_push(
    request: TestPushRequest,
    db: Database = Depends(get_db),
):
    """
    测试飞书推送

    Args:
        request: 测试推送请求

    Returns:
        成功消息
    """
    logger.info(f"API调用: POST /api/config/test-push, message={request.message}")

    try:
        # 获取飞书 Webhook URL
        webhook_url = db.get_config_value("feishu_webhook_url")

        if not webhook_url:
            logger.warning("未配置飞书Webhook URL")
            raise HTTPException(
                status_code=400,
                detail="未配置飞书 Webhook URL，请先在配置页面填写"
            )

        # 创建飞书推送器
        notifier = FeishuNotifier(webhook_url)
        logger.debug(f"飞书推送器初始化成功: {webhook_url[:50]}...")

        # 发送测试消息
        success = notifier.send_message(request.message)

        if success:
            logger.info("测试消息发送成功")
            return SuccessResponse(message="测试消息发送成功")
        else:
            logger.error("测试消息发送失败")
            raise HTTPException(
                status_code=500,
                detail="测试消息发送失败，请检查 Webhook URL 是否正确"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试推送异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))