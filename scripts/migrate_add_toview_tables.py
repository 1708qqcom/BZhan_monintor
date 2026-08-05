"""
数据库迁移脚本：添加稍后再看功能相关表

创建的表：
1. toview_videos - 稍后再看视频缓存表
2. toview_push_history - 推送历史表

执行方式：
python scripts/migrate_add_toview_tables.py
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import sqlite3
from src.database import Database


def migrate_add_toview_tables():
    """执行数据库迁移"""

    db_path = Path("data/monitor.db")

    if not db_path.exists():
        print("❌ 数据库文件不存在，请先运行主程序初始化数据库")
        return False

    print("开始迁移...")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # 检查表是否已存在
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='toview_videos'
        """)

        if cursor.fetchone():
            print("⚠️  toview_videos 表已存在，跳过创建")
        else:
            # 创建 toview_videos 表
            cursor.execute("""
                CREATE TABLE toview_videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    bvid TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    mid INTEGER,
                    pic TEXT,
                    play INTEGER DEFAULT 0,
                    duration TEXT,
                    pubdate INTEGER,
                    added_at INTEGER NOT NULL,
                    synced_at INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, bvid)
                )
            """)
            print("✓ toview_videos 表创建成功")

            # 创建索引
            cursor.execute("""
                CREATE INDEX idx_toview_user ON toview_videos(user_id)
            """)
            cursor.execute("""
                CREATE INDEX idx_toview_synced ON toview_videos(synced_at)
            """)
            print("✓ 索引创建成功")

        # 检查推送历史表
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='toview_push_history'
        """)

        if cursor.fetchone():
            print("⚠️  toview_push_history 表已存在，跳过创建")
        else:
            # 创建 toview_push_history 表
            cursor.execute("""
                CREATE TABLE toview_push_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    push_type TEXT NOT NULL,
                    pushed_at INTEGER NOT NULL,
                    video_count INTEGER NOT NULL,
                    video_list TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    pushed_by INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (pushed_by) REFERENCES users(id)
                )
            """)
            print("✓ toview_push_history 表创建成功")

            # 创建索引
            cursor.execute("""
                CREATE INDEX idx_toview_history_user ON toview_push_history(user_id)
            """)
            cursor.execute("""
                CREATE INDEX idx_toview_history_time ON toview_push_history(pushed_at)
            """)
            print("✓ 推送历史索引创建成功")

        conn.commit()
        print("\n✅ 迁移完成！")

        # 验证表结构
        print("\n验证表结构:")
        cursor.execute("PRAGMA table_info(toview_videos)")
        print("\ntoview_videos 表字段:")
        for row in cursor.fetchall():
            print(f"  - {row[1]} ({row[2]})")

        cursor.execute("PRAGMA table_info(toview_push_history)")
        print("\ntoview_push_history 表字段:")
        for row in cursor.fetchall():
            print(f"  - {row[1]} ({row[2]})")

        return True

    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    print("="*60)
    print("数据库迁移：添加稍后再看功能表")
    print("="*60 + "\n")

    success = migrate_add_toview_tables()

    if success:
        print("\n下一步：")
        print("1. 重启应用")
        print("2. 测试稍后再看功能")
        sys.exit(0)
    else:
        sys.exit(1)
