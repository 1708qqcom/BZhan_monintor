"""
更新UP主头像脚本

从B站API获取UP主详细信息并更新数据库
"""
import sys
import logging
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
    """更新UP主头像"""
    db = Database()

    # 获取Cookie
    auth = db.get_auth()
    if not auth or not auth.get("cookies"):
        logger.error("未登录B站账号，请先登录")
        return

    # 创建B站客户端
    client = BilibiliClient(cookies=auth["cookies"])

    # 获取所有UP主
    ups = db.get_ups()
    logger.info(f"共 {len(ups)} 个UP主需要更新")

    success_count = 0
    fail_count = 0

    for up in ups:
        mid = up["mid"]
        old_name = up["name"]
        old_face = up.get("face", "")

        try:
            logger.info(f"更新UP主: {old_name} (mid={mid})")

            # 获取UP主信息
            up_info = client.get_up_info(mid)

            new_name = up_info.get("name", old_name)
            new_face = up_info.get("face", "")

            # 更新数据库
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE ups
                    SET name = ?, face = ?, updated_at = datetime('now')
                    WHERE mid = ?
                """, (new_name, new_face, mid))
                conn.commit()

            logger.info(f"  ✓ 更新成功: {new_name}, 头像: {new_face[:50]}...")
            success_count += 1

        except Exception as e:
            logger.error(f"  ✗ 更新失败: {e}")
            fail_count += 1

    logger.info(f"更新完成: 成功 {success_count}, 失败 {fail_count}")


if __name__ == "__main__":
    main()