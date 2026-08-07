"""
调度器单元测试
"""
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from src.scheduler import MonitorScheduler


class TestLoadHistory:
    """测试历史记录加载"""

    def test_load_history_file_not_exist(self):
        """文件不存在时初始化空结构"""
        scheduler = MonitorScheduler(
            bilibili_client=MagicMock(),
            feishu_notifier=MagicMock(),
            history_file="nonexistent/path/history.json",
        )

        scheduler.load_history()

        assert scheduler.video_history == {"videos": {}, "updated_at": None}

    def test_load_history_valid_file(self):
        """加载有效的历史文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_file = Path(tmpdir) / "history.json"
            test_data = {
                "videos": {
                    "BV1test": {
                        "title": "测试视频",
                        "up_id": 123,
                        "pushed": True,
                    }
                },
                "updated_at": "2026-08-02T10:00:00",
            }

            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(test_data, f)

            scheduler = MonitorScheduler(
                bilibili_client=MagicMock(),
                feishu_notifier=MagicMock(),
                history_file=str(history_file),
            )

            scheduler.load_history()

            assert scheduler.video_history["videos"]["BV1test"]["title"] == "测试视频"
            assert len(scheduler.video_history["videos"]) == 1

    def test_load_history_invalid_json(self):
        """JSON解析失败时使用空结构"""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_file = Path(tmpdir) / "history.json"

            with open(history_file, "w", encoding="utf-8") as f:
                f.write("not a valid json{")

            scheduler = MonitorScheduler(
                bilibili_client=MagicMock(),
                feishu_notifier=MagicMock(),
                history_file=str(history_file),
            )

            scheduler.load_history()

            assert scheduler.video_history == {"videos": {}, "updated_at": None}

    def test_load_history_missing_videos_key(self):
        """缺少videos字段时使用空结构"""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_file = Path(tmpdir) / "history.json"

            with open(history_file, "w", encoding="utf-8") as f:
                json.dump({"updated_at": "2026-08-02"}, f)

            scheduler = MonitorScheduler(
                bilibili_client=MagicMock(),
                feishu_notifier=MagicMock(),
                history_file=str(history_file),
            )

            scheduler.load_history()

            assert scheduler.video_history == {"videos": {}, "updated_at": None}


class TestSaveHistory:
    """测试历史记录保存"""

    def test_save_history_creates_directory(self):
        """自动创建父目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_file = Path(tmpdir) / "subdir" / "history.json"

            scheduler = MonitorScheduler(
                bilibili_client=MagicMock(),
                feishu_notifier=MagicMock(),
                history_file=str(history_file),
            )
            scheduler.video_history = {"videos": {}, "updated_at": None}

            scheduler.save_history()

            assert history_file.exists()

    def test_save_history_writes_correctly(self):
        """正确写入JSON文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_file = Path(tmpdir) / "history.json"

            scheduler = MonitorScheduler(
                bilibili_client=MagicMock(),
                feishu_notifier=MagicMock(),
                history_file=str(history_file),
            )
            scheduler.video_history = {
                "videos": {"BV1test": {"title": "测试"}},
                "updated_at": None,
            }

            scheduler.save_history()

            with open(history_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert "BV1test" in data["videos"]
            assert data["updated_at"] is not None

    def test_save_history_utf8_encoding(self):
        """正确处理中文编码"""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_file = Path(tmpdir) / "history.json"

            scheduler = MonitorScheduler(
                bilibili_client=MagicMock(),
                feishu_notifier=MagicMock(),
                history_file=str(history_file),
            )
            scheduler.video_history = {
                "videos": {"BV1test": {"title": "中文标题测试"}},
                "updated_at": None,
            }

            scheduler.save_history()

            with open(history_file, "r", encoding="utf-8") as f:
                content = f.read()

            assert "中文标题测试" in content


class TestCleanupOldRecords:
    """测试过期记录清理"""

    def test_cleanup_removes_old_records(self):
        """删除过期记录"""
        scheduler = MonitorScheduler(
            bilibili_client=MagicMock(),
            feishu_notifier=MagicMock(),
            history_retention_days=30,
        )

        old_date = (datetime.now() - timedelta(days=31)).isoformat()
        recent_date = (datetime.now() - timedelta(days=10)).isoformat()

        scheduler.video_history = {
            "videos": {
                "BV1old": {
                    "title": "旧视频",
                    "pushed_at": old_date,
                },
                "BV1new": {
                    "title": "新视频",
                    "pushed_at": recent_date,
                },
            },
            "updated_at": None,
        }

        removed = scheduler.cleanup_old_records()

        assert removed == 1
        assert "BV1old" not in scheduler.video_history["videos"]
        assert "BV1new" in scheduler.video_history["videos"]

    def test_cleanup_keeps_records_without_timestamp(self):
        """保留无时间戳的记录"""
        scheduler = MonitorScheduler(
            bilibili_client=MagicMock(),
            feishu_notifier=MagicMock(),
            history_retention_days=30,
        )

        scheduler.video_history = {
            "videos": {
                "BV1no_time": {
                    "title": "无时间戳视频",
                    "pushed_at": None,
                },
            },
            "updated_at": None,
        }

        removed = scheduler.cleanup_old_records()

        assert removed == 0
        assert "BV1no_time" in scheduler.video_history["videos"]


class TestCheckNewVideos:
    """测试新视频检测"""

    def test_check_new_videos_returns_new_only(self):
        """只返回新视频"""
        mock_client = MagicMock()
        mock_client.get_up_videos.return_value = [
            {"bvid": "BV1new", "title": "新视频"},
            {"bvid": "BV1old", "title": "旧视频"},
        ]

        scheduler = MonitorScheduler(
            bilibili_client=mock_client,
            feishu_notifier=MagicMock(),
        )
        scheduler.video_history = {
            "videos": {"BV1old": {"title": "旧视频"}},
            "updated_at": None,
        }

        new_videos = scheduler.check_new_videos(123, "测试UP主", mock_client)

        assert len(new_videos) == 1
        assert new_videos[0]["bvid"] == "BV1new"

    def test_check_new_videos_empty_result(self):
        """无新视频时返回空列表"""
        mock_client = MagicMock()
        mock_client.get_up_videos.return_value = []

        scheduler = MonitorScheduler(
            bilibili_client=mock_client,
            feishu_notifier=MagicMock(),
        )

        result = scheduler.check_new_videos(123, "测试UP主", mock_client)

        assert result == []

    def test_check_new_videos_handles_exception(self):
        """异常时返回空列表"""
        mock_client = MagicMock()
        mock_client.get_up_videos.side_effect = Exception("API错误")

        scheduler = MonitorScheduler(
            bilibili_client=mock_client,
            feishu_notifier=MagicMock(),
        )

        result = scheduler.check_new_videos(123, "测试UP主", mock_client)

        assert result == []


class TestRecordVideo:
    """测试视频记录"""

    def test_record_video_adds_to_history(self):
        """正确记录视频"""
        scheduler = MonitorScheduler(
            bilibili_client=MagicMock(),
            feishu_notifier=MagicMock(),
        )

        scheduler._record_video(
            bvid="BV1test",
            video_info={"title": "测试视频", "pubdate": 1722571200},
            up_id=123,
            up_name="测试UP主",
            pushed=True,
        )

        assert "BV1test" in scheduler.video_history["videos"]
        record = scheduler.video_history["videos"]["BV1test"]
        assert record["title"] == "测试视频"
        assert record["up_id"] == 123
        assert record["pushed"] is True


class TestPushVideo:
    """测试视频推送"""

    def test_push_video_success(self):
        """推送成功"""
        mock_feishu = MagicMock()
        mock_feishu.send_new_video_notification.return_value = True

        scheduler = MonitorScheduler(
            bilibili_client=MagicMock(),
            feishu_notifier=mock_feishu,
        )

        result = scheduler._push_video(
            bvid="BV1test",
            video_info={"title": "测试视频", "pubdate": 1722571200, "play": 1000},
            up_name="测试UP主",
        )

        assert result is True
        mock_feishu.send_new_video_notification.assert_called_once()

    def test_push_video_no_notifier(self):
        """无推送器时返回False"""
        scheduler = MonitorScheduler(
            bilibili_client=MagicMock(),
            feishu_notifier=None,
        )

        result = scheduler._push_video(
            bvid="BV1test",
            video_info={"title": "测试视频"},
            up_name="测试UP主",
        )

        assert result is False


class TestRunMonitorCycle:
    """测试监控循环"""

    def test_run_cycle_without_database_returns_safely(self):
        """未启用数据库时安全返回，不抛异常（多用户架构依赖 DB）"""
        scheduler = MonitorScheduler(
            bilibili_client=MagicMock(),
            feishu_notifier=MagicMock(),
            database=None,
        )

        # 未启用数据库时应提前返回，不抛异常
        scheduler.run_monitor_cycle()

    def test_run_cycle_no_valid_users_skips(self):
        """无有效B站登录用户时跳过本次循环，不抛异常"""
        mock_db = MagicMock()
        mock_db.get_config.return_value = {}
        mock_db.get_all_users_with_valid_auth.return_value = []

        scheduler = MonitorScheduler(
            bilibili_client=MagicMock(),
            feishu_notifier=MagicMock(),
            database=mock_db,
        )

        # 无有效用户时应跳过，不抛异常
        scheduler.run_monitor_cycle()

        mock_db.get_all_users_with_valid_auth.assert_called_once()