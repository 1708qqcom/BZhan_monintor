"""
关注列表同步服务

功能：
- 从B站API获取关注列表
- 同步到数据库
- 提供给API和登录流程共用

设计原则：
- 独立服务模块，方便多处调用
- 详细日志输出，方便调试
- 异常隔离，同步失败不影响主流程
"""
import logging
import sqlite3
from typing import Optional

from src.bilibili import BilibiliClient
from src.database import Database

logger = logging.getLogger("monitor.sync_service")


def sync_followed_ups(
    db: Database,
    cookies: dict,
    max_count: int = 50,
) -> dict:
    """
    同步B站关注列表到数据库

    Args:
        db: 数据库实例
        cookies: B站Cookie字典
        max_count: 最多同步数量，默认50

    Returns:
        同步结果 {
            "success": bool,
            "total": int,      # 获取到的总数
            "added": int,      # 新增数量
            "skipped": int,    # 跳过数量（已存在）
            "failed": int,     # 失败数量
            "message": str,    # 结果消息
        }
    """
    logger.info(f"[SyncService] 开始同步关注列表，max_count={max_count}")

    result = {
        "success": False,
        "total": 0,
        "added": 0,
        "skipped": 0,
        "failed": 0,
        "message": "",
    }

    try:
        # 1. 创建B站客户端
        logger.debug("[SyncService] 创建 BilibiliClient 实例")
        client = BilibiliClient(cookies=cookies)

        # 2. 调用B站API获取关注列表
        logger.info(f"[SyncService] 调用 B站API 获取关注列表...")
        ups = client.get_followed_ups(max_count=max_count)

        if not ups:
            logger.warning("[SyncService] 未获取到任何UP主")
            result["success"] = True
            result["message"] = "关注列表为空"
            return result

        result["total"] = len(ups)
        logger.info(f"[SyncService] 获取到 {len(ups)} 个UP主，开始写入数据库")

        # 3. 遍历写入数据库
        for idx, up in enumerate(ups, 1):
            mid = up.get("mid")
            uname = up.get("uname", f"UP主_{mid}")
            face = up.get("face", "")

            logger.debug(f"[SyncService] 处理第 {idx}/{len(ups)} 个: mid={mid}, name={uname}")

            try:
                # 尝试添加到数据库
                up_id = db.add_up(mid=mid, name=uname, face=face)
                result["added"] += 1
                logger.debug(f"[SyncService] 添加成功: id={up_id}, mid={mid}")

            except sqlite3.IntegrityError:
                # UP主已存在，跳过
                result["skipped"] += 1
                logger.debug(f"[SyncService] UP主已存在，跳过: mid={mid}")

            except Exception as e:
                # 其他错误
                result["failed"] += 1
                logger.error(f"[SyncService] 添加UP主失败: mid={mid}, error={e}")

        # 4. 构造结果消息
        result["success"] = True
        result["message"] = f"同步完成: 获取{result['total']}个, 新增{result['added']}个, 跳过{result['skipped']}个"

        logger.info(f"[SyncService] {result['message']}")

        return result

    except Exception as e:
        # 整体同步失败
        error_msg = f"同步失败: {str(e)}"
        result["success"] = False
        result["message"] = error_msg
        logger.error(f"[SyncService] {error_msg}", exc_info=True)
        return result