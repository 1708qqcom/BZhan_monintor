"""
定时调度模块

功能：
- 定时执行监控任务
- 管理视频历史记录
- 协调各模块工作流
- 支持数据库存储（v2.1+）
"""
import json
import logging
import signal
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.exceptions import CookieExpiredError
from src.database import Database

logger = logging.getLogger("monitor.scheduler")


class MonitorScheduler:
    """监控任务调度器"""

    def __init__(
        self,
        bilibili_client,
        feishu_notifier,
        history_file: str = "data/video_history.json",
        check_interval_minutes: int = 30,
        max_ups: int = 50,
        history_retention_days: int = 180,
        database: Optional[Database] = None,
    ):
        """
        初始化调度器

        Args:
            bilibili_client: B站API客户端实例
            feishu_notifier: 飞书推送器实例
            history_file: 历史记录文件路径（兼容旧版本）
            check_interval_minutes: 检查间隔（分钟）
            max_ups: 最多监控UP主数量
            history_retention_days: 历史记录保留天数
            database: 数据库实例（v2.1+推荐使用）
        """
        self.bilibili = bilibili_client
        self.feishu = feishu_notifier
        self.history_file = Path(history_file)
        self.check_interval = check_interval_minutes * 60
        self.max_ups = max_ups
        self.history_retention_days = history_retention_days
        self.video_history: dict = {"videos": {}, "updated_at": None}
        self._running = True

        # 手动触发机制（线程安全）
        self._trigger_event = threading.Event()
        self._is_checking = False
        self._check_lock = threading.Lock()

        # 数据库支持（优先使用数据库）
        self.db = database
        self.use_database = database is not None

        # 状态回调函数（用于通知外部状态变化）
        self._state_callback = None

        # 推送器更新锁（保护 feishu 实例的并发更新）
        self._feishu_lock = threading.Lock()

        logger.info(
            f"调度器初始化完成: "
            f"检查间隔={check_interval_minutes}分钟, "
            f"最多监控{max_ups}个UP主, "
            f"历史保留{history_retention_days}天, "
            f"存储模式={'数据库' if self.use_database else 'JSON文件'}"
        )

    # ==================== 历史记录管理 ====================

    def load_history(self) -> None:
        """
        加载历史记录

        优先从数据库加载，如果未启用数据库则从JSON文件加载
        """
        if self.use_database:
            self._load_history_from_db()
        else:
            self._load_history_from_file()

    def _load_history_from_db(self) -> None:
        """
        从数据库加载历史记录

        将数据库中的视频记录转换为内存中的字典结构（兼容旧逻辑）
        """
        logger.debug("从数据库加载历史记录...")

        try:
            # 从数据库获取所有视频记录
            result = self.db.get_videos(page=1, page_size=10000)

            # 转换为字典结构（兼容旧代码）
            videos_dict = {}
            for item in result["items"]:
                bvid = item["bvid"]
                videos_dict[bvid] = {
                    "title": item.get("title", ""),
                    "up_id": item.get("up_id"),
                    "up_name": item.get("up_name", ""),
                    "pubdate": item.get("pub_time"),
                    "pushed": item.get("pushed", False),
                    "pushed_at": item.get("pushed_at"),
                    "created_at": item.get("created_at"),
                }

            self.video_history = {
                "videos": videos_dict,
                "updated_at": datetime.now().isoformat()
            }

            logger.info(f"从数据库加载历史记录成功，共 {len(videos_dict)} 条")

        except Exception as e:
            logger.error(f"从数据库加载历史记录失败: {e}，使用空结构")
            self.video_history = {"videos": {}, "updated_at": None}

    def _load_history_from_file(self) -> None:
        """
        从JSON文件加载历史记录（兼容旧版本）
        """
        if not self.history_file.exists():
            logger.info(f"历史文件不存在，将创建新文件: {self.history_file}")
            self.video_history = {"videos": {}, "updated_at": None}
            return

        try:
            logger.debug(f"正在加载历史记录: {self.history_file}")
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 验证数据结构
            if not isinstance(data, dict) or "videos" not in data:
                logger.warning("历史文件结构异常，使用空结构")
                self.video_history = {"videos": {}, "updated_at": None}
                return

            self.video_history = data
            video_count = len(self.video_history.get("videos", {}))
            logger.info(f"历史记录加载成功，共 {video_count} 条记录")

        except json.JSONDecodeError as e:
            logger.warning(f"历史文件JSON解析失败: {e}，使用空结构")
            self.video_history = {"videos": {}, "updated_at": None}

        except Exception as e:
            logger.error(f"加载历史记录异常: {e}，使用空结构")
            self.video_history = {"videos": {}, "updated_at": None}

    def save_history(self) -> None:
        """
        保存历史记录

        如果启用数据库，数据已在 _record_video() 中实时写入，此方法仅记录日志
        如果未启用数据库，则写入JSON文件
        """
        if self.use_database:
            # 数据库模式下，数据已实时写入
            video_count = len(self.video_history.get("videos", {}))
            logger.debug(f"数据库模式，无需手动保存，当前 {video_count} 条记录")
        else:
            # JSON文件模式
            self._save_history_to_file()

    def _save_history_to_file(self) -> None:
        """
        保存历史记录到JSON文件（兼容旧版本）
        """
        try:
            # 创建父目录
            self.history_file.parent.mkdir(parents=True, exist_ok=True)

            # 更新时间戳
            self.video_history["updated_at"] = datetime.now().isoformat()

            # 写入文件
            logger.debug(f"正在保存历史记录: {self.history_file}")
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.video_history, f, ensure_ascii=False, indent=2)

            video_count = len(self.video_history.get("videos", {}))
            logger.info(f"历史记录保存成功，共 {video_count} 条记录")

        except Exception as e:
            logger.error(f"保存历史记录失败: {e}")
            # 不抛出异常，避免影响主流程

    def cleanup_old_records(self) -> int:
        """
        清理过期历史记录

        删除超过 self.history_retention_days 天的记录

        Returns:
            清理的记录数量
        """
        if not self.video_history.get("videos"):
            logger.debug("无历史记录需要清理")
            return 0

        cutoff_date = datetime.now() - timedelta(days=self.history_retention_days)
        logger.debug(f"清理 {cutoff_date.date()} 之前的记录")

        videos = self.video_history["videos"]
        to_delete = []

        for bvid, record in videos.items():
            pushed_at_str = record.get("pushed_at")
            if not pushed_at_str:
                # 无时间戳的记录也保留（可能是首次运行的记录）
                continue

            try:
                pushed_at = datetime.fromisoformat(pushed_at_str)
                if pushed_at < cutoff_date:
                    to_delete.append(bvid)
                    logger.debug(f"标记删除过期记录: {bvid} ({pushed_at.date()})")
            except ValueError as e:
                logger.warning(f"解析时间戳失败: {pushed_at_str}, {e}")
                continue

        # 执行删除
        for bvid in to_delete:
            del videos[bvid]

        if to_delete:
            logger.info(f"清理了 {len(to_delete)} 条过期历史记录")

        return len(to_delete)

    # ==================== 辅助方法 ====================

    def _record_video(
        self,
        bvid: str,
        video_info: dict,
        up_id: int,
        up_name: str,
        pushed: bool = False,
    ) -> None:
        """
        记录视频到历史

        Args:
            bvid: 视频BV号
            video_info: 视频信息字典
            up_id: UP主ID
            up_name: UP主名称
            pushed: 是否已推送
        """
        now = datetime.now().isoformat()

        record = {
            "title": video_info.get("title", ""),
            "up_id": up_id,
            "up_name": up_name,
            "pubdate": video_info.get("pubdate"),
            "pushed": pushed,
            "pushed_at": now if pushed else None,
            "created_at": now,
        }

        # 更新内存缓存
        self.video_history["videos"][bvid] = record

        # 如果启用数据库，实时写入
        if self.use_database:
            try:
                # 获取UP主的数据库ID
                up_record = self.db.get_up_by_mid(up_id)
                if not up_record:
                    logger.warning(f"UP主不存在于数据库: mid={up_id}, 跳过写入")
                    return

                # 构造视频URL
                video_url = f"https://www.bilibili.com/video/{bvid}"

                # 格式化发布时间
                pubdate = video_info.get("pubdate")
                pub_time = None
                if pubdate:
                    try:
                        pub_time = datetime.fromtimestamp(pubdate).isoformat()
                    except (TypeError, ValueError):
                        pass

                # 写入数据库
                self.db.add_video(
                    up_id=up_record["id"],
                    bvid=bvid,
                    title=video_info.get("title", ""),
                    url=video_url,
                    pub_time=pub_time,
                    view_count=video_info.get("play", 0),
                    pushed=pushed,
                    pushed_at=now if pushed else None,
                )

                logger.debug(f"视频已写入数据库: {bvid}")

            except Exception as e:
                logger.error(f"写入视频到数据库失败: {e}", exc_info=True)

        logger.debug(f"记录视频: {bvid} - {record['title']}")

    def set_state_callback(self, callback) -> None:
        """
        设置状态回调函数

        Args:
            callback: 回调函数，签名为 callback(**kwargs)
                      支持的参数：last_check_time, next_check_time, is_running
        """
        self._state_callback = callback
        logger.debug("状态回调函数已设置")

    def update_feishu_notifier(self, webhook_url: str) -> bool:
        """
        动态更新飞书推送器（线程安全）

        Args:
            webhook_url: 飞书 Webhook URL，空字符串表示禁用推送

        Returns:
            更新成功返回 True
        """
        with self._feishu_lock:
            if webhook_url:
                try:
                    from src.feishu import FeishuNotifier
                    self.feishu = FeishuNotifier(webhook_url)
                    logger.info(f"飞书推送器已更新: {webhook_url[:50]}...")
                    return True
                except Exception as e:
                    logger.error(f"更新飞书推送器失败: {e}")
                    return False
            else:
                self.feishu = None
                logger.info("飞书推送器已禁用")
                return True

    def _notify_state_change(self, **kwargs) -> None:
        """
        通知状态变化

        Args:
            **kwargs: 状态参数
        """
        if self._state_callback:
            try:
                self._state_callback(**kwargs)
            except Exception as e:
                logger.warning(f"状态回调执行失败: {e}")

    def trigger_refresh(self) -> bool:
        """
        手动触发刷新

        线程安全地触发一次立即检查。
        如果当前正在检查中，则返回 False。

        Returns:
            True 表示触发成功，False 表示正在检查中
        """
        with self._check_lock:
            if self._is_checking:
                logger.info("手动触发刷新失败：正在检查中")
                return False

        logger.info("手动触发刷新")
        self._trigger_event.set()
        return True

    def _fetch_and_record_latest_videos(self, up_mid: int, up_name: str, up_db_id: int) -> None:
        """
        获取并记录UP主最新的5个视频

        用于新添加的UP主，确保数据库中有最新视频记录

        Args:
            up_mid: UP主的B站ID
            up_name: UP主名称
            up_db_id: UP主在数据库中的ID
        """
        try:
            logger.debug(f"获取UP主最新视频: {up_name} (mid={up_mid})")

            # 获取最近5个视频
            videos = self.bilibili.get_up_videos(up_mid, page=1, page_size=5)

            if not videos:
                logger.info(f"UP主 {up_name} 暂无视频")
                return

            # 记录到数据库
            for video in videos:
                bvid = video.get("bvid")
                if not bvid:
                    continue

                # 检查是否已存在（避免重复）
                if bvid in self.video_history["videos"]:
                    continue

                # 构造视频URL
                video_url = f"https://www.bilibili.com/video/{bvid}"

                # 格式化发布时间
                pubdate = video.get("pubdate")
                pub_time = None
                if pubdate:
                    try:
                        pub_time = datetime.fromtimestamp(pubdate).isoformat()
                    except (TypeError, ValueError):
                        pass

                # 写入数据库（标记为已推送，避免重复推送）
                now = datetime.now().isoformat()
                self.db.add_video(
                    up_id=up_db_id,
                    bvid=bvid,
                    title=video.get("title", ""),
                    url=video_url,
                    pub_time=pub_time,
                    view_count=video.get("play", 0),
                    pushed=True,  # 标记为已推送，避免后续推送
                    pushed_at=now,
                )

                # 更新内存缓存
                self.video_history["videos"][bvid] = {
                    "title": video.get("title", ""),
                    "up_id": up_mid,
                    "up_name": up_name,
                    "pubdate": pubdate,
                    "pushed": True,
                    "pushed_at": now,
                    "created_at": now,
                }

                logger.debug(f"记录视频: {bvid} - {video.get('title')}")

            logger.info(f"UP主 {up_name} 已记录 {len(videos)} 个最新视频")

        except Exception as e:
            logger.error(f"获取UP主 {up_name} 最新视频失败: {e}")

    def load_config_from_db(self) -> None:
        """
        从数据库加载配置（热更新）

        在每次监控循环开始时调用，读取最新配置
        """
        if not self.use_database:
            logger.debug("未启用数据库，跳过配置热更新")
            return

        try:
            config = self.db.get_config()

            # 更新检查间隔
            interval_str = config.get("check_interval_minutes")
            if interval_str:
                new_interval = int(interval_str) * 60
                if new_interval != self.check_interval:
                    logger.info(f"检查间隔已更新: {self.check_interval // 60}分钟 -> {new_interval // 60}分钟")
                    self.check_interval = new_interval

            # 更新最大UP主数
            max_ups_str = config.get("max_ups")
            if max_ups_str:
                new_max = int(max_ups_str)
                if new_max != self.max_ups:
                    logger.info(f"最大UP主数已更新: {self.max_ups} -> {new_max}")
                    self.max_ups = new_max

            logger.debug("配置热更新完成")

        except Exception as e:
            logger.warning(f"加载配置失败，使用当前配置: {e}")

    # ==================== 辅助方法 ====================

    def _push_video(
        self,
        bvid: str,
        video_info: dict,
        up_name: str,
    ) -> bool:
        """
        推送视频通知到飞书

        Args:
            bvid: 视频BV号
            video_info: 视频信息字典
            up_name: UP主名称

        Returns:
            推送成功返回 True
        """
        # 使用锁保护读取，确保获取最新的推送器实例
        with self._feishu_lock:
            feishu = self.feishu

        if not feishu:
            logger.warning("飞书推送器未初始化，跳过推送")
            return False

        # 构造视频URL
        video_url = f"https://www.bilibili.com/video/{bvid}"

        # 格式化发布时间
        pubdate = video_info.get("pubdate")
        if pubdate:
            try:
                pub_time = datetime.fromtimestamp(pubdate).strftime("%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError):
                pub_time = "未知时间"
                logger.warning(f"发布时间格式异常: {pubdate}")
        else:
            pub_time = "未知时间"

        # 获取播放量
        view_count = video_info.get("play") or 0

        logger.info(f"正在推送视频: {video_info.get('title')}")

        try:
            success = feishu.send_new_video_notification(
                up_name=up_name,
                video_title=video_info.get("title", "未知标题"),
                video_url=video_url,
                pub_time=pub_time,
                view_count=view_count,
            )

            if success:
                logger.info(f"视频推送成功: {bvid}")
            else:
                logger.warning(f"视频推送失败: {bvid}")

            return success

        except Exception as e:
            logger.error(f"推送视频异常: {e}")
            return False

    # ==================== 核心业务 ====================

    def check_new_videos(self, up_id: int, up_name: str) -> list[dict]:
        """
        检查某个UP主的新视频

        Args:
            up_id: UP主ID
            up_name: UP主名称

        Returns:
            新视频列表，每个元素包含 bvid 和 video_info
        """
        logger.debug(f"检查UP主新视频: {up_name} (mid={up_id})")

        try:
            # 获取最近5个视频
            videos = self.bilibili.get_up_videos(up_id, page=1, page_size=5)

            if not videos:
                logger.debug(f"UP主 {up_name} 暂无视频")
                return []

            new_videos = []
            for video in videos:
                bvid = video.get("bvid")
                if not bvid:
                    continue

                # 检查是否已在历史记录中
                if bvid in self.video_history["videos"]:
                    logger.debug(f"视频已记录: {bvid}")
                    continue

                new_videos.append({
                    "bvid": bvid,
                    "video_info": video,
                })
                logger.debug(f"发现新视频: {bvid} - {video.get('title')}")

            if new_videos:
                logger.info(f"UP主 {up_name} 发现 {len(new_videos)} 个新视频")
            else:
                logger.debug(f"UP主 {up_name} 无新视频")

            return new_videos

        except Exception as e:
            logger.error(f"检查UP主 {up_name} 视频失败: {e}")
            return []

    def run_monitor_cycle(self) -> None:
        """
        执行一次监控循环

        流程：
        1. 热更新配置（如果启用数据库）
        2. 检查Cookie有效性
        3. 获取关注列表
        4. 遍历检查新视频
        5. 推送通知
        6. 更新历史记录
        7. 清理过期记录
        """
        # 检查状态锁，防止并发执行
        with self._check_lock:
            if self._is_checking:
                logger.warning("监控循环正在执行，跳过本次触发")
                return
            self._is_checking = True

        logger.info("========== 开始监控循环 ==========")
        cycle_start = time.time()

        # 通知开始检查
        self._notify_state_change(
            is_running=True,
            is_checking=True,
            last_check_time=datetime.now().isoformat()
        )

        try:
            # 1. 热更新配置（如果启用数据库）
            if self.use_database:
                self.load_config_from_db()

            # 2. 验证Cookie
            logger.debug("验证Cookie有效性...")
            if not self.bilibili.check_cookie_valid():
                logger.error("Cookie已过期")
                raise CookieExpiredError()

            # 3. 获取监控列表
            if self.use_database:
                # 从数据库获取正在监控的UP主列表
                logger.info("从数据库获取监控列表...")
                ups = self.db.get_ups(is_monitoring=True)
                # 转换为统一格式（兼容B站API返回格式）
                ups = [{"mid": up["mid"], "uname": up["name"], "face": up.get("face", "")} for up in ups]
                logger.info(f"获取到 {len(ups)} 个正在监控的UP主")
            else:
                # 兼容模式：从B站API获取关注列表
                logger.info("获取B站关注列表...")
                ups = self.bilibili.get_followed_ups(max_count=self.max_ups)
                logger.info(f"获取到 {len(ups)} 个UP主")

            if not ups:
                logger.warning("关注列表为空，跳过本次循环")
                return

            # 判断是否首次运行
            is_first_run = len(self.video_history.get("videos", {})) == 0
            if is_first_run:
                logger.info("首次运行，只记录视频不推送")

            # 3. 遍历UP主检查新视频
            total_new = 0
            total_pushed = 0

            for i, up in enumerate(ups, 1):
                up_id = up.get("mid")
                up_name = up.get("uname", "未知UP主")

                logger.debug(f"[{i}/{len(ups)}] 检查: {up_name}")

                try:
                    # 如果UP主在数据库中但没有视频记录，先获取最新视频
                    if self.use_database:
                        up_record = self.db.get_up_by_mid(up_id)
                        if up_record:
                            existing_videos = self.db.get_videos(page=1, page_size=1, up_id=up_record["id"])
                            if existing_videos["total"] == 0:
                                logger.info(f"UP主 {up_name} 无视频记录，获取最新5个视频")
                                self._fetch_and_record_latest_videos(up_id, up_name, up_record["id"])
                                continue  # 跳过本次检查，下次循环会正常检查新视频

                    new_videos = self.check_new_videos(up_id, up_name)

                    for item in new_videos:
                        bvid = item["bvid"]
                        video_info = item["video_info"]
                        total_new += 1

                        # 非首次运行才推送
                        pushed = False
                        if not is_first_run:
                            pushed = self._push_video(bvid, video_info, up_name)
                            if pushed:
                                total_pushed += 1

                        # 记录到历史
                        self._record_video(
                            bvid=bvid,
                            video_info=video_info,
                            up_id=up_id,
                            up_name=up_name,
                            pushed=pushed,
                        )

                except CookieExpiredError:
                    # Cookie过期，向上抛出终止循环
                    logger.error(f"检查UP主 {up_name} 时Cookie过期")
                    raise

                except Exception as e:
                    # 其他异常，记录日志继续下一个UP主
                    logger.error(f"检查UP主 {up_name} 异常: {e}")
                    continue

            # 4. 清理过期记录
            cleaned = self.cleanup_old_records()

            # 5. 保存历史
            self.save_history()

            # 统计
            cycle_duration = time.time() - cycle_start
            logger.info(
                f"========== 监控循环完成 ========== "
                f"新视频: {total_new}, 已推送: {total_pushed}, "
                f"清理: {cleaned}, 耗时: {cycle_duration:.1f}秒"
            )

            # 通知检查完成，计算下次检查时间
            from datetime import timedelta
            next_check = datetime.now() + timedelta(seconds=self.check_interval)
            self._notify_state_change(
                is_running=True,
                is_checking=False,
                last_check_time=datetime.now().isoformat(),
                next_check_time=next_check.isoformat(),
                check_interval_minutes=self.check_interval // 60
            )

        except CookieExpiredError:
            # 向上抛出，由 start() 处理
            logger.error("Cookie已过期，监控终止")
            raise

        except Exception as e:
            logger.error(f"监控循环异常: {e}")
            # 发送告警
            if self.feishu:
                try:
                    self.feishu.send_error_notification(f"监控循环异常: {e}")
                except Exception as notify_err:
                    logger.error(f"发送告警失败: {notify_err}")
            raise

        finally:
            # 清除检查状态
            with self._check_lock:
                self._is_checking = False

    # ==================== 信号处理和主循环 ====================

    def _graceful_shutdown(self, signum, frame) -> None:
        """
        优雅退出信号处理器

        Args:
            signum: 信号编号
            frame: 当前栈帧
        """
        logger.info(f"收到退出信号 ({signum})，准备优雅退出...")
        self._running = False

        # 保存历史记录
        try:
            self.save_history()
            logger.info("历史记录已保存")
        except Exception as e:
            logger.error(f"保存历史记录失败: {e}")

        logger.info("调度器已停止")
        sys.exit(0)

    def start(self, skip_signals: bool = False) -> None:
        """
        启动定时监控

        无限循环执行监控任务，直到收到退出信号或Cookie过期

        Args:
            skip_signals: 是否跳过信号注册（后台线程模式需要跳过）
        """
        logger.info("=" * 50)
        logger.info("监控调度器启动")
        logger.info("=" * 50)

        # 加载历史记录
        self.load_history()

        # 注册信号处理器（Windows 只支持 SIGINT）
        # 后台线程模式下跳过，因为 signal.signal() 只能在主线程调用
        if not skip_signals:
            try:
                signal.signal(signal.SIGINT, self._graceful_shutdown)
                logger.debug("已注册 SIGINT 信号处理器")
            except ValueError as e:
                logger.warning(f"无法注册信号处理器: {e}")

        logger.info(f"监控间隔: {self.check_interval // 60} 分钟")
        logger.info(f"历史保留: {self.history_retention_days} 天")

        # 主循环
        cycle_count = 0
        while self._running:
            cycle_count += 1
            logger.info(f"\n第 {cycle_count} 次监控循环")

            try:
                self.run_monitor_cycle()

            except CookieExpiredError:
                logger.error("Cookie已过期，请重新登录")
                if self.feishu:
                    try:
                        self.feishu.send_error_notification("Cookie已过期，请重新登录")
                    except Exception:
                        pass
                break

            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                # 异常后继续运行，等待下一次循环

            # 等待下一次循环（可被手动触发打断）
            if self._running:
                logger.info(f"等待 {self.check_interval // 60} 分钟后进行下次检查...")
                triggered = self._trigger_event.wait(timeout=self.check_interval)
                if triggered:
                    logger.info("收到手动触发信号，立即开始检查")
                    self._trigger_event.clear()

        logger.info("调度器已退出")