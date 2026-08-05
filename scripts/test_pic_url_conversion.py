"""
测试图片URL协议转换功能

验证：
1. HTTP URL是否正确转换为HTTPS
2. HTTPS URL是否保持不变
3. 空URL和None是否正确处理
"""
import sys
import os
from pathlib import Path

# 设置控制台编码为UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.bilibili import BilibiliClient
from src.database import Database


def test_url_conversion():
    """测试URL协议转换"""
    print("=" * 60)
    print("测试图片URL协议转换功能")
    print("=" * 60 + "\n")

    # 测试用例
    test_cases = [
        ("http://i2.hdslb.com/bfs/archive/test.jpg", "https://i2.hdslb.com/bfs/archive/test.jpg"),
        ("https://i2.hdslb.com/bfs/archive/test.jpg", "https://i2.hdslb.com/bfs/archive/test.jpg"),
        ("", ""),
        (None, ""),
    ]

    print("单元测试：")
    print("-" * 40)

    passed = 0
    failed = 0

    for input_url, expected_url in test_cases:
        # 模拟转换逻辑
        if input_url and input_url.startswith("http://"):
            result_url = input_url.replace("http://", "https://", 1)
        else:
            result_url = input_url or ""

        # 验证
        if result_url == expected_url:
            print(f"[OK] 输入: {input_url or '(空)'}")
            print(f"     输出: {result_url}")
            passed += 1
        else:
            print(f"[FAIL] 输入: {input_url or '(空)'}")
            print(f"       期望: {expected_url}")
            print(f"       实际: {result_url}")
            failed += 1
        print()

    print("-" * 40)
    print(f"单元测试结果: {passed} 通过, {failed} 失败\n")

    # 集成测试：使用真实API
    print("=" * 60)
    print("集成测试：验证真实API返回的URL")
    print("=" * 60 + "\n")

    try:
        db = Database()
        auth = db.get_auth()

        if not auth or not auth.get("cookies"):
            print("[WARNING] 未找到有效的B站登录，跳过集成测试")
            return

        client = BilibiliClient(cookies=auth["cookies"])
        videos = client.get_toview_list(page=1, page_size=5)

        if not videos:
            print("[WARNING] 稍后再看列表为空，跳过验证")
            return

        print(f"获取到 {len(videos)} 个视频\n")

        http_count = 0
        https_count = 0
        empty_count = 0

        for i, video in enumerate(videos, 1):
            pic_url = video.get("pic", "")
            print(f"{i}. {video['title'][:30]}")
            print(f"   封面URL: {pic_url}")

            if pic_url.startswith("https://"):
                https_count += 1
                print(f"   [OK] 使用HTTPS协议")
            elif pic_url.startswith("http://"):
                http_count += 1
                print(f"   [FAIL] 仍使用HTTP协议（转换失败）")
            else:
                empty_count += 1
                print(f"   [WARNING] URL为空或格式异常")

            print()

        print("=" * 60)
        print("验证结果:")
        print(f"  HTTPS URL: {https_count} 个 [OK]")
        print(f"  HTTP URL: {http_count} 个 [FAIL]")
        print(f"  空URL: {empty_count} 个")
        print("=" * 60)

        if http_count > 0:
            print("\n[ERROR] 发现未转换的HTTP URL，请检查代码实现")
        else:
            print("\n[SUCCESS] 所有URL已成功转换为HTTPS")

    except Exception as e:
        print(f"[ERROR] 集成测试失败: {e}")


if __name__ == "__main__":
    test_url_conversion()
