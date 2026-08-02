"""
数据迁移脚本：JSON -> SQLite

功能：
- 备份 data/video_history.json
- 解析 JSON 提取 UP主 去重
- 插入 UP主 到 ups 表
- 插入视频记录到 videos 表
- 校验迁移前后记录数一致
- 输出迁移报告

使用方法：
    python scripts/migrate_json_to_sqlite.py
"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("migration")

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


def migrate_json_to_sqlite(
    json_file: str = "data/video_history.json",
    db_file: str = "data/monitor.db",
    backup_suffix: str = None
):
    """
    执行数据迁移

    Args:
        json_file: JSON 历史文件路径
        db_file: 数据库文件路径
        backup_suffix: 备份文件后缀
    """
    logger.info("=" * 60)
    logger.info("开始数据迁移：JSON -> SQLite")
    logger.info("=" * 60)

    # 导入数据库模块
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.database import Database

    # 路径处理
    json_path = PROJECT_ROOT / json_file
    db_path = PROJECT_ROOT / db_file

    # 检查 JSON 文件
    if not json_path.exists():
        logger.error(f"JSON 文件不存在: {json_path}")
        return False

    logger.info(f"JSON 文件: {json_path}")
    logger.info(f"数据库文件: {db_path}")

    # 1. 备份 JSON 文件
    if backup_suffix is None:
        backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_path = json_path.with_suffix(f".json.backup_{backup_suffix}")

    logger.info(f"备份 JSON 文件到: {backup_path}")
    shutil.copy2(json_path, backup_path)

    # 2. 读取 JSON 数据
    logger.info("读取 JSON 数据...")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"读取 JSON 失败: {e}")
        return False

    videos_data = data.get("videos", {})
    logger.info(f"JSON 中共有 {len(videos_data)} 条视频记录")

    # 3. 提取 UP主 信息（去重）
    logger.info("提取 UP主 信息...")
    ups_map = {}  # {mid: {name, face}}

    for bvid, video in videos_data.items():
        up_id = video.get("up_id")
        up_name = video.get("up_name", "未知UP主")

        if up_id and up_id not in ups_map:
            ups_map[up_id] = {
                "name": up_name,
                "face": ""  # JSON 中没有头像信息
            }

    logger.info(f"提取到 {len(ups_map)} 个 UP主")

    # 4. 初始化数据库
    logger.info("初始化数据库...")
    db = Database(str(db_path))
    db.init_db()

    # 5. 插入 UP主
    logger.info("插入 UP主 数据...")
    up_id_mapping = {}  # {mid: db_id}

    for mid, info in ups_map.items():
        try:
            db_id = db.add_up(mid=mid, name=info["name"], face=info["face"])
            up_id_mapping[mid] = db_id
            logger.debug(f"UP主已插入: mid={mid}, name={info['name']}, db_id={db_id}")
        except Exception as e:
            # UP主可能已存在
            existing = db.get_up_by_mid(mid)
            if existing:
                up_id_mapping[mid] = existing["id"]
                logger.debug(f"UP主已存在: mid={mid}, db_id={existing['id']}")
            else:
                logger.warning(f"插入 UP主 失败: mid={mid}, {e}")

    logger.info(f"UP主 插入完成，共 {len(up_id_mapping)} 个")

    # 6. 插入视频记录
    logger.info("插入视频记录...")
    success_count = 0
    fail_count = 0

    for bvid, video in videos_data.items():
        try:
            up_id = video.get("up_id")
            db_up_id = up_id_mapping.get(up_id)

            if not db_up_id:
                logger.warning(f"视频 {bvid} 的 UP主 不存在: up_id={up_id}")
                fail_count += 1
                continue

            # 构造视频 URL
            video_url = f"https://www.bilibili.com/video/{bvid}"

            # 插入视频
            db.add_video(
                up_id=db_up_id,
                bvid=bvid,
                title=video.get("title", ""),
                url=video_url,
                pub_time=None,  # JSON 中没有标准的发布时间
                view_count=0,
                pushed=video.get("pushed", False),
                pushed_at=video.get("pushed_at"),
            )

            success_count += 1
            logger.debug(f"视频已插入: {bvid}")

        except Exception as e:
            # 视频可能已存在
            existing = db.get_video_by_bvid(bvid)
            if existing:
                logger.debug(f"视频已存在: {bvid}")
                success_count += 1
            else:
                logger.warning(f"插入视频失败: {bvid}, {e}")
                fail_count += 1

    logger.info(f"视频插入完成: 成功 {success_count}, 失败 {fail_count}")

    # 7. 校验数据
    logger.info("校验迁移结果...")

    db_videos = db.get_videos(page=1, page_size=10000)
    db_count = db_videos["total"]
    json_count = len(videos_data)

    logger.info(f"JSON 视频数: {json_count}")
    logger.info(f"数据库视频数: {db_count}")

    if db_count >= json_count:
        logger.info("✓ 迁移校验通过")
    else:
        logger.warning(f"⚠ 迁移数量不一致，可能存在数据丢失")

    # 8. 迁移报告
    logger.info("=" * 60)
    logger.info("迁移报告")
    logger.info("=" * 60)
    logger.info(f"源文件: {json_path}")
    logger.info(f"目标数据库: {db_path}")
    logger.info(f"备份文件: {backup_path}")
    logger.info(f"UP主 数量: {len(ups_map)}")
    logger.info(f"视频记录数: {success_count}")
    logger.info(f"失败记录数: {fail_count}")
    logger.info("=" * 60)
    logger.info("迁移完成")

    return True


if __name__ == "__main__":
    migrate_json_to_sqlite()