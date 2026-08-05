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

            # 1. UP主表
            logger.debug("创建 ups 表...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mid INTEGER UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    face TEXT,
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
                    updated_at TEXT NOT NULL
                )
            """)

            # 4. 登录信息表
            logger.debug("创建 auth 表...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auth (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    cookies TEXT,
                    created_at TEXT,
                    expires_at TEXT
                )
            """)
            # 初始化 auth 表的默认记录
            cursor.execute("""
                INSERT OR IGNORE INTO auth (id, cookies, created_at, expires_at)
                VALUES (1, NULL, NULL, NULL)
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

    def get_ups(self, is_monitoring: Optional[bool] = None) -> list[dict]:
        """
        查询 UP主列表

        Args:
            is_monitoring: 是否监控中，None 表示全部

        Returns:
            UP主列表 [{"id": 1, "mid": 123, "name": "名字", ...}, ...]
        """
        logger.debug(f"查询 UP主列表: is_monitoring={is_monitoring}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if is_monitoring is None:
                cursor.execute("""
                    SELECT id, mid, name, face, is_monitoring, created_at, updated_at
                    FROM ups
                    ORDER BY created_at DESC
                """)
            else:
                cursor.execute("""
                    SELECT id, mid, name, face, is_monitoring, created_at, updated_at
                    FROM ups
                    WHERE is_monitoring = ?
                    ORDER BY created_at DESC
                """, (1 if is_monitoring else 0,))

            rows = cursor.fetchall()
            result = [dict(row) for row in rows]

            logger.info(f"查询到 {len(result)} 个 UP主")
            return result

    def get_up_by_mid(self, mid: int) -> Optional[dict]:
        """
        按 mid 查询 UP主

        Args:
            mid: B站 UP主 ID

        Returns:
            UP主信息字典，不存在返回 None
        """
        logger.debug(f"查询 UP主: mid={mid}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, mid, name, face, is_monitoring, created_at, updated_at
                FROM ups
                WHERE mid = ?
            """, (mid,))

            row = cursor.fetchone()
            if row:
                logger.debug(f"找到 UP主: {dict(row)}")
                return dict(row)
            else:
                logger.debug(f"未找到 UP主: mid={mid}")
                return None

    def add_up(self, mid: int, name: str, face: str = "") -> int:
        """
        添加 UP主

        Args:
            mid: B站 UP主 ID
            name: UP主名称
            face: 头像 URL

        Returns:
            新记录的 id

        Raises:
            sqlite3.IntegrityError: mid 已存在
        """
        logger.info(f"添加 UP主: mid={mid}, name={name}")

        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO ups (mid, name, face, is_monitoring, created_at, updated_at)
                    VALUES (?, ?, ?, 1, ?, ?)
                """, (mid, name, face, now, now))

                conn.commit()
                up_id = cursor.lastrowid

                logger.info(f"UP主添加成功: id={up_id}, mid={mid}, name={name}")
                return up_id

            except sqlite3.IntegrityError:
                logger.warning(f"UP主已存在: mid={mid}")
                raise

    def remove_up(self, up_id: int) -> bool:
        """
        删除 UP主（真删除，一并删除关联的视频记录）

        Args:
            up_id: UP主记录 ID

        Returns:
            成功返回 True
        """
        logger.info(f"删除 UP主: up_id={up_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. 先删除关联的视频记录
            cursor.execute("DELETE FROM videos WHERE up_id = ?", (up_id,))
            videos_deleted = cursor.rowcount
            logger.info(f"删除关联视频: {videos_deleted} 条")

            # 2. 再删除 UP主记录
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
    ) -> dict:
        """
        分页查询视频历史

        Args:
            page: 页码（从1开始）
            page_size: 每页数量
            up_id: 按 UP主筛选
            date_from: 开始日期 (YYYY-MM-DD)
            date_to: 结束日期 (YYYY-MM-DD)

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
            f"up_id={up_id}, date_from={date_from}, date_to={date_to}"
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 构造 WHERE 条件
            conditions = []
            params = []

            if up_id is not None:
                conditions.append("v.up_id = ?")
                params.append(up_id)

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
                    u.name as up_name, u.face as up_face
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

    def get_config(self) -> dict:
        """
        获取所有配置

        Returns:
            配置字典 {"key": "value", ...}
        """
        logger.debug("查询所有配置")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT key, value FROM config
            """)

            rows = cursor.fetchall()
            config = {row["key"]: row["value"] for row in rows}

            logger.debug(f"查询到 {len(config)} 项配置")
            return config

    def get_config_value(self, key: str, default: str = None) -> Optional[str]:
        """
        获取单个配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值，不存在返回 default
        """
        logger.debug(f"查询配置: key={key}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT value FROM config WHERE key = ?
            """, (key,))

            row = cursor.fetchone()
            if row:
                logger.debug(f"配置值: {key}={row['value']}")
                return row["value"]
            else:
                logger.debug(f"配置不存在: key={key}, 使用默认值={default}")
                return default

    def update_config(self, key: str, value: str) -> None:
        """
        更新配置

        Args:
            key: 配置键
            value: 配置值
        """
        logger.info(f"更新配置: {key}={value}")

        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO config (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, now))

            conn.commit()
            logger.info(f"配置已更新: {key}={value}")

    # ==================== 登录信息管理 ====================

    def get_auth(self) -> Optional[dict]:
        """
        获取登录信息

        Returns:
            {"cookies": dict, "created_at": str, "expires_at": str} 或 None
        """
        logger.debug("查询登录信息")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cookies, created_at, expires_at
                FROM auth
                WHERE id = 1
            """)

            row = cursor.fetchone()
            if row and row["cookies"]:
                cookies_dict = json.loads(row["cookies"])
                result = {
                    "cookies": cookies_dict,
                    "created_at": row["created_at"],
                    "expires_at": row["expires_at"],
                }
                logger.debug("找到登录信息")
                return result
            else:
                logger.debug("未找到登录信息")
                return None

    def save_auth(self, cookies: dict, expires_at: Optional[str] = None) -> None:
        """
        保存登录信息

        Args:
            cookies: Cookie 字典
            expires_at: 过期时间
        """
        logger.info("保存登录信息")

        now = datetime.now().isoformat()
        cookies_json = json.dumps(cookies, ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE auth
                SET cookies = ?, created_at = ?, expires_at = ?
                WHERE id = 1
            """, (cookies_json, now, expires_at))

            conn.commit()
            logger.info("登录信息已保存")

    def clear_auth(self) -> None:
        """
        清除登录信息
        """
        logger.info("清除登录信息")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE auth
                SET cookies = NULL, created_at = NULL, expires_at = NULL
                WHERE id = 1
            """)

            conn.commit()
            logger.info("登录信息已清除")
