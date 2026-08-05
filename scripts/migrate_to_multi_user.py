"""
多用户隔离数据迁移脚本

功能：
- 备份现有数据库
- 创建 users 表
- 重建 auth 表（添加 user_id）
- ups/config 表添加 user_id 字段
- 创建默认管理员用户
- 迁移现有数据到默认用户
- 支持回滚

使用方法：
    python scripts/migrate_to_multi_user.py --backup    # 仅备份
    python scripts/migrate_to_multi_user.py --migrate   # 执行迁移
    python scripts/migrate_to_multi_user.py --rollback  # 回滚

注意：
- 迁移前必须备份
- 建议先在测试环境验证
"""
import argparse
import json
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("migration")

# 默认管理员信息
DEFAULT_ADMIN = {
    "username": "admin",
    "password": "Huisec@123",
}


class MultiUserMigrator:
    """多用户数据迁移器"""

    def __init__(self, db_path: str = None):
        """
        初始化迁移器

        Args:
            db_path: 数据库文件路径，默认为 data/monitor.db
        """
        if db_path is None:
            project_root = Path(__file__).parent.parent
            db_path = project_root / "data" / "monitor.db"

        self.db_path = Path(db_path)
        self.backup_path = self.db_path.with_suffix(".db.backup")
        self.rollback_path = self.db_path.with_suffix(".db.rollback")

        logger.info(f"数据库路径: {self.db_path}")
        logger.info(f"备份路径: {self.backup_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """
        获取数据库连接

        Returns:
            数据库连接对象
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def backup(self) -> bool:
        """
        备份数据库

        Returns:
            成功返回 True
        """
        logger.info("=" * 50)
        logger.info("开始备份数据库...")

        if not self.db_path.exists():
            logger.error(f"数据库文件不存在: {self.db_path}")
            return False

        try:
            # 删除旧备份
            if self.backup_path.exists():
                self.backup_path.unlink()
                logger.info(f"已删除旧备份: {self.backup_path}")

            # 创建新备份
            shutil.copy2(self.db_path, self.backup_path)
            logger.info(f"备份完成: {self.backup_path}")
            logger.info(f"备份大小: {self.backup_path.stat().st_size / 1024:.2f} KB")

            return True

        except Exception as e:
            logger.error(f"备份失败: {e}", exc_info=True)
            return False

    def create_users_table(self, conn: sqlite3.Connection) -> bool:
        """
        创建 users 表

        Args:
            conn: 数据库连接

        Returns:
            成功返回 True
        """
        logger.info("创建 users 表...")

        try:
            cursor = conn.cursor()

            # 检查表是否已存在
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='users'
            """)

            if cursor.fetchone():
                logger.warning("users 表已存在，跳过创建")
                return True

            # 创建 users 表
            cursor.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    is_admin INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
            """)

            conn.commit()
            logger.info("users 表创建成功")
            return True

        except Exception as e:
            logger.error(f"创建 users 表失败: {e}", exc_info=True)
            return False

    def create_default_admin(self, conn: sqlite3.Connection) -> bool:
        """
        创建默认管理员用户

        Args:
            conn: 数据库连接

        Returns:
            成功返回 True
        """
        logger.info("创建默认管理员用户...")

        try:
            cursor = conn.cursor()

            # 检查是否已存在
            cursor.execute("SELECT id FROM users WHERE username = ?", (DEFAULT_ADMIN["username"],))

            if cursor.fetchone():
                logger.warning(f"管理员用户已存在: {DEFAULT_ADMIN['username']}")
                return True

            # 创建管理员
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO users (id, username, password, is_admin, created_at, updated_at)
                VALUES (1, ?, ?, 1, ?, ?)
            """, (
                DEFAULT_ADMIN["username"],
                DEFAULT_ADMIN["password"],
                now,
                now
            ))

            conn.commit()
            logger.info(f"默认管理员创建成功: username={DEFAULT_ADMIN['username']}, password={DEFAULT_ADMIN['password']}")
            return True

        except Exception as e:
            logger.error(f"创建默认管理员失败: {e}", exc_info=True)
            return False

    def rebuild_auth_table(self, conn: sqlite3.Connection) -> bool:
        """
        重建 auth 表（添加 user_id）

        Args:
            conn: 数据库连接

        Returns:
            成功返回 True
        """
        logger.info("重建 auth 表...")

        try:
            cursor = conn.cursor()

            # 1. 读取现有 auth 数据
            cursor.execute("SELECT cookies, created_at, expires_at FROM auth WHERE id = 1")
            old_auth = cursor.fetchone()
            old_cookies = old_auth["cookies"] if old_auth else None
            old_created_at = old_auth["created_at"] if old_auth else None
            old_expires_at = old_auth["expires_at"] if old_auth else None

            logger.info(f"现有 auth 数据: cookies={'有' if old_cookies else '无'}")

            # 2. 删除旧表
            cursor.execute("DROP TABLE IF EXISTS auth")
            logger.info("已删除旧 auth 表")

            # 3. 创建新表
            cursor.execute("""
                CREATE TABLE auth (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    cookies TEXT,
                    created_at TEXT,
                    expires_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_user_id ON auth(user_id)
            """)

            # 4. 迁移数据到默认用户
            if old_cookies:
                cursor.execute("""
                    INSERT INTO auth (user_id, cookies, created_at, expires_at)
                    VALUES (1, ?, ?, ?)
                """, (old_cookies, old_created_at, old_expires_at))
                logger.info("已迁移 auth 数据到默认用户")
            else:
                logger.info("无 auth 数据需要迁移")

            conn.commit()
            logger.info("auth 表重建成功")
            return True

        except Exception as e:
            logger.error(f"重建 auth 表失败: {e}", exc_info=True)
            return False

    def alter_ups_table(self, conn: sqlite3.Connection) -> bool:
        """
        ups 表添加 user_id 字段

        Args:
            conn: 数据库连接

        Returns:
            成功返回 True
        """
        logger.info("修改 ups 表...")

        try:
            cursor = conn.cursor()

            # 1. 检查是否已有 user_id 字段
            cursor.execute("PRAGMA table_info(ups)")
            columns = [row["name"] for row in cursor.fetchall()]

            if "user_id" in columns:
                logger.warning("ups 表已有 user_id 字段，跳过")
                return True

            # 2. 添加 user_id 字段（默认值为 1）
            cursor.execute("""
                ALTER TABLE ups ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1
            """)

            # 3. 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ups_user_id ON ups(user_id)
            """)

            conn.commit()
            logger.info("ups 表修改成功，已添加 user_id 字段")
            return True

        except Exception as e:
            logger.error(f"修改 ups 表失败: {e}", exc_info=True)
            return False

    def alter_config_table(self, conn: sqlite3.Connection) -> bool:
        """
        config 表添加 user_id 字段

        Args:
            conn: 数据库连接

        Returns:
            成功返回 True
        """
        logger.info("修改 config 表...")

        try:
            cursor = conn.cursor()

            # 1. 检查是否已有 user_id 字段
            cursor.execute("PRAGMA table_info(config)")
            columns = [row["name"] for row in cursor.fetchall()]

            if "user_id" in columns:
                logger.warning("config 表已有 user_id 字段，跳过")
                return True

            # 2. 添加 user_id 字段（NULL 表示全局配置）
            cursor.execute("""
                ALTER TABLE config ADD COLUMN user_id INTEGER
            """)

            # 3. 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_config_user_id ON config(user_id)
            """)

            # 4. 将现有配置标记为全局配置（user_id = NULL）
            # 注意：全局配置如检查间隔等，user_id 保持为 NULL
            # 用户级别配置（如飞书Webhook）后续由用户自己设置

            conn.commit()
            logger.info("config 表修改成功，已添加 user_id 字段")
            return True

        except Exception as e:
            logger.error(f"修改 config 表失败: {e}", exc_info=True)
            return False

    def migrate(self) -> bool:
        """
        执行完整迁移流程

        Returns:
            成功返回 True
        """
        logger.info("=" * 50)
        logger.info("开始数据迁移...")

        # 1. 检查备份
        if not self.backup_path.exists():
            logger.error("未找到备份文件，请先运行 --backup")
            return False

        try:
            conn = self._get_connection()

            # 2. 创建 users 表
            if not self.create_users_table(conn):
                return False

            # 3. 创建默认管理员
            if not self.create_default_admin(conn):
                return False

            # 4. 重建 auth 表
            if not self.rebuild_auth_table(conn):
                return False

            # 5. 修改 ups 表
            if not self.alter_ups_table(conn):
                return False

            # 6. 修改 config 表
            if not self.alter_config_table(conn):
                return False

            conn.close()

            logger.info("=" * 50)
            logger.info("数据迁移完成！")
            logger.info(f"默认管理员: username={DEFAULT_ADMIN['username']}, password={DEFAULT_ADMIN['password']}")
            logger.info("请使用该账号登录Web后台")

            return True

        except Exception as e:
            logger.error(f"迁移失败: {e}", exc_info=True)
            return False

    def rollback(self) -> bool:
        """
        回滚到备份版本

        Returns:
            成功返回 True
        """
        logger.info("=" * 50)
        logger.info("开始回滚...")

        if not self.backup_path.exists():
            logger.error(f"备份文件不存在: {self.backup_path}")
            return False

        try:
            # 删除当前数据库
            if self.db_path.exists():
                self.db_path.unlink()
                logger.info(f"已删除当前数据库: {self.db_path}")

            # 恢复备份
            shutil.copy2(self.backup_path, self.db_path)
            logger.info(f"已恢复备份: {self.backup_path} -> {self.db_path}")

            logger.info("回滚完成！")
            return True

        except Exception as e:
            logger.error(f"回滚失败: {e}", exc_info=True)
            return False

    def verify(self) -> bool:
        """
        验证迁移结果

        Returns:
            成功返回 True
        """
        logger.info("=" * 50)
        logger.info("验证迁移结果...")

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 1. 检查 users 表
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            logger.info(f"users 表记录数: {user_count}")

            if user_count == 0:
                logger.error("users 表为空")
                return False

            # 2. 检查 auth 表结构
            cursor.execute("PRAGMA table_info(auth)")
            auth_columns = [row["name"] for row in cursor.fetchall()]

            if "user_id" not in auth_columns:
                logger.error("auth 表缺少 user_id 字段")
                return False

            logger.info(f"auth 表字段: {auth_columns}")

            # 3. 检查 ups 表结构
            cursor.execute("PRAGMA table_info(ups)")
            ups_columns = [row["name"] for row in cursor.fetchall()]

            if "user_id" not in ups_columns:
                logger.error("ups 表缺少 user_id 字段")
                return False

            logger.info(f"ups 表字段: {ups_columns}")

            # 4. 检查 config 表结构
            cursor.execute("PRAGMA table_info(config)")
            config_columns = [row["name"] for row in cursor.fetchall()]

            if "user_id" not in config_columns:
                logger.error("config 表缺少 user_id 字段")
                return False

            logger.info(f"config 表字段: {config_columns}")

            conn.close()

            logger.info("验证通过！")
            return True

        except Exception as e:
            logger.error(f"验证失败: {e}", exc_info=True)
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="多用户数据迁移脚本")

    parser.add_argument(
        "--backup",
        action="store_true",
        help="备份数据库"
    )

    parser.add_argument(
        "--migrate",
        action="store_true",
        help="执行迁移"
    )

    parser.add_argument(
        "--rollback",
        action="store_true",
        help="回滚到备份版本"
    )

    parser.add_argument(
        "--verify",
        action="store_true",
        help="验证迁移结果"
    )

    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="数据库路径（默认: data/monitor.db）"
    )

    args = parser.parse_args()

    migrator = MultiUserMigrator(db_path=args.db_path)

    if args.backup:
        success = migrator.backup()
        exit(0 if success else 1)

    elif args.migrate:
        success = migrator.migrate()
        if success:
            migrator.verify()
        exit(0 if success else 1)

    elif args.rollback:
        success = migrator.rollback()
        exit(0 if success else 1)

    elif args.verify:
        success = migrator.verify()
        exit(0 if success else 1)

    else:
        parser.print_help()
        exit(1)


if __name__ == "__main__":
    main()