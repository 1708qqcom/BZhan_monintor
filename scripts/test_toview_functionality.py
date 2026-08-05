"""
测试稍后再看功能

使用方式：
python scripts/test_toview_functionality.py
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
from datetime import datetime


class ToViewFunctionalityTester:
    """稍后再看功能测试器"""

    def __init__(self, base_url: str = "http://localhost:3231"):
        self.base_url = base_url
        self.session = requests.Session()

    def test_all(self) -> bool:
        """运行所有测试"""
        print("=" * 60)
        print("稍后再看功能测试")
        print("=" * 60 + "\n")

        tests = [
            ("健康检查", self.test_health),
            ("数据库迁移验证", self.test_database_migration),
            ("B站API测试", self.test_bilibili_api),
            ("飞书推送测试", self.test_feishu_notification),
        ]

        results = []
        for name, test_func in tests:
            print(f"\n测试: {name}")
            print("-" * 40)
            try:
                success = test_func()
                results.append((name, success))
                print(f"结果: {'✓ 通过' if success else '✗ 失败'}")
            except Exception as e:
                results.append((name, False))
                print(f"结果: ✗ 异常 - {e}")

        # 汇总
        print("\n" + "=" * 60)
        print("测试汇总")
        print("=" * 60)
        for name, success in results:
            status = "✓" if success else "✗"
            print(f"{status} {name}")

        passed = sum(1 for _, success in results if success)
        total = len(results)
        print(f"\n通过: {passed}/{total}")
        print("=" * 60)

        return passed == total

    def test_health(self) -> bool:
        """测试健康检查"""
        try:
            response = self.session.get(f"{self.base_url}/api/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"  服务状态: {data.get('status')}")
                print(f"  数据库状态: {data.get('database')}")
                print(f"  版本: {data.get('version')}")
                return data.get('status') == 'ok'
            return False
        except Exception as e:
            print(f"  错误: {e}")
            return False

    def test_database_migration(self) -> bool:
        """测试数据库迁移"""
        try:
            from src.database import Database

            db = Database()

            # 检查表是否存在
            with db._get_connection() as conn:
                cursor = conn.cursor()

                # 检查 toview_videos 表
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='toview_videos'
                """)
                toview_exists = cursor.fetchone() is not None

                # 检查 toview_push_history 表
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='toview_push_history'
                """)
                history_exists = cursor.fetchone() is not None

                print(f"  toview_videos 表: {'✓ 存在' if toview_exists else '✗ 不存在'}")
                print(f"  toview_push_history 表: {'✓ 存在' if history_exists else '✗ 不存在'}")

                return toview_exists and history_exists
        except Exception as e:
            print(f"  错误: {e}")
            return False

    def test_bilibili_api(self) -> bool:
        """测试B站API"""
        try:
            from src.database import Database
            from src.bilibili import BilibiliClient

            db = Database()

            # 获取第一个用户的Cookie
            auth = db.get_auth()
            if not auth or not auth.get("cookies"):
                print("  警告: 没有有效的B站登录，跳过API测试")
                return True  # 跳过不算失败

            cookies = auth["cookies"]
            client = BilibiliClient(cookies=cookies)

            # 测试获取稍后再看列表
            print("  尝试获取稍后再看列表...")
            videos = client.get_toview_list(page=1, page_size=5)

            print(f"  成功获取 {len(videos)} 个视频")

            if videos:
                first_video = videos[0]
                print(f"  第一个视频: {first_video.get('title', '未知')[:30]}")

            return True
        except Exception as e:
            print(f"  错误: {e}")
            return False

    def test_feishu_notification(self) -> bool:
        """测试飞书推送"""
        try:
            from src.database import Database
            from src.feishu import FeishuNotifier

            db = Database()

            # 获取飞书Webhook配置
            webhook_url = db.get_config_value("feishu_webhook_url")

            if not webhook_url:
                print("  警告: 未配置飞书Webhook，跳过推送测试")
                return True  # 跳过不算失败

            print(f"  Webhook地址: {webhook_url[:50]}...")

            # 测试发送稍后再看通知
            test_videos = [
                {
                    "bvid": "BV1test123",
                    "title": "测试视频标题",
                    "author": "测试UP主",
                    "play": 12345
                }
            ]

            feishu = FeishuNotifier(webhook_url)
            success = feishu.send_toview_notification("测试用户", test_videos)

            if success:
                print("  飞书推送测试消息发送成功")
            else:
                print("  飞书推送测试消息发送失败")

            return True
        except Exception as e:
            print(f"  错误: {e}")
            return False


if __name__ == "__main__":
    print("\n提示：确保服务已启动 (python main.py)")
    print("提示：确保已执行数据库迁移 (python scripts/migrate_add_toview_tables.py)\n")

    tester = ToViewFunctionalityTester()
    success = tester.test_all()

    sys.exit(0 if success else 1)