"""
稍后再看API路由

功能：
- 获取当前用户的稍后再看列表
- 获取所有用户的稍后再看列表（管理员）
- 手动推送稍后再看（管理员）
- 获取推送历史
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.bilibili import BilibiliClient
from src.feishu import FeishuNotifier
from src.database import Database
from src.exceptions import CookieExpiredError, BilibiliAPIError

logger = logging.getLogger("monitor.api.toview")

# 创建路由器
router = APIRouter(prefix="/api/toview", tags=["稍后再看"])

# 数据库实例
db = Database()


# ==================== 请求模型 ====================

class PushRequest(BaseModel):
    """手动推送请求"""
    user_id: Optional[int] = None  # 目标用户ID，不填则推送自己的
    count: int = 3  # 推送数量，默认3个


# ==================== API端点 ====================

@router.get("")
async def get_toview(request: Request):
    """
    获取当前用户的稍后再看列表

    Returns:
        {
            "success": true,
            "data": {
                "count": 10,
                "videos": [...]
            }
        }
    """
    user_id = request.session.get("user_id")
    username = request.session.get("username", "unknown")

    logger.info(f"API调用: GET /api/toview, user={username}")

    try:
        # 1. 获取用户的B站Cookie
        auth = db.get_auth(user_id=user_id)

        if not auth or not auth.get("cookies"):
            raise HTTPException(
                status_code=401,
                detail="未登录B站账号，请先在配置页面扫码登录"
            )

        # 2. 调用B站API
        client = BilibiliClient(cookies=auth["cookies"])
        videos = client.get_toview_list()

        # 3. 保存到数据库（缓存）
        if videos:
            db.save_toview_videos(user_id, videos)

        logger.info(f"[用户 {username}] 获取稍后再看成功，共 {len(videos)} 个视频")

        return {
            "success": True,
            "data": {
                "count": len(videos),
                "videos": videos
            }
        }

    except CookieExpiredError:
        logger.warning(f"[用户 {username}] B站Cookie已过期")
        raise HTTPException(
            status_code=401,
            detail="B站登录已过期，请重新扫码登录"
        )

    except BilibiliAPIError as e:
        logger.error(f"[用户 {username}] B站API调用失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"B站API调用失败: {str(e)}"
        )

    except Exception as e:
        logger.error(f"[用户 {username}] 获取稍后再看失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取失败: {str(e)}"
        )


@router.get("/all")
async def get_all_toview(request: Request, user_id: Optional[int] = None):
    """
    获取所有用户的稍后再看列表（管理员）

    Args:
        user_id: 可选，筛选指定用户

    Returns:
        {
            "success": true,
            "data": [
                {
                    "user_id": 1,
                    "username": "user1",
                    "count": 5,
                    "videos": [...]
                }
            ]
        }
    """
    # 权限检查
    is_admin = request.session.get("is_admin", False)
    if not is_admin:
        logger.warning("非管理员尝试访问所有用户稍后再看")
        raise HTTPException(
            status_code=403,
            detail="无权限，只有管理员可以访问"
        )

    logger.info(f"API调用: GET /api/toview/all, user_id={user_id}")

    try:
        data = db.get_all_toview_videos(user_id=user_id)

        logger.info(f"管理员查询稍后再看成功，共 {len(data)} 个用户")

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        logger.error(f"管理员查询稍后再看失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"查询失败: {str(e)}"
        )


@router.post("/push")
async def push_toview(request: Request, body: PushRequest):
    """
    手动推送稍后再看（管理员）

    Args:
        body: {
            "user_id": 1,  # 可选，不填则推送自己的
            "count": 3     # 可选，推送数量
        }

    Returns:
        {
            "success": true,
            "message": "推送成功",
            "pushed_videos": [...]
        }
    """
    # 权限检查
    is_admin = request.session.get("is_admin", False)
    current_user_id = request.session.get("user_id")
    username = request.session.get("username", "unknown")

    if not is_admin:
        logger.warning(f"非管理员尝试手动推送: user={username}")
        raise HTTPException(
            status_code=403,
            detail="无权限，只有管理员可以手动推送"
        )

    # 确定目标用户ID
    target_user_id = body.user_id if body.user_id else current_user_id

    logger.info(
        f"API调用: POST /api/toview/push, "
        f"admin={username}, target_user_id={target_user_id}, count={body.count}"
    )

    try:
        # 1. 获取目标用户信息
        auth = db.get_auth(user_id=target_user_id)

        if not auth or not auth.get("cookies"):
            raise HTTPException(
                status_code=404,
                detail="目标用户未登录B站账号"
            )

        target_user = db.get_user_by_id(target_user_id)
        if not target_user:
            raise HTTPException(
                status_code=404,
                detail="目标用户不存在"
            )

        # 2. 获取飞书Webhook
        webhook_url = db.get_config_value(
            "feishu_webhook_url",
            user_id=target_user_id
        )
        if not webhook_url:
            # 回退到全局配置
            webhook_url = db.get_config_value("feishu_webhook_url")

        if not webhook_url:
            raise HTTPException(
                status_code=400,
                detail="目标用户未配置飞书Webhook"
            )

        # 3. 获取稍后再看列表
        client = BilibiliClient(cookies=auth["cookies"])
        videos = client.get_toview_list(page_size=body.count)

        if not videos:
            return {
                "success": True,
                "message": "稍后再看列表为空，无需推送",
                "pushed_videos": []
            }

        # 4. 推送到飞书
        feishu = FeishuNotifier(webhook_url)
        push_success = feishu.send_toview_notification(
            username=target_user["username"],
            videos=videos
        )

        # 5. 记录推送历史
        db.save_toview_push_history(
            user_id=target_user_id,
            push_type="manual",
            videos=videos,
            success=push_success,
            error_message=None if push_success else "推送失败",
            pushed_by=current_user_id
        )

        if push_success:
            logger.info(
                f"[管理员 {username}] 手动推送成功，"
                f"target_user={target_user['username']}, count={len(videos)}"
            )
            return {
                "success": True,
                "message": f"推送成功，共 {len(videos)} 个视频",
                "pushed_videos": videos
            }
        else:
            logger.warning(
                f"[管理员 {username}] 手动推送失败，"
                f"target_user={target_user['username']}"
            )
            raise HTTPException(
                status_code=500,
                detail="推送失败，请检查飞书Webhook配置"
            )

    except CookieExpiredError:
        logger.warning(f"目标用户B站Cookie已过期: user_id={target_user_id}")
        raise HTTPException(
            status_code=401,
            detail="目标用户B站登录已过期"
        )

    except BilibiliAPIError as e:
        logger.error(f"B站API调用失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"B站API调用失败: {str(e)}"
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"手动推送失败: {e}", exc_info=True)

        # 记录失败历史
        try:
            db.save_toview_push_history(
                user_id=target_user_id,
                push_type="manual",
                videos=[],
                success=False,
                error_message=str(e),
                pushed_by=current_user_id
            )
        except Exception as db_error:
            logger.error(f"记录推送历史失败: {db_error}")

        raise HTTPException(
            status_code=500,
            detail=f"推送失败: {str(e)}"
        )


@router.get("/history")
async def get_history(request: Request, user_id: Optional[int] = None, limit: int = 100):
    """
    获取推送历史

    Args:
        user_id: 可选，管理员可查看指定用户的历史
        limit: 返回数量限制，默认100

    Returns:
        {
            "success": true,
            "data": [
                {
                    "id": 1,
                    "push_type": "auto",
                    "pushed_at": 1234567890,
                    "video_count": 3,
                    "success": true
                }
            ]
        }
    """
    is_admin = request.session.get("is_admin", False)
    current_user_id = request.session.get("user_id")
    username = request.session.get("username", "unknown")

    # 权限检查：普通用户只能查看自己的历史
    if user_id is not None and not is_admin:
        if user_id != current_user_id:
            logger.warning(f"非管理员尝试查看他人历史: user={username}")
            raise HTTPException(
                status_code=403,
                detail="无权限查看其他用户的推送历史"
            )

    # 确定查询的用户ID
    query_user_id = user_id if is_admin and user_id else current_user_id

    logger.info(
        f"API调用: GET /api/toview/history, "
        f"user={username}, query_user_id={query_user_id}, limit={limit}"
    )

    try:
        # 管理员不传user_id时查询所有
        if is_admin and user_id is None:
            histories = db.get_toview_push_history(user_id=None, limit=limit)
        else:
            histories = db.get_toview_push_history(user_id=query_user_id, limit=limit)

        logger.info(f"查询推送历史成功，共 {len(histories)} 条")

        return {
            "success": True,
            "data": histories
        }

    except Exception as e:
        logger.error(f"查询推送历史失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"查询失败: {str(e)}"
        )