"""
登录状态 API

端点：
- GET /api/login/status - 查询登录状态
- GET /api/login/qrcode - 获取登录二维码
- POST /api/login/poll - 轮询扫码结果并保存登录信息
- POST /api/login/logout - 退出登录
"""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from src.database import Database
from src.models import LoginStatusResponse, QrCodeResponse, SuccessResponse
from src.login import BilibiliLogin
from src.sync_service import sync_followed_ups

logger = logging.getLogger("monitor.api.login")

router = APIRouter(prefix="/api/login", tags=["登录管理"])

# 临时存储 auth_code（生产环境应使用 Redis 或数据库）
_auth_code_store: dict = {}


# ==================== 依赖注入 ====================

def get_db() -> Database:
    """获取数据库实例（依赖注入）"""
    return Database()


# ==================== API 端点 ====================

@router.get(
    "/status",
    response_model=LoginStatusResponse,
    summary="查询登录状态",
    description="查询当前B站账号登录状态和Cookie有效期"
)
async def get_login_status(db: Database = Depends(get_db)):
    """
    查询登录状态

    Returns:
        登录状态信息
    """
    logger.info("API调用: GET /api/login/status")

    try:
        # 从数据库获取登录信息
        auth = db.get_auth()

        if not auth or not auth.get("cookies"):
            logger.info("未登录")
            return LoginStatusResponse(
                is_logged_in=False,
                message="未登录B站账号"
            )

        # 计算剩余天数
        expires_at = auth.get("expires_at")
        days_remaining = None

        if expires_at:
            try:
                expires_date = datetime.fromisoformat(expires_at)
                days_remaining = (expires_date - datetime.now()).days

                logger.debug(f"Cookie过期时间: {expires_at}, 剩余{days_remaining}天")

            except Exception as e:
                logger.warning(f"解析过期时间失败: {e}")

        # 构造响应
        username = auth["cookies"].get("uname", "未知用户")

        logger.info(f"已登录: username={username}, days_remaining={days_remaining}")

        return LoginStatusResponse(
            is_logged_in=True,
            username=username,
            expires_at=expires_at,
            days_remaining=days_remaining,
            message="登录状态正常" if days_remaining and days_remaining > 7 else "Cookie即将过期，建议重新登录"
        )

    except Exception as e:
        logger.error(f"查询登录状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/qrcode",
    response_model=QrCodeResponse,
    summary="获取登录二维码",
    description="获取B站扫码登录二维码"
)
async def get_qrcode():
    """
    获取登录二维码

    Returns:
        二维码URL和图片URL
    """
    logger.info("API调用: GET /api/login/qrcode")

    try:
        # 使用登录模块生成二维码
        login = BilibiliLogin()

        logger.debug("调用BilibiliLogin生成二维码")
        auth_code, qrcode_url = login.generate_qrcode()

        if not auth_code or not qrcode_url:
            logger.error("生成二维码失败")
            raise HTTPException(
                status_code=500,
                detail="生成二维码失败"
            )

        # 临时存储 auth_code 供后续轮询使用
        _auth_code_store["current"] = auth_code
        logger.info(f"二维码生成成功，auth_code 已保存")

        # 生成二维码图片URL（使用 Segno 在本地生成 base64 图片）
        import segno
        import io
        import base64

        qr = segno.make(qrcode_url)
        buffer = io.BytesIO()
        qr.save(buffer, kind="png", scale=5)
        buffer.seek(0)
        qr_base64 = base64.b64encode(buffer.read()).decode("utf-8")
        image_url = f"data:image/png;base64,{qr_base64}"

        return QrCodeResponse(
            qrcode_url=qrcode_url,
            image_url=image_url
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取二维码失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/poll",
    response_model=SuccessResponse,
    summary="轮询扫码结果",
    description="轮询B站扫码登录结果，成功则保存Cookie"
)
async def poll_scan_result(db: Database = Depends(get_db)):
    """
    轮询扫码结果

    检查用户是否已扫码确认，如果成功则保存Cookie到数据库

    Returns:
        扫码结果
    """
    logger.info("API调用: POST /api/login/poll")

    try:
        # 获取保存的 auth_code
        auth_code = _auth_code_store.get("current")

        if not auth_code:
            logger.warning("未找到 auth_code，可能二维码已过期")
            return SuccessResponse(
                message="二维码已过期，请重新获取",
                data={"status": "expired"}
            )

        # 使用登录模块轮询扫码结果
        login = BilibiliLogin()

        logger.debug(f"轮询扫码结果: auth_code={auth_code[:20]}...")
        cookies = login.poll_scan_result(auth_code, timeout=10)

        if cookies:
            # 扫码成功，保存 Cookie
            logger.info(f"扫码成功，获取到 cookies: {list(cookies.keys())}")

            # 计算过期时间（B站 Cookie 一般 30 天有效）
            expires_at = (datetime.now() + timedelta(days=30)).isoformat()

            # 保存到数据库
            db.save_auth(cookies, expires_at=expires_at)

            # 清除临时存储
            _auth_code_store.pop("current", None)

            logger.info("登录信息已保存到数据库")

            # ========== 自动同步关注列表 ==========
            sync_result = None
            try:
                logger.info("开始自动同步关注列表...")

                # 从数据库读取配置
                max_ups_str = db.get_config_value("max_ups", default="50")
                try:
                    max_ups = int(max_ups_str)
                except (ValueError, TypeError):
                    max_ups = 50

                logger.info(f"同步数量配置: max_ups={max_ups}")

                sync_result = sync_followed_ups(
                    db=db,
                    cookies=cookies,
                    max_count=max_ups,
                    fetch_videos=True,
                )

                logger.info(f"自动同步完成: {sync_result['message']}")

            except Exception as e:
                # 同步失败不影响登录成功
                logger.error(f"自动同步失败（不影响登录）: {e}", exc_info=True)
                sync_result = {
                    "success": False,
                    "message": f"同步失败: {str(e)}",
                }

            # 构造响应（包含同步结果）
            response_data = {
                "status": "success",
                "cookies": list(cookies.keys()),
                "sync_result": sync_result,
            }

            return SuccessResponse(
                message="登录成功",
                data=response_data,
            )
        else:
            # 未扫码或扫码中
            return SuccessResponse(
                message="等待扫码",
                data={"status": "waiting"}
            )

    except Exception as e:
        logger.error(f"轮询扫码结果失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/logout",
    response_model=SuccessResponse,
    summary="退出登录",
    description="清除B站账号登录信息"
)
async def logout(db: Database = Depends(get_db)):
    """
    退出登录

    清除数据库中的登录信息

    Returns:
        成功消息
    """
    logger.info("API调用: POST /api/login/logout")

    try:
        # 清除数据库中的登录信息
        db.clear_auth()

        logger.info("B站账号已退出登录")

        return SuccessResponse(message="已退出登录")

    except Exception as e:
        logger.error(f"退出登录失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))