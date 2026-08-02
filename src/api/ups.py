"""
UP主管理 API

端点：
- GET /api/ups - 获取UP主列表
- POST /api/ups - 添加UP主
- DELETE /api/ups/{id} - 移除UP主
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src.database import Database
from src.models import (
    UpResponse,
    UpCreateRequest,
    UpListResponse,
    ErrorResponse,
    SuccessResponse,
)
from src.bilibili import BilibiliClient

logger = logging.getLogger("monitor.api.ups")

router = APIRouter(prefix="/api/ups", tags=["UP主管理"])


# ==================== 依赖注入 ====================

def get_db() -> Database:
    """获取数据库实例（依赖注入）"""
    # TODO: 改为全局单例
    return Database()


# ==================== API 端点 ====================

@router.get(
    "",
    response_model=UpListResponse,
    summary="获取UP主列表",
    description="获取所有监控中的UP主列表"
)
async def get_ups(
    is_monitoring: Optional[bool] = None,
    db: Database = Depends(get_db),
):
    """
    获取UP主列表

    Args:
        is_monitoring: 是否监控中，不传则返回全部

    Returns:
        UP主列表
    """
    logger.info(f"API调用: GET /api/ups, is_monitoring={is_monitoring}")

    try:
        ups = db.get_ups(is_monitoring=is_monitoring)

        # 转换为响应模型
        items = [UpResponse(**up) for up in ups]

        logger.info(f"返回 {len(items)} 个UP主")
        return UpListResponse(items=items, total=len(items))

    except Exception as e:
        logger.error(f"获取UP主列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "",
    response_model=SuccessResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="添加UP主",
    description="添加UP主到监控列表，会调用B站API验证有效性"
)
async def add_up(
    request: UpCreateRequest,
    db: Database = Depends(get_db),
):
    """
    添加UP主

    流程：
    1. 调用B站API验证mid有效性
    2. 获取UP主名称和头像
    3. 添加到数据库

    Args:
        request: 包含mid的请求体

    Returns:
        成功消息
    """
    logger.info(f"API调用: POST /api/ups, mid={request.mid}")

    try:
        # 1. 检查是否已存在
        existing = db.get_up_by_mid(request.mid)
        if existing:
            logger.warning(f"UP主已存在: mid={request.mid}")
            raise HTTPException(
                status_code=409,
                detail=f"UP主已存在: {existing['name']}"
            )

        # 2. 调用B站API获取UP主信息
        logger.debug(f"调用B站API验证UP主: mid={request.mid}")

        # 从数据库获取Cookie
        auth = db.get_auth()
        if not auth or not auth.get("cookies"):
            raise HTTPException(
                status_code=400,
                detail="未登录B站账号，请先登录"
            )

        # 创建B站客户端
        client = BilibiliClient(cookies=auth["cookies"])

        try:
            # 获取UP主详细信息
            up_info = client.get_up_info(request.mid)

            up_name = up_info.get("name", f"UP主_{request.mid}")
            up_face = up_info.get("face", "")

            logger.info(f"UP主验证通过: mid={request.mid}, name={up_name}")

        except Exception as e:
            logger.error(f"调用B站API失败: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"验证UP主失败: {str(e)}"
            )

        # 3. 添加到数据库
        up_id = db.add_up(
            mid=request.mid,
            name=up_name,
            face=up_face
        )

        logger.info(f"UP主添加成功: id={up_id}, mid={request.mid}")

        return SuccessResponse(
            message="UP主添加成功",
            data={"id": up_id, "mid": request.mid, "name": up_name}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加UP主失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{up_id}",
    response_model=SuccessResponse,
    responses={404: {"model": ErrorResponse}},
    summary="移除UP主",
    description="从监控列表移除UP主（软删除）"
)
async def remove_up(
    up_id: int,
    db: Database = Depends(get_db),
):
    """
    移除UP主

    Args:
        up_id: UP主记录ID

    Returns:
        成功消息
    """
    logger.info(f"API调用: DELETE /api/ups/{up_id}")

    try:
        success = db.remove_up(up_id)

        if not success:
            logger.warning(f"UP主不存在: up_id={up_id}")
            raise HTTPException(
                status_code=404,
                detail=f"UP主不存在: id={up_id}"
            )

        logger.info(f"UP主已移除: up_id={up_id}")

        return SuccessResponse(message="UP主已移除")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除UP主失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
