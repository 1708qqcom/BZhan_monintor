"""
视频历史 API

端点：
- GET /api/videos - 获取推送历史（分页、筛选）
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.database import Database
from src.models import PaginatedVideoResponse, VideoResponse

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