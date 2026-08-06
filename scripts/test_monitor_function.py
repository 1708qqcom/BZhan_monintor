"""
测试监控功能 - 验证新视频检测和推送

思路：
1. 清空某个UP主的历史视频记录
2. 运行一次监控循环
3. 观察是否能检测到"新视频"并推送到飞书
"""
import logging
from src.database import Database
from src.login import BilibiliLogin
from src.bilibili import BilibiliClient
from src.feishu import FeishuNotifier
from src.scheduler import MonitorScheduler
import yaml

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_monitor_once():
    """测试一次监控循环"""

    print("=" * 60)
    print("监控功能测试")
    print("=" * 60)

    # 1. 加载配置
    with open('config/settings.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 2. 初始化数据库
    db = Database()
    db.init_db()

    # 3. 获取一个测试UP主
    ups = db.get_ups(is_monitoring=True)
    if not ups:
        print("[ERROR] 数据库中没有UP主，请先同步关注列表")
        return

    test_up = ups[0]
    print(f"\n测试UP主: {test_up['name']} (mid={test_up['mid']})")

    # 4. 删除该UP主的所有视频历史记录（模拟"从未监控过"）
    print(f"\n清除 {test_up['name']} 的历史记录...")

    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM videos WHERE up_id = ?", (test_up['id'],))
        deleted = cursor.rowcount
        conn.commit()

    print(f"已删除 {deleted} 条历史记录")

    # 5. 加载Cookie
    login = BilibiliLogin()
    cookies = login.load_cookies()

    if not cookies:
        print("[ERROR] 未找到Cookie，请先运行 'python main.py --login'")
        return

    # 6. 初始化客户端
    client = BilibiliClient(cookies)

    # 7. 验证Cookie
    if not client.check_cookie_valid():
        print("[ERROR] Cookie已过期，请重新登录")
        return

    print("[OK] Cookie有效")

    # 8. 初始化飞书推送器
    webhook_url = config.get('feishu', {}).get('webhook_url', '')
    if not webhook_url:
        print("[ERROR] 未配置飞书Webhook URL")
        return

    notifier = FeishuNotifier(webhook_url)
    print("[OK] 飞书推送器已初始化")

    # 9. 创建调度器并执行一次检查
    scheduler = MonitorScheduler(
        bilibili_client=client,
        feishu_notifier=notifier,
        check_interval_minutes=30,
        max_ups=1,  # 只检查1个UP主
        database=db,
    )

    # 重新加载历史（已清空）
    scheduler.load_history()

    print("\n" + "=" * 60)
    print("开始测试监控循环...")
    print("=" * 60)

    # 执行一次监控循环
    try:
        scheduler.run_monitor_cycle()
        print("\n" + "=" * 60)
        print("[SUCCESS] 监控循环完成！请检查飞书群消息")
        print("=" * 60)
    except Exception as e:
        print(f"\n[ERROR] 监控循环异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_monitor_once()
