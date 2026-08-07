"""
用户引导流程 API

端点：
- GET /api/onboarding/status - 获取引导进度
- POST /api/onboarding/complete-step - 完成步骤
- POST /api/onboarding/skip-step - 跳过步骤
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from src.database import Database
from src.models import (
    OnboardingStatusResponse,
    OnboardingProgress,
    OnboardingStepRequest,
    SuccessResponse,
)

logger = logging.getLogger("monitor.api.onboarding")

router = APIRouter(prefix="/api/onboarding", tags=["引导流程"])


# ==================== 依赖注入 ====================

def get_db() -> Database:
    """获取数据库实例（依赖注入）"""
    return Database()


# ==================== 辅助函数 ====================

def _calculate_progress_percent(progress: dict) -> int:
    """
    计算引导进度百分比

    Args:
        progress: 引导进度字典

    Returns:
        进度百分比（0-100）
    """
    completed_count = sum([
        progress.get("step1_completed", 0) or progress.get("step1_skipped", 0),
        progress.get("step2_completed", 0) or progress.get("step2_skipped", 0),
        progress.get("step3_completed", 0) or progress.get("step3_skipped", 0),
    ])
    return int((completed_count / 3) * 100)


def _check_is_completed(progress: dict) -> bool:
    """
    检查引导是否完成（所有步骤完成或跳过）

    Args:
        progress: 引导进度字典

    Returns:
        是否完成
    """
    step1_done = progress.get("step1_completed", 0) or progress.get("step1_skipped", 0)
    step2_done = progress.get("step2_completed", 0) or progress.get("step2_skipped", 0)
    step3_done = progress.get("step3_completed", 0) or progress.get("step3_skipped", 0)
    return bool(step1_done and step2_done and step3_done)


# ==================== API 端点 ====================

@router.get(
    "/status",
    response_model=OnboardingStatusResponse,
    summary="获取引导进度",
    description="查询当前用户的引导流程进度"
)
async def get_onboarding_status(
    request: Request,
    db: Database = Depends(get_db)
):
    """
    获取引导进度

    Returns:
        引导状态信息：
        - has_onboarding_record: 是否存在引导记录
        - progress: 引导进度详情（不存在则为 None）
    """
    logger.info("API调用: GET /api/onboarding/status")

    # 获取当前用户 ID
    user_id = request.session.get("user_id")
    if not user_id:
        logger.warning("未找到用户信息")
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        # 查询引导进度
        progress = db.get_onboarding_progress(user_id)

        # 不存在记录（老用户）
        if not progress:
            logger.info(f"用户无引导记录: user_id={user_id}")
            return OnboardingStatusResponse(
                has_onboarding_record=False,
                progress=None
            )

        # 计算进度百分比和完成状态
        progress_percent = _calculate_progress_percent(progress)
        is_completed = _check_is_completed(progress)

        # 构造响应
        return OnboardingStatusResponse(
            has_onboarding_record=True,
            progress=OnboardingProgress(
                user_id=progress["user_id"],
                current_step=progress["current_step"],
                step1_completed=bool(progress["step1_completed"]),
                step1_skipped=bool(progress["step1_skipped"]),
                step2_completed=bool(progress["step2_completed"]),
                step2_skipped=bool(progress["step2_skipped"]),
                step3_completed=bool(progress["step3_completed"]),
                step3_skipped=bool(progress["step3_skipped"]),
                progress_percent=progress_percent,
                is_completed=is_completed
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取引导进度失败: user_id={user_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.post(
    "/complete-step",
    response_model=SuccessResponse,
    summary="完成引导步骤",
    description="标记指定的引导步骤为已完成"
)
async def complete_onboarding_step(
    request: Request,
    body: OnboardingStepRequest,
    db: Database = Depends(get_db)
):
    """
    完成引导步骤

    Args:
        body: 包含步骤编号的请求体（step: 1-3）

    Returns:
        成功消息
    """
    logger.info(f"API调用: POST /api/onboarding/complete-step, step={body.step}")

    # 获取当前用户 ID
    user_id = request.session.get("user_id")
    if not user_id:
        logger.warning("未找到用户信息")
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        # 更新步骤状态
        success = db.update_onboarding_step(user_id, body.step, completed=True)

        if not success:
            logger.warning(f"更新引导步骤失败: user_id={user_id}, step={body.step}")
            raise HTTPException(status_code=404, detail="引导记录不存在")

        logger.info(f"引导步骤已完成: user_id={user_id}, step={body.step}")

        return SuccessResponse(message=f"步骤{body.step}已完成")

    except ValueError as e:
        logger.warning(f"参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"完成引导步骤失败: user_id={user_id}, step={body.step}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.post(
    "/skip-step",
    response_model=SuccessResponse,
    summary="跳过引导步骤",
    description="跳过指定的引导步骤"
)
async def skip_onboarding_step(
    request: Request,
    body: OnboardingStepRequest,
    db: Database = Depends(get_db)
):
    """
    跳过引导步骤

    Args:
        body: 包含步骤编号的请求体（step: 1-3）

    Returns:
        成功消息
    """
    logger.info(f"API调用: POST /api/onboarding/skip-step, step={body.step}")

    # 获取当前用户 ID
    user_id = request.session.get("user_id")
    if not user_id:
        logger.warning("未找到用户信息")
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        # 更新步骤状态
        success = db.update_onboarding_step(user_id, body.step, skipped=True)

        if not success:
            logger.warning(f"更新引导步骤失败: user_id={user_id}, step={body.step}")
            raise HTTPException(status_code=404, detail="引导记录不存在")

        logger.info(f"引导步骤已跳过: user_id={user_id}, step={body.step}")

        return SuccessResponse(message=f"步骤{body.step}已跳过")

    except ValueError as e:
        logger.warning(f"参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"跳过引导步骤失败: user_id={user_id}, step={body.step}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")
