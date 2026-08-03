"""
视频历史 API

端点：
- GET /api/videos - 获取推送历史（分页、筛选）
- POST /api/videos/{bvid}/push - 手动推送视频到飞书
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.bilibili import BilibiliClient
from src.database import Database
from src.exceptions import BilibiliAPIError, FeishuAPIError
from src.feishu import FeishuNotifier
from src.models import (
    ErrorResponse,
    PaginatedVideoResponse,
    SuccessResponse,
    VideoResponse,
)

logger = logging.getLogger("monitor.api.videos")

router = APIRouter(prefix="/api/videos", tags=["推送历史"])


# ==================== 依赖注入 ====================

def get_db() -> Database:
    """获取数据库实例（依赖注入）"""
    return Database()


# ==================== API 端点 ====================

@router.get(
    "",
    response_model=PaginatedVideoResponse,
    summary="获取推送历史",
    description="分页查询视频推送历史，支持按UP主和日期筛选"
)
async def get_videos(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    up_id: Optional[int] = Query(None, description="按UP主筛选"),
    date_from: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    db: Database = Depends(get_db),
):
    """
    获取推送历史

    Args:
        page: 页码（从1开始）
        page_size: 每页数量（最大100）
        up_id: 按UP主筛选
        date_from: 开始日期
        date_to: 结束日期

    Returns:
        分页视频列表
    """
    logger.info(
        f"API调用: GET /api/videos, "
        f"page={page}, page_size={page_size}, "
        f"up_id={up_id}, date_from={date_from}, date_to={date_to}"
    )

    try:
        # 查询数据库
        result = db.get_videos(
            page=page,
            page_size=page_size,
            up_id=up_id,
            date_from=date_from,
            date_to=date_to,
        )

        # 转换为响应模型
        items = [VideoResponse(**item) for item in result["items"]]

        logger.info(
            f"返回 {len(items)} 条视频记录，"
            f"总计 {result['total']} 条"
        )

        return PaginatedVideoResponse(
            items=items,
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
        )

    except Exception as e:
        logger.error(f"获取视频历史失败: {e}", exc_info=True)
        raise


@router.post(
    "/{bvid}/push",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse},
        400: {"model": ErrorResponse, "description": "Webhook未配置或参数错误"},
        404: {"model": ErrorResponse, "description": "视频不存在"},
        500: {"model": ErrorResponse, "description": "推送失败"},
    },
    summary="手动推送视频到飞书",
    description="将指定视频推送到飞书群，如视频信息不完整会自动补全"
)
async def push_video(
    bvid: str,
    db: Database = Depends(get_db),
):
    """
    手动推送视频到飞书

    Args:
        bvid: 视频BV号

    Returns:
        推送结果

    Raises:
        HTTPException: 404 视频不存在
        HTTPException: 400 Webhook未配置
        HTTPException: 500 推送失败
    """
    logger.info(f"[手动推送] 开始推送视频: bvid={bvid}")

    push_success = False
    error_msg = None
    video_id = None

    try:
        # 1. 查询视频记录
        video = db.get_video_by_bvid(bvid)
        if not video:
            logger.warning(f"[手动推送] 视频不存在: bvid={bvid}")
            raise HTTPException(status_code=404, detail=f"视频不存在: {bvid}")

        video_id = video["id"]

        # 2. 检查视频信息完整性
        required_fields = ["title", "url", "pub_time", "view_count"]
        missing_fields = [f for f in required_fields if not video.get(f)]

        if missing_fields:
            logger.warning(
                f"[手动推送] 视频信息不完整，缺失字段: {missing_fields}, "
                f"调用B站API补全"
            )

            try:
                # 补全视频信息
                await _supplement_video_info(bvid, video, db)
            except BilibiliAPIError as e:
                logger.error(f"[手动推送] 补全视频信息失败: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"补全视频信息失败: {e.message}"
                )

        # 3. 获取UP主信息
        up_id = video.get("up_id")
        if not up_id:
            logger.error(f"[手动推送] 视频缺少up_id: bvid={bvid}")
            raise HTTPException(
                status_code=500,
                detail="视频数据异常：缺少UP主信息"
            )

        # 通过 up_id 查询 UP主信息（up_id 是 ups 表的主键 id）
        up_info = _get_up_by_id(db, up_id)
        up_name = up_info.get("name", "未知UP主") if up_info else "未知UP主"

        # 4. 获取飞书 Webhook 配置
        webhook_url = db.get_config_value("feishu_webhook_url")
        if not webhook_url:
            logger.error("[手动推送] 飞书 Webhook 未配置")
            raise HTTPException(
                status_code=400,
                detail="飞书 Webhook 未配置，请先在设置页面配置"
            )

        # 5. 发送飞书通知
        logger.info(f"[手动推送] 发送飞书通知: {video['title']}")

        notifier = FeishuNotifier(webhook_url)
        push_success = notifier.send_new_video_notification(
            up_name=up_name,
            video_title=video["title"],
            video_url=video.get("url", f"https://www.bilibili.com/video/{bvid}"),
            pub_time=video.get("pub_time", "未知时间"),
            view_count=video.get("view_count", 0),
        )

        if push_success:
            logger.info(f"[手动推送] 推送成功: bvid={bvid}, title={video['title']}")

            # 更新视频推送状态
            db.update_video_pushed(bvid, pushed=True)

            return SuccessResponse(
                message="推送成功",
                data={"bvid": bvid, "title": video["title"]}
            )
        else:
            error_msg = "飞书推送返回失败"
            logger.error(f"[手动推送] 推送失败: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

    except HTTPException:
        # HTTPException 向上抛出
        raise

    except FeishuAPIError as e:
        error_msg = f"飞书API错误: {e.message}"
        logger.error(f"[手动推送] 推送失败: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

    except Exception as e:
        error_msg = f"推送异常: {str(e)}"
        logger.error(f"[手动推送] 推送异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)

    finally:
        # 记录推送历史（无论成功失败）
        if video_id:
            try:
                db.add_push_history(
                    video_id=video_id,
                    push_type="manual",
                    success=push_success,
                    error_message=error_msg,
                )
            except Exception as e:
                logger.error(f"[手动推送] 记录推送历史失败: {e}")


async def _supplement_video_info(bvid: str, video: dict, db: Database) -> None:
    """
    补全视频信息（内部方法）

    Args:
        bvid: 视频BV号
        video: 当前视频记录
        db: 数据库实例

    Raises:
        BilibiliAPIError: API调用失败
    """
    # 获取登录信息
    auth = db.get_auth()
    cookies = auth.get("cookies") if auth else None

    # 初始化B站客户端
    client = BilibiliClient(cookies=cookies)

    # 获取视频详情
    detail = client.get_video_detail(bvid)

    # 更新数据库
    update_data = {}
    if not video.get("title") and detail.get("title"):
        update_data["title"] = detail["title"]
    if not video.get("pub_time") and detail.get("pub_date"):
        update_data["pub_time"] = detail["pub_date"]
    if not video.get("view_count") and detail.get("view_count"):
        update_data["view_count"] = detail["view_count"]

    # 确保URL存在
    if not video.get("url"):
        update_data["url"] = f"https://www.bilibili.com/video/{bvid}"

    if update_data:
        db.update_video(bvid, update_data)
        # 更新本地video对象，供后续使用
        video.update(update_data)
        logger.info(f"[手动推送] 视频信息已补全: {list(update_data.keys())}")


def _get_up_by_id(db: Database, up_id: int) -> Optional[dict]:
    """
    通过数据库 ID 查询 UP主信息

    Args:
        db: 数据库实例
        up_id: ups 表的主键 ID

    Returns:
        UP主信息字典，不存在返回 None
    """
    logger.debug(f"查询 UP主: up_id={up_id}")

    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, mid, name, face, is_monitoring, created_at, updated_at
            FROM ups
            WHERE id = ?
        """, (up_id,))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None