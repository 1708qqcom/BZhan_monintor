"""
清空数据脚本

用途：删除所有JSON数据文件和数据库记录，用于测试扫码登录后的自动同步功能

使用方法：
    python scripts/clear_all_data.py
    python scripts/clear_all_data.py --keep-auth  # 保留B站登录信息
"""
import argparse
import logging
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import Database

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("clear_data")


def clear_json_files():
    """删除所有JSON数据文件"""
    data_dir = project_root / "data"

    if not data_dir.exists():
        logger.info(f"数据目录不存在: {data_dir}")
        return

    # 要删除的JSON文件列表
    json_files = [
        "history.json",      # 视频历史记录
        "cookies.json",      # Cookie文件（如果存在旧版）
    ]

    deleted_count = 0

    for filename in json_files:
        filepath = data_dir / filename
        if filepath.exists():
            try:
                os.remove(filepath)
                logger.info(f"✓ 已删除: {filepath}")
                deleted_count += 1
            except Exception as e:
                logger.error(f"✗ 删除失败: {filepath}, 错误: {e}")

    logger.info(f"共删除 {deleted_count} 个JSON文件")


def clear_database(keep_auth: bool = False):
    """
    清空数据库表数据

    Args:
        keep_auth: 是否保留B站登录信息
    """
    db = Database()

    # 确保数据库已初始化
    db.init_db()

    logger.info("开始清空数据库表...")

    with db._get_connection() as conn:
        cursor = conn.cursor()

        # 1. 删除视频历史记录
        cursor.execute("DELETE FROM videos")
        videos_count = cursor.rowcount
        logger.info(f"✓ 已删除 {videos_count} 条视频记录")

        # 2. 删除UP主记录
        cursor.execute("DELETE FROM ups")
        ups_count = cursor.rowcount
        logger.info(f"✓ 已删除 {ups_count} 个UP主")

        # 3. 清空配置（可选）
        # cursor.execute("DELETE FROM config")
        # config_count = cursor.rowcount
        # logger.info(f"✓ 已删除 {config_count} 项配置")

        # 4. 清空登录信息（可选）
        if not keep_auth:
            cursor.execute("UPDATE auth SET cookies = NULL, created_at = NULL, expires_at = NULL WHERE id = 1")
            logger.info("✓ 已清空B站登录信息")
        else:
            logger.info("⊗ 保留B站登录信息")

        conn.commit()

    logger.info("数据库清空完成")


def main():
    parser = argparse.ArgumentParser(
        description="清空JSON数据文件和数据库记录",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/clear_all_data.py              # 清空所有数据
    python scripts/clear_all_data.py --keep-auth  # 保留B站登录信息
        """
    )

    parser.add_argument(
        "--keep-auth",
        action="store_true",
        help="保留B站登录信息（Cookie）"
    )

    parser.add_argument(
        "--json-only",
        action="store_true",
        help="仅删除JSON文件"
    )

    parser.add_argument(
        "--db-only",
        action="store_true",
        help="仅清空数据库"
    )

    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("清空数据脚本")
    logger.info("=" * 50)

    # 确认操作
    if not args.keep_auth:
        logger.warning("⚠️  即将删除所有数据，包括B站登录信息！")
        logger.warning("⚠️  扫码登录后需要重新同步关注列表")

        confirm = input("\n确认继续？(y/N): ").strip().lower()
        if confirm != 'y':
            logger.info("已取消操作")
            return

    # 执行清空
    if not args.db_only:
        clear_json_files()

    if not args.json_only:
        clear_database(keep_auth=args.keep_auth)

    logger.info("=" * 50)
    logger.info("清空完成！")
    logger.info("=" * 50)

    # 提示后续操作
    if not args.keep_auth:
        logger.info("\n后续操作：")
        logger.info("1. 启动Web服务: python main.py --web")
        logger.info("2. 访问登录页面: http://localhost:3231/bilibili-login")
        logger.info("3. 扫码登录")
        logger.info("4. 验证UP主列表: curl http://localhost:3231/api/ups/sync")
    else:
        logger.info("\n后续操作：")
        logger.info("1. 启动Web服务: python main.py --web")
        logger.info("2. 访问登录页面: http://localhost:3231/bilibili-login")
        logger.info("3. 如果Cookie有效，可直接测试同步: curl -X POST http://localhost:3231/api/ups/sync")


if __name__ == "__main__":
    main()