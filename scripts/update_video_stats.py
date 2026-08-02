"""
更新视频播放量和推送时间脚本

功能：
- 从B站API获取视频播放量
- 对于未设置推送时间的记录，设置为迁移当天
"""
import sys
import logging
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import Database
from src.bilibili import BilibiliClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """更新视频播放量和推送时间"""
    db = Database()

    # 获取Cookie
    auth = db.get_auth()
    if not auth or not auth.get("cookies"):
        logger.error("未登录B站账号，请先登录")
        return

    # 创建B站客户端
    client = BilibiliClient(cookies=auth["cookies"])

    # 获取所有视频
    result = db.get_videos(page=1, page_size=10000)
    videos = result["items"]

    # 限制处理数量（测试用）
    videos = videos[:10]

    logger.info(f"共 {len(videos)} 条视频记录需要更新")

    # 迷移日期（用于设置历史数据的推送时间）
    migration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    success_count = 0
    fail_count = 0

    for i, video in enumerate(videos, 1):
        bvid = video["bvid"]
        title = video["title"][:30]  # 截断标题
        old_view_count = video.get("view_count", 0)
        old_pushed_at = video.get("pushed_at")

        try:
            logger.info(f"[{i}/{len(videos)}] 更新: {bvid} - {title}...")

            # 获取视频信息（包含播放量）
            video_info = client.get_video_info(bvid=bvid)
            new_view_count = video_info["stat"]["view"]

            # 推送时间：如果原数据为空，使用迁移日期
            new_pushed_at = old_pushed_at if old_pushed_at else migration_date

            # 更新数据库
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE videos
                    SET view_count = ?, pushed_at = ?
                    WHERE bvid = ?
                """, (new_view_count, new_pushed_at, bvid))
                conn.commit()

            logger.info(f"  ✓ 播放量: {old_view_count} -> {new_view_count}, 推送时间: {new_pushed_at}")
            success_count += 1

        except Exception as e:
            logger.error(f"  ✗ 更新失败: {e}")
            fail_count += 1

        # 每10个视频输出进度
        if i % 10 == 0:
            logger.info(f"进度: {i}/{len(videos)}, 成功: {success_count}, 失败: {fail_count}")

    logger.info(f"更新完成: 成功 {success_count}, 失败 {fail_count}")


if __name__ == "__main__":
    main()
