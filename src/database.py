"""
数据库管理模块

功能：
- SQLite 数据库连接管理（WAL 模式）
- UP主 CRUD 操作
- 视频历史 CRUD 操作
- 配置管理操作
- 登录信息操作

设计原则：
- 使用 WAL 模式支持并发读写
- 连接使用上下文管理器自动释放
- 所有操作带详细日志方便调试
"""
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("monitor.database")


class Database:
    """SQLite 数据库管理类"""

    def __init__(self, db_path: str = None):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径，默认为项目根目录下的 data/monitor.db
        """
        if db_path is None:
            # 默认使用项目根目录下的 data/monitor.db
            # src/database.py 的父目录的父目录就是项目根目录
            project_root = Path(__file__).parent.parent
            db_path = project_root / "data" / "monitor.db"
        self.db_path = Path(db_path)
        self._connection: Optional[sqlite3.Connection] = None

        logger.info(f"数据库管理器初始化: {self.db_path}")

    def init_db(self) -> None:
        """
        初始化数据库表结构

        创建以下表：
        - users: 用户表
        - ups: UP主表
        - videos: 视频历史表
        - config: 配置表
        - auth: 登录信息表
        """
        logger.info("开始初始化数据库表结构...")

        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"数据库目录已确认: {self.db_path.parent}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 0. 用户表（新增）
            logger.debug("创建 users 表...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    is_admin INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
            """)

            # 1. UP主表
            logger.debug("创建 ups 表...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mid INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    face TEXT,
                    user_id INTEGER DEFAULT 1,
                    is_monitoring INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ups_mid ON ups(mid)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ups_is_monitoring ON ups(is_monitoring)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ups_user_id ON ups(user_id)
            """)

            # 2. 视频历史表
            logger.debug("创建 videos 表...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    up_id INTEGER NOT NULL,
                    bvid TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT,
                    pub_time TEXT,
                    view_count INTEGER DEFAULT 0,
                    pushed INTEGER DEFAULT 0,
                    pushed_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (up_id) REFERENCES ups(id)
                )
            """)
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_videos_bvid ON videos(bvid)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_videos_up_id ON videos(up_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_videos_pushed ON videos(pushed)
            """)

            # 3. 配置表
            logger.debug("创建 config 表...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    user_id INTEGER,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_config_user_id ON config(user_id)
            """)

            # 4. 登录信息表（支持多用户）
            logger.debug("创建 auth 表...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auth (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    cookies TEXT,
                    created_at TEXT,
                    expires_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_user_id ON auth(user_id)
            """)

            # 5. 推送历史表
            logger.debug("创建 push_history 表...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS push_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL,
                    pushed_at TEXT NOT NULL,
                    push_type TEXT NOT NULL DEFAULT 'manual',
                    success INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (video_id) REFERENCES videos(id)
                )
            """)
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_push_history_video_id
                ON push_history(video_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_push_history_pushed_at
                ON push_history(pushed_at)
            """)

            # 6. 稍后再看视频缓存表
            logger.debug("创建 toview_videos 表...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS toview_videos (
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
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_toview_user ON toview_videos(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_toview_synced ON toview_videos(synced_at)
            """)

            # 7. 稍后再看推送历史表
            logger.debug("创建 toview_push_history 表...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS toview_push_history (
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
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_toview_history_user ON toview_push_history(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_toview_history_time ON toview_push_history(pushed_at)
            """)

            conn.commit()
            logger.info("数据库表结构初始化完成")

    @contextmanager
    def _get_connection(self):
        """
        获取数据库连接（上下文管理器）

        Yields:
            sqlite3.Connection: 数据库连接对象

        使用示例：
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM ups")
        """
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path))
            # 启用 WAL 模式（支持并发读写）
            conn.execute("PRAGMA journal_mode=WAL")
            # 外键约束
            conn.execute("PRAGMA foreign_keys=ON")
            # 返回字典格式结果
            conn.row_factory = sqlite3.Row

            logger.debug(f"数据库连接已建立: {self.db_path}")
            yield conn

        except sqlite3.Error as e:
            logger.error(f"数据库连接失败: {e}")
            raise
        finally:
            if conn:
                conn.close()
                logger.debug("数据库连接已关闭")

    # ==================== UP主 CRUD ====================

    def get_ups(
        self,
        user_id: int = None,
        is_monitoring: Optional[bool] = None,
        page: Optional[int] = None,
        page_size: int = 20,
        keyword: Optional[str] = None,
    ) -> list[dict]:
        """
        查询 UP主列表（支持分页和搜索）

        Args:
            user_id: 用户 ID，None 表示查询所有（管理员用）
            is_monitoring: 是否监控中，None 表示全部
            page: 页码（从1开始），None 表示不分页返回全部
            page_size: 每页数量，默认 20
            keyword: 搜索关键词（匹配 name 或 mid）

        Returns:
            UP主列表 [{"id": 1, "mid": 123, "name": "名字", ...}, ...]
        """
        logger.debug(
            f"查询 UP主列表: user_id={user_id}, is_monitoring={is_monitoring}, "
            f"page={page}, page_size={page_size}, keyword={keyword}"
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 构造 WHERE 条件
            conditions = []
            params = []

            if user_id is not None:
                conditions.append("user_id = ?")
                params.append(user_id)

            if is_monitoring is not None:
                conditions.append("is_monitoring = ?")
                params.append(1 if is_monitoring else 0)

            if keyword:
                # 搜索 name 或 mid
                conditions.append("(name LIKE ? OR CAST(mid AS TEXT) LIKE ?)")
                search_pattern = f"%{keyword}%"
                params.extend([search_pattern, search_pattern])

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            # 构造分页
            if page is not None:
                offset = (page - 1) * page_size
                pagination_clause = f"LIMIT ? OFFSET ?"
                params.extend([page_size, offset])
            else:
                pagination_clause = ""

            sql = f"""
                SELECT id, mid, name, face, user_id, is_monitoring, created_at, updated_at
                FROM ups
                WHERE {where_clause}
                ORDER BY created_at DESC
                {pagination_clause}
            """

            cursor.execute(sql, params)
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]

            logger.info(f"查询到 {len(result)} 个 UP主")
            return result

    def get_ups_count(
        self,
        user_id: int = None,
        is_monitoring: Optional[bool] = None,
        keyword: Optional[str] = None,
    ) -> int:
        """
        查询 UP主总数（用于分页）

        Args:
            user_id: 用户 ID，None 表示查询所有（管理员用）
            is_monitoring: 是否监控中，None 表示全部
            keyword: 搜索关键词（匹配 name 或 mid）

        Returns:
            符合条件的 UP主总数
        """
        logger.debug(
            f"查询 UP主总数: user_id={user_id}, is_monitoring={is_monitoring}, keyword={keyword}"
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 构造 WHERE 条件（与 get_ups 一致）
            conditions = []
            params = []

            if user_id is not None:
                conditions.append("user_id = ?")
                params.append(user_id)

            if is_monitoring is not None:
                conditions.append("is_monitoring = ?")
                params.append(1 if is_monitoring else 0)

            if keyword:
                conditions.append("(name LIKE ? OR CAST(mid AS TEXT) LIKE ?)")
                search_pattern = f"%{keyword}%"
                params.extend([search_pattern, search_pattern])

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            sql = f"SELECT COUNT(*) FROM ups WHERE {where_clause}"
            cursor.execute(sql, params)
            total = cursor.fetchone()[0]

            logger.debug(f"UP主总数: {total}")
            return total

    def get_up_by_mid(self, mid: int, user_id: int = None) -> Optional[dict]:
        """
        按 mid 查询 UP主

        Args:
            mid: B站 UP主 ID
            user_id: 用户 ID，None 表示查询所有用户

        Returns:
            UP主信息字典，不存在返回 None
        """
        logger.debug(f"查询 UP主: mid={mid}, user_id={user_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if user_id is None:
                cursor.execute("""
                    SELECT id, mid, name, face, user_id, is_monitoring, created_at, updated_at
                    FROM ups
                    WHERE mid = ?
                """, (mid,))
            else:
                cursor.execute("""
                    SELECT id, mid, name, face, user_id, is_monitoring, created_at, updated_at
                    FROM ups
                    WHERE mid = ? AND user_id = ?
                """, (mid, user_id))

            row = cursor.fetchone()
            if row:
                logger.debug(f"找到 UP主: {dict(row)}")
                return dict(row)
            else:
                logger.debug(f"未找到 UP主: mid={mid}")
                return None

    def add_up(self, mid: int, name: str, face: str = "", user_id: int = None) -> int:
        """
        添加 UP主

        Args:
            mid: B站 UP主 ID
            name: UP主名称
            face: 头像 URL
            user_id: 用户 ID

        Returns:
            新记录的 id

        Raises:
            sqlite3.IntegrityError: mid 已存在（同一用户）
        """
        logger.info(f"添加 UP主: mid={mid}, name={name}, user_id={user_id}")

        now = datetime.now().isoformat()

        # 如果未指定 user_id，使用默认用户（id=1）
        if user_id is None:
            user_id = 1

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO ups (mid, name, face, user_id, is_monitoring, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                """, (mid, name, face, user_id, now, now))

                conn.commit()
                up_id = cursor.lastrowid

                logger.info(f"UP主添加成功: id={up_id}, mid={mid}, name={name}, user_id={user_id}")
                return up_id

            except sqlite3.IntegrityError:
                logger.warning(f"UP主已存在: mid={mid}, user_id={user_id}")
                raise

    def remove_up(self, up_id: int, user_id: int = None) -> bool:
        """
        删除 UP主（验证归属）

        Args:
            up_id: UP主记录 ID
            user_id: 用户 ID，用于验证归属（None 表示管理员删除）

        Returns:
            成功返回 True
        """
        logger.info(f"删除 UP主: up_id={up_id}, user_id={user_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. 验证归属（如果指定了 user_id）
            if user_id is not None:
                cursor.execute("SELECT user_id FROM ups WHERE id = ?", (up_id,))
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"UP主不存在: up_id={up_id}")
                    return False
                if row["user_id"] != user_id:
                    logger.warning(f"无权删除 UP主: up_id={up_id}, user_id={user_id}")
                    return False

            # 2. 删除关联的视频记录
            cursor.execute("DELETE FROM videos WHERE up_id = ?", (up_id,))
            videos_deleted = cursor.rowcount
            logger.info(f"删除关联视频: {videos_deleted} 条")

            # 3. 删除 UP主记录
            cursor.execute("DELETE FROM ups WHERE id = ?", (up_id,))
            conn.commit()
            affected = cursor.rowcount

            if affected > 0:
                logger.info(f"UP主已删除: up_id={up_id}, 关联视频: {videos_deleted} 条")
                return True
            else:
                logger.warning(f"未找到 UP主: up_id={up_id}")
                return False

    # ==================== 视频历史 CRUD ====================

    def get_videos(
        self,
        page: int = 1,
        page_size: int = 20,
        up_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> dict:
        """
        分页查询视频历史

        Args:
            page: 页码（从1开始）
            page_size: 每页数量
            up_id: 按 UP主筛选
            date_from: 开始日期 (YYYY-MM-DD)
            date_to: 结束日期 (YYYY-MM-DD)
            user_id: 用户 ID，用于筛选用户的视频（管理员用）

        Returns:
            {
                "items": [...],
                "total": 总数,
                "page": 当前页,
                "page_size": 每页数量
            }
        """
        logger.debug(
            f"查询视频历史: page={page}, page_size={page_size}, "
            f"up_id={up_id}, date_from={date_from}, date_to={date_to}, user_id={user_id}"
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 构造 WHERE 条件
            conditions = []
            params = []

            if up_id is not None:
                conditions.append("v.up_id = ?")
                params.append(up_id)

            if user_id is not None:
                # 通过 ups 表关联过滤用户
                conditions.append("u.user_id = ?")
                params.append(user_id)

            if date_from:
                conditions.append("DATE(v.pushed_at) >= ?")
                params.append(date_from)

            if date_to:
                conditions.append("DATE(v.pushed_at) <= ?")
                params.append(date_to)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            # 查询总数
            count_sql = f"""
                SELECT COUNT(*)
                FROM videos v
                LEFT JOIN ups u ON v.up_id = u.id
                WHERE {where_clause}
            """
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            # 分页查询
            offset = (page - 1) * page_size
            query_sql = f"""
                SELECT
                    v.id, v.up_id, v.bvid, v.title, v.url, v.pub_time,
                    v.view_count, v.pushed, v.pushed_at, v.created_at,
                    u.name as up_name, u.face as up_face, u.user_id
                FROM videos v
                LEFT JOIN ups u ON v.up_id = u.id
                WHERE {where_clause}
                ORDER BY v.pushed_at DESC
                LIMIT ? OFFSET ?
            """
            cursor.execute(query_sql, params + [page_size, offset])

            rows = cursor.fetchall()
            items = [dict(row) for row in rows]

            logger.info(f"查询到 {len(items)} 条视频记录，总计 {total} 条")

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    def get_video_by_bvid(self, bvid: str) -> Optional[dict]:
        """
        按 BV号 查询视频

        Args:
            bvid: 视频BV号

        Returns:
            视频信息字典，不存在返回 None
        """
        logger.debug(f"查询视频: bvid={bvid}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, up_id, bvid, title, url, pub_time,
                       view_count, pushed, pushed_at, created_at
                FROM videos
                WHERE bvid = ?
            """, (bvid,))

            row = cursor.fetchone()
            if row:
                logger.debug(f"找到视频: {dict(row)}")
                return dict(row)
            else:
                logger.debug(f"未找到视频: bvid={bvid}")
                return None

    def add_video(
        self,
        up_id: int,
        bvid: str,
        title: str,
        url: str = "",
        pub_time: Optional[str] = None,
        view_count: int = 0,
        pushed: bool = False,
        pushed_at: Optional[str] = None,
    ) -> int:
        """
        添加视频记录

        Args:
            up_id: UP主 ID
            bvid: 视频BV号
            title: 视频标题
            url: 视频链接
            pub_time: 发布时间
            view_count: 播放量
            pushed: 是否已推送
            pushed_at: 推送时间

        Returns:
            新记录的 id

        Raises:
            sqlite3.IntegrityError: bvid 已存在
        """
        logger.info(f"添加视频记录: bvid={bvid}, title={title}")

        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO videos
                    (up_id, bvid, title, url, pub_time, view_count, pushed, pushed_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    up_id, bvid, title, url, pub_time, view_count,
                    1 if pushed else 0, pushed_at, now
                ))

                conn.commit()
                video_id = cursor.lastrowid

                logger.info(f"视频记录添加成功: id={video_id}, bvid={bvid}")
                return video_id

            except sqlite3.IntegrityError:
                logger.warning(f"视频已存在: bvid={bvid}")
                raise

    def update_video_pushed(self, bvid: str, pushed: bool = True) -> bool:
        """
        更新视频推送状态

        Args:
            bvid: 视频BV号
            pushed: 是否已推送

        Returns:
            成功返回 True
        """
        logger.debug(f"更新视频推送状态: bvid={bvid}, pushed={pushed}")

        pushed_at = datetime.now().isoformat() if pushed else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE videos
                SET pushed = ?, pushed_at = ?
                WHERE bvid = ?
            """, (1 if pushed else 0, pushed_at, bvid))

            conn.commit()
            affected = cursor.rowcount

            if affected > 0:
                logger.debug(f"视频推送状态已更新: bvid={bvid}")
                return True
            else:
                logger.warning(f"未找到视频: bvid={bvid}")
                return False

    def update_video(self, bvid: str, video_data: dict) -> bool:
        """
        更新视频信息

        Args:
            bvid: 视频BV号
            video_data: 要更新的字段字典，可包含：
                - title: 标题
                - url: 链接
                - pub_time: 发布时间
                - view_count: 播放量

        Returns:
            成功返回 True
        """
        logger.info(f"更新视频信息: bvid={bvid}, fields={list(video_data.keys())}")

        if not video_data:
            logger.warning("更新字段为空，跳过")
            return False

        # 构造动态更新语句
        set_clauses = []
        params = []
        allowed_fields = {"title", "url", "pub_time", "view_count"}

        for field, value in video_data.items():
            if field in allowed_fields:
                set_clauses.append(f"{field} = ?")
                params.append(value)

        if not set_clauses:
            logger.warning("无有效更新字段")
            return False

        params.append(bvid)
        sql = f"UPDATE videos SET {', '.join(set_clauses)} WHERE bvid = ?"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            affected = cursor.rowcount

            if affected > 0:
                logger.info(f"视频信息已更新: bvid={bvid}")
                return True
            else:
                logger.warning(f"未找到视频: bvid={bvid}")
                return False

    # ==================== 推送历史 CRUD ====================

    def add_push_history(
        self,
        video_id: int,
        push_type: str = "manual",
        success: bool = False,
        error_message: str = None,
    ) -> int:
        """
        添加推送历史记录

        Args:
            video_id: 视频ID
            push_type: 推送类型（manual/auto）
            success: 是否成功
            error_message: 错误信息（失败时记录）

        Returns:
            新记录的 id
        """
        logger.info(
            f"添加推送历史: video_id={video_id}, "
            f"type={push_type}, success={success}"
        )

        now = datetime.now().isoformat()
        pushed_at = now

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO push_history
                (video_id, pushed_at, push_type, success, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                video_id, pushed_at, push_type,
                1 if success else 0, error_message, now
            ))

            conn.commit()
            history_id = cursor.lastrowid

            logger.info(f"推送历史记录添加成功: id={history_id}")
            return history_id

    def get_push_history(self, video_id: int, limit: int = 10) -> list[dict]:
        """
        获取视频的推送历史

        Args:
            video_id: 视频ID
            limit: 返回数量限制

        Returns:
            推送历史列表
        """
        logger.debug(f"查询推送历史: video_id={video_id}, limit={limit}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, video_id, pushed_at, push_type, success, error_message, created_at
                FROM push_history
                WHERE video_id = ?
                ORDER BY pushed_at DESC
                LIMIT ?
            """, (video_id, limit))

            rows = cursor.fetchall()
            result = [dict(row) for row in rows]

            logger.debug(f"查询到 {len(result)} 条推送历史")
            return result

    # ==================== 配置管理 ====================

    def get_config(self, user_id: int = None) -> dict:
        """
        获取配置（合并全局配置和用户配置）

        Args:
            user_id: 用户ID，用于获取用户级别的配置

        Returns:
            配置字典 {"key": "value", ...}
        """
        logger.debug(f"查询配置: user_id={user_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. 获取全局配置（user_id 为 NULL）
            cursor.execute("""
                SELECT key, value FROM config WHERE user_id IS NULL
            """)
            global_rows = cursor.fetchall()
            config = {row["key"]: row["value"] for row in global_rows}

            # 2. 获取用户配置（如果有 user_id）
            if user_id is not None:
                cursor.execute("""
                    SELECT key, value FROM config WHERE user_id = ?
                """, (user_id,))
                user_rows = cursor.fetchall()
                # 用户配置覆盖全局配置
                for row in user_rows:
                    config[row["key"]] = row["value"]

            logger.debug(f"查询到 {len(config)} 项配置")
            return config

    def get_config_value(self, key: str, default: str = None, user_id: int = None) -> Optional[str]:
        """
        获取单个配置值

        Args:
            key: 配置键
            default: 默认值
            user_id: 用户ID（优先获取用户配置，回退到全局配置）

        Returns:
            配置值，不存在返回 default
        """
        logger.debug(f"查询配置: key={key}, user_id={user_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 优先查询用户配置
            if user_id is not None:
                cursor.execute("""
                    SELECT value FROM config WHERE key = ? AND user_id = ?
                """, (key, user_id))
                row = cursor.fetchone()
                if row:
                    logger.debug(f"配置值(用户): {key}={row['value']}")
                    return row["value"]

            # 回退到全局配置
            cursor.execute("""
                SELECT value FROM config WHERE key = ? AND user_id IS NULL
            """, (key,))
            row = cursor.fetchone()
            if row:
                logger.debug(f"配置值(全局): {key}={row['value']}")
                return row["value"]

            logger.debug(f"配置不存在: key={key}, 使用默认值={default}")
            return default

    def update_config(self, key: str, value: str, user_id: int = None) -> None:
        """
        更新配置

        Args:
            key: 配置键
            value: 配置值
            user_id: 用户ID（None 表示全局配置）
        """
        logger.info(f"更新配置: key={key}, user_id={user_id}")

        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if user_id is None:
                # 更新全局配置
                cursor.execute("""
                    INSERT OR REPLACE INTO config (key, value, user_id, updated_at)
                    VALUES (?, ?, NULL, ?)
                """, (key, value, now))
            else:
                # 更新用户配置
                cursor.execute("""
                    INSERT OR REPLACE INTO config (key, value, user_id, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (key, value, user_id, now))

            conn.commit()
            logger.info(f"配置已更新: key={key}, user_id={user_id}")

    # ==================== 登录信息管理 ====================

    def get_auth(self, user_id: int = None) -> Optional[dict]:
        """
        获取登录信息

        Args:
            user_id: 用户 ID，None 表示获取第一条记录（兼容旧逻辑）

        Returns:
            {"cookies": dict, "created_at": str, "expires_at": str} 或 None
        """
        logger.debug(f"查询登录信息: user_id={user_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if user_id is None:
                # 兼容旧逻辑：获取第一条记录
                cursor.execute("""
                    SELECT user_id, cookies, created_at, expires_at
                    FROM auth
                    LIMIT 1
                """)
            else:
                cursor.execute("""
                    SELECT user_id, cookies, created_at, expires_at
                    FROM auth
                    WHERE user_id = ?
                """, (user_id,))

            row = cursor.fetchone()
            if row and row["cookies"]:
                cookies_dict = json.loads(row["cookies"])
                result = {
                    "user_id": row["user_id"],
                    "cookies": cookies_dict,
                    "created_at": row["created_at"],
                    "expires_at": row["expires_at"],
                }
                logger.debug("找到登录信息")
                return result
            else:
                logger.debug("未找到登录信息")
                return None

    def save_auth(self, cookies: dict, expires_at: Optional[str] = None, user_id: int = None) -> None:
        """
        保存登录信息

        Args:
            cookies: Cookie 字典
            expires_at: 过期时间
            user_id: 用户 ID
        """
        logger.info(f"保存登录信息: user_id={user_id}")

        now = datetime.now().isoformat()
        cookies_json = json.dumps(cookies, ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if user_id is None:
                # 兼容旧逻辑：更新第一条记录
                cursor.execute("""
                    UPDATE auth
                    SET cookies = ?, created_at = ?, expires_at = ?
                    WHERE id = (SELECT MIN(id) FROM auth)
                """, (cookies_json, now, expires_at))
            else:
                # 插入或更新用户登录信息
                cursor.execute("""
                    INSERT OR REPLACE INTO auth (user_id, cookies, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                """, (user_id, cookies_json, now, expires_at))

            conn.commit()
            logger.info(f"登录信息已保存: user_id={user_id}")

    def clear_auth(self, user_id: int = None) -> None:
        """
        清除登录信息

        Args:
            user_id: 用户 ID，None 表示清除第一条记录（兼容旧逻辑）
        """
        logger.info(f"清除登录信息: user_id={user_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if user_id is None:
                # 兼容旧逻辑：清除第一条记录
                cursor.execute("""
                    DELETE FROM auth WHERE id = (SELECT MIN(id) FROM auth)
                """)
            else:
                cursor.execute("DELETE FROM auth WHERE user_id = ?", (user_id,))

            conn.commit()
            logger.info(f"登录信息已清除: user_id={user_id}")

    # ==================== 用户管理 ====================

    def create_users_table(self) -> None:
        """
        创建 users 表（新用户首次启动时自动创建）
        """
        logger.debug("创建 users 表...")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 创建 users 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
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
            logger.debug("users 表创建完成")

    def add_user(self, username: str, password: str, is_admin: bool = False) -> int:
        """
        添加用户

        Args:
            username: 用户名
            password: 密码
            is_admin: 是否管理员

        Returns:
            新用户的 id

        Raises:
            sqlite3.IntegrityError: 用户名已存在
        """
        logger.info(f"添加用户: username={username}, is_admin={is_admin}")

        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO users (username, password, is_admin, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, password, 1 if is_admin else 0, now, now))

                conn.commit()
                user_id = cursor.lastrowid

                logger.info(f"用户添加成功: id={user_id}, username={username}")
                return user_id

            except sqlite3.IntegrityError:
                logger.warning(f"用户名已存在: username={username}")
                raise

    def get_user_by_username(self, username: str) -> Optional[dict]:
        """
        按用户名查询用户

        Args:
            username: 用户名

        Returns:
            用户信息字典，不存在返回 None
        """
        logger.debug(f"查询用户: username={username}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, password, is_admin, created_at, updated_at
                FROM users
                WHERE username = ?
            """, (username,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            else:
                logger.debug(f"用户不存在: username={username}")
                return None

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """
        按 ID 查询用户

        Args:
            user_id: 用户 ID

        Returns:
            用户信息字典，不存在返回 None
        """
        logger.debug(f"查询用户: user_id={user_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, password, is_admin, created_at, updated_at
                FROM users
                WHERE id = ?
            """, (user_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            else:
                logger.debug(f"用户不存在: user_id={user_id}")
                return None

    def get_all_users(self) -> list[dict]:
        """
        获取所有用户列表（管理员用）

        Returns:
            用户列表
        """
        logger.debug("查询所有用户")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, is_admin, created_at, updated_at
                FROM users
                ORDER BY created_at DESC
            """)

            rows = cursor.fetchall()
            result = [dict(row) for row in rows]

            logger.info(f"查询到 {len(result)} 个用户")
            return result

    def delete_user(self, user_id: int) -> bool:
        """
        删除用户（级联删除关联数据）

        Args:
            user_id: 用户 ID

        Returns:
            成功返回 True
        """
        logger.info(f"删除用户: user_id={user_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # SQLite 外键级联会自动删除关联数据
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            affected = cursor.rowcount

            if affected > 0:
                logger.info(f"用户已删除: user_id={user_id}")
                return True
            else:
                logger.warning(f"用户不存在: user_id={user_id}")
                return False

    def get_all_users_with_valid_auth(self) -> list[dict]:
        """
        获取所有有效 B站登录的用户（监控线程用）

        Returns:
            用户列表，包含 id, username, cookies, expires_at
        """
        logger.debug("查询所有有效 B站登录的用户")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    u.id, u.username, u.is_admin,
                    a.cookies, a.expires_at
                FROM users u
                INNER JOIN auth a ON u.id = a.user_id
                WHERE a.cookies IS NOT NULL
            """)

            rows = cursor.fetchall()
            result = []
            for row in rows:
                user_data = dict(row)
                if user_data.get("cookies"):
                    user_data["cookies"] = json.loads(user_data["cookies"])
                result.append(user_data)

            logger.info(f"查询到 {len(result)} 个有效 B站登录用户")
            return result

    def user_exists(self) -> bool:
        """
        检查是否存在任何用户

        Returns:
            存在返回 True
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            return count > 0

    # ==================== 稍后再看视频管理 ====================

    def save_toview_videos(self, user_id: int, videos: list[dict]) -> int:
        """
        保存稍后再看视频列表

        Args:
            user_id: 用户 ID
            videos: 视频列表，每个元素包含 bvid, title, author, mid, pic, play, duration, pubdate

        Returns:
            保存的视频数量

        Raises:
            sqlite3.Error: 数据库操作失败
        """
        if not videos:
            logger.debug("视频列表为空，跳过保存")
            return 0

        logger.info(f"保存稍后再看视频: user_id={user_id}, count={len(videos)}")

        now = int(datetime.now().timestamp())
        saved_count = 0

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for video in videos:
                bvid = video.get("bvid")
                if not bvid:
                    logger.warning(f"视频缺少 bvid: {video}")
                    continue

                try:
                    # 使用 INSERT OR REPLACE 实现更新或插入
                    cursor.execute("""
                        INSERT OR REPLACE INTO toview_videos
                        (user_id, bvid, title, author, mid, pic, play, duration, pubdate, added_at, synced_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user_id,
                        bvid,
                        video.get("title", ""),
                        video.get("author"),
                        video.get("mid"),
                        video.get("pic"),
                        video.get("play", 0),
                        video.get("duration"),
                        video.get("pubdate"),
                        video.get("added_at", now),
                        now
                    ))
                    saved_count += 1

                except sqlite3.Error as e:
                    logger.error(f"保存视频失败: bvid={bvid}, error={e}")
                    continue

            conn.commit()

        logger.info(f"稍后再看视频保存成功: user_id={user_id}, saved={saved_count}")
        return saved_count

    def get_toview_videos(self, user_id: int, limit: int = 30) -> list[dict]:
        """
        获取用户的稍后再看视频列表

        Args:
            user_id: 用户 ID
            limit: 返回数量限制

        Returns:
            视频列表，按添加时间倒序排列
        """
        logger.debug(f"查询稍后再看视频: user_id={user_id}, limit={limit}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, bvid, title, author, mid, pic, play, duration, pubdate, added_at, synced_at
                FROM toview_videos
                WHERE user_id = ?
                ORDER BY added_at DESC
                LIMIT ?
            """, (user_id, limit))

            rows = cursor.fetchall()
            result = [dict(row) for row in rows]

            logger.info(f"查询到 {len(result)} 条稍后再看视频")
            return result

    def get_all_toview_videos(self, user_id: Optional[int] = None) -> list[dict]:
        """
        获取所有用户的稍后再看视频（管理员用）

        Args:
            user_id: 可选，筛选指定用户

        Returns:
            分用户的视频列表，每个元素包含 user_id, username, count, videos
        """
        logger.debug(f"查询所有用户稍后再看视频: user_id={user_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if user_id is not None:
                # 查询指定用户
                cursor.execute("""
                    SELECT
                        u.id as user_id,
                        u.username,
                        COUNT(tv.id) as count
                    FROM users u
                    LEFT JOIN toview_videos tv ON u.id = tv.user_id
                    WHERE u.id = ?
                    GROUP BY u.id
                """, (user_id,))
            else:
                # 查询所有用户
                cursor.execute("""
                    SELECT
                        u.id as user_id,
                        u.username,
                        COUNT(tv.id) as count
                    FROM users u
                    LEFT JOIN toview_videos tv ON u.id = tv.user_id
                    GROUP BY u.id
                """)

            user_rows = cursor.fetchall()

            result = []
            for user_row in user_rows:
                user_data = dict(user_row)

                # 查询该用户的视频列表
                cursor.execute("""
                    SELECT bvid, title, author, mid, pic, play, duration, pubdate, added_at
                    FROM toview_videos
                    WHERE user_id = ?
                    ORDER BY added_at DESC
                    LIMIT 10
                """, (user_data["user_id"],))

                video_rows = cursor.fetchall()
                user_data["videos"] = [dict(row) for row in video_rows]
                result.append(user_data)

            logger.info(f"查询到 {len(result)} 个用户的稍后再看数据")
            return result

    def save_toview_push_history(
        self,
        user_id: int,
        push_type: str,
        videos: list[dict],
        success: bool,
        error_message: str = None,
        pushed_by: int = None
    ) -> int:
        """
        保存稍后再看推送历史

        Args:
            user_id: 用户 ID
            push_type: 推送类型（'auto' 或 'manual'）
            videos: 推送的视频列表
            success: 是否成功
            error_message: 错误信息（失败时记录）
            pushed_by: 手动推送的操作人 ID（管理员）

        Returns:
            新记录的 id
        """
        logger.info(
            f"保存推送历史: user_id={user_id}, type={push_type}, "
            f"success={success}, video_count={len(videos)}"
        )

        now = int(datetime.now().timestamp())
        video_list_json = json.dumps(videos, ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO toview_push_history
                (user_id, push_type, pushed_at, video_count, video_list, success, error_message, pushed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                push_type,
                now,
                len(videos),
                video_list_json,
                1 if success else 0,
                error_message,
                pushed_by
            ))

            conn.commit()
            history_id = cursor.lastrowid

            logger.info(f"推送历史保存成功: id={history_id}")
            return history_id

    def get_toview_push_history(
        self,
        user_id: Optional[int] = None,
        limit: int = 100
    ) -> list[dict]:
        """
        获取推送历史

        Args:
            user_id: 用户 ID（None 表示查询所有）
            limit: 返回数量限制

        Returns:
            推送历史列表，按推送时间倒序排列
        """
        logger.debug(f"查询推送历史: user_id={user_id}, limit={limit}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if user_id is not None:
                cursor.execute("""
                    SELECT
                        tph.id, tph.user_id, tph.push_type, tph.pushed_at,
                        tph.video_count, tph.video_list, tph.success, tph.error_message,
                        tph.pushed_by, u.username as pushed_by_name
                    FROM toview_push_history tph
                    LEFT JOIN users u ON tph.pushed_by = u.id
                    WHERE tph.user_id = ?
                    ORDER BY tph.pushed_at DESC
                    LIMIT ?
                """, (user_id, limit))
            else:
                cursor.execute("""
                    SELECT
                        tph.id, tph.user_id, tph.push_type, tph.pushed_at,
                        tph.video_count, tph.video_list, tph.success, tph.error_message,
                        tph.pushed_by, u.username as pushed_by_name
                    FROM toview_push_history tph
                    LEFT JOIN users u ON tph.pushed_by = u.id
                    ORDER BY tph.pushed_at DESC
                    LIMIT ?
                """, (limit,))

            rows = cursor.fetchall()
            result = []

            for row in rows:
                history = dict(row)
                # 解析视频列表 JSON
                if history.get("video_list"):
                    try:
                        history["video_list"] = json.loads(history["video_list"])
                    except json.JSONDecodeError:
                        history["video_list"] = []
                result.append(history)

            logger.info(f"查询到 {len(result)} 条推送历史")
            return result
