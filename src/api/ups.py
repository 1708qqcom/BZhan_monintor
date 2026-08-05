"""
UP主管理 API

端点：
- GET /api/ups - 获取UP主列表
- POST /api/ups - 添加UP主
- DELETE /api/ups/{id} - 移除UP主
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from src.database import Database
from src.models import (
    UpResponse,
    UpCreateRequest,
    UpListResponse,
    PaginatedUpResponse,
    ErrorResponse,
    SuccessResponse,
)
from src.bilibili import BilibiliClient
from src.sync_service import sync_followed_ups

logger = logging.getLogger("monitor.api.ups")

router = APIRouter(prefix="/api/ups", tags=["UP主管理"])


# ==================== 依赖注入 ====================

def get_db() -> Database:
    """获取数据库实例（依赖注入）"""
    return Database()


# ==================== API 端点 ====================

@router.get(
    "",
    response_model=PaginatedUpResponse,
    summary="获取UP主列表",
    description="获取UP主列表，普通用户只能看到自己的，管理员可以查看所有。支持分页和搜索。"
)
async def get_ups(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    is_monitoring: Optional[bool] = None,
    user_id: Optional[int] = None,
    db: Database = Depends(get_db),
):
    """
    获取UP主列表（分页）

    Args:
        request: 请求对象（用于获取当前用户信息）
        page: 页码（从1开始），默认 1
        page_size: 每页数量，默认 20
        keyword: 搜索关键词（匹配 name 或 mid）
        is_monitoring: 是否监控中，不传则返回全部
        user_id: 管理员筛选指定用户的UP主

    Returns:
        分页UP主列表，每个UP主包含 latest_videos 字段
    """
    # 获取当前用户信息
    current_user_id = request.session.get("user_id")
    is_admin = request.session.get("is_admin", False)

    logger.info(
        f"API调用: GET /api/ups, user_id={current_user_id}, is_admin={is_admin}, "
        f"page={page}, page_size={page_size}, keyword={keyword}"
    )

    try:
        # 确定查询的用户ID
        query_user_id = None

        if is_admin:
            # 管理员可以查看所有用户，或筛选指定用户
            query_user_id = user_id  # None 表示所有用户
        else:
            # 普通用户只能查看自己的
            query_user_id = current_user_id

        # 查询总数
        total = db.get_ups_count(
            user_id=query_user_id,
            is_monitoring=is_monitoring,
            keyword=keyword
        )

        # 查询分页数据
        ups = db.get_ups(
            user_id=query_user_id,
            is_monitoring=is_monitoring,
            page=page,
            page_size=page_size,
            keyword=keyword
        )

        # 为每个UP主查询最新5个视频
        items = []
        for up in ups:
            up_data = UpResponse(**up).model_dump()

            # 查询该UP主最新的5个视频
            videos_result = db.get_videos(
                page=1,
                page_size=5,
                up_id=up["id"]
            )
            up_data["latest_videos"] = videos_result.get("items", [])
            items.append(up_data)

        logger.info(f"返回 {len(items)} 个UP主，总计 {total} 个")

        return PaginatedUpResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )

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
    request: Request,
    body: UpCreateRequest,
    db: Database = Depends(get_db),
):
    """
    添加UP主

    流程：
    1. 调用B站API验证mid有效性
    2. 获取UP主名称和头像
    3. 添加到数据库（关联到当前用户）

    Args:
        request: 请求对象
        body: 包含mid的请求体

    Returns:
        成功消息
    """
    # 获取当前用户ID
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    logger.info(f"API调用: POST /api/ups, mid={body.mid}, user_id={user_id}")

    try:
        # 1. 检查是否已存在（同一用户）
        existing = db.get_up_by_mid(body.mid, user_id=user_id)
        if existing:
            logger.warning(f"UP主已存在: mid={body.mid}, user_id={user_id}")
            raise HTTPException(
                status_code=409,
                detail=f"UP主已存在: {existing['name']}"
            )

        # 2. 调用B站API获取UP主信息
        logger.debug(f"调用B站API验证UP主: mid={body.mid}")

        # 从数据库获取当前用户的Cookie
        auth = db.get_auth(user_id=user_id)

        if not auth or not auth.get("cookies"):
            username = request.session.get("username", "unknown")
            logger.warning(
                f"用户未绑定B站账号，无法添加UP主: "
                f"user_id={user_id}, username={username}, mid={body.mid}"
            )
            raise HTTPException(
                status_code=400,
                detail="未绑定B站账号，请先扫码登录"
            )

        # 创建B站客户端
        client = BilibiliClient(cookies=auth["cookies"])

        try:
            # 获取UP主详细信息
            up_info = client.get_up_info(body.mid)

            up_name = up_info.get("name", f"UP主_{body.mid}")
            up_face = up_info.get("face", "")

            logger.info(f"UP主验证通过: mid={body.mid}, name={up_name}")

        except Exception as e:
            logger.error(f"调用B站API失败: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"验证UP主失败: {str(e)}"
            )

        # 3. 添加到数据库（关联到当前用户）
        up_id = db.add_up(
            mid=body.mid,
            name=up_name,
            face=up_face,
            user_id=user_id,
        )

        logger.info(f"UP主添加成功: id={up_id}, mid={body.mid}, user_id={user_id}")

        return SuccessResponse(
            message="UP主添加成功",
            data={"id": up_id, "mid": body.mid, "name": up_name}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加UP主失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/sync",
    response_model=SuccessResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="同步关注列表",
    description="从当前用户的B站账号同步关注列表到数据库"
)
async def sync_ups(
    request: Request,
    db: Database = Depends(get_db),
):
    """
    同步B站关注列表

    流程：
    1. 从数据库获取当前用户的Cookie
    2. 调用B站API获取关注列表
    3. 写入数据库（关联到当前用户）
    4. 返回同步结果

    Returns:
        同步结果统计
    """
    # 获取当前用户ID
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    logger.info(f"API调用: POST /api/ups/sync, user_id={user_id}")

    try:
        # 1. 从数据库获取当前用户的Cookie
        auth = db.get_auth(user_id=user_id)

        if not auth or not auth.get("cookies"):
            logger.warning(f"用户未绑定B站账号: user_id={user_id}")
            raise HTTPException(
                status_code=400,
                detail="未绑定B站账号，请先扫码登录"
            )

        cookies = auth["cookies"]
        username = cookies.get("uname", "未知用户")
        logger.info(f"开始同步关注列表: user_id={user_id}, B站用户={username}")

        # 2. 从数据库读取配置
        max_ups_str = db.get_config_value("max_ups", default="50")
        try:
            max_ups = int(max_ups_str)
        except (ValueError, TypeError):
            max_ups = 50

        logger.info(f"同步数量配置: max_ups={max_ups}")

        # 3. 调用同步服务（关联到当前用户）
        sync_result = sync_followed_ups(
            db=db,
            cookies=cookies,
            max_count=max_ups,
            fetch_videos=True,
            user_id=user_id,
        )

        logger.info(f"同步结果: {sync_result['message']}")

        # 4. 返回结果
        if sync_result["success"]:
            return SuccessResponse(
                message=sync_result["message"],
                data=sync_result
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=sync_result["message"]
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"同步关注列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{up_id}",
    response_model=SuccessResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="删除UP主",
    description="删除UP主及其关联的视频记录（需验证归属）"
)
async def remove_up(
    up_id: int,
    request: Request,
    db: Database = Depends(get_db),
):
    """
    删除UP主

    Args:
        up_id: UP主记录ID
        request: 请求对象

    Returns:
        成功消息
    """
    # 获取当前用户信息
    user_id = request.session.get("user_id")
    is_admin = request.session.get("is_admin", False)

    logger.info(f"API调用: DELETE /api/ups/{up_id}, user_id={user_id}")

    try:
        # 管理员可以删除任意UP主，普通用户只能删除自己的
        success = db.remove_up(
            up_id=up_id,
            user_id=None if is_admin else user_id
        )

        if not success:
            logger.warning(f"UP主不存在或无权删除: up_id={up_id}")
            raise HTTPException(
                status_code=404,
                detail=f"UP主不存在或无权删除"
            )

        logger.info(f"UP主已删除: up_id={up_id}")

        return SuccessResponse(message="UP主已删除")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除UP主失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
