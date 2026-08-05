"""
验证图片显示功能

使用方式：
python scripts/verify_image_display.py
"""
import sys
import os
from pathlib import Path

# 设置控制台编码为UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import Database
from src.bilibili import BilibiliClient


def verify_image_urls():
    """验证图片URL是否正确"""
    print("=" * 60)
    print("验证图片显示功能")
    print("=" * 60 + "\n")

    try:
        db = Database()
        auth = db.get_auth()

        if not auth or not auth.get("cookies"):
            print("[ERROR] 未找到有效的B站登录")
            print("请先在Web界面完成B站扫码登录")
            return False

        print("[OK] 已获取用户登录信息\n")

        client = BilibiliClient(cookies=auth["cookies"])
        videos = client.get_toview_list(page=1, page_size=5)

        if not videos:
            print("[WARNING] 稍后再看列表为空")
            return True

        print(f"获取到 {len(videos)} 个视频\n")
        print("-" * 60)

        all_https = True

        for i, video in enumerate(videos, 1):
            pic_url = video.get("pic", "")

            print(f"\n{i}. {video['title'][:40]}")
            print(f"   UP主: {video['author']}")
            print(f"   封面URL: {pic_url}")

            if pic_url.startswith("https://"):
                print(f"   [OK] 使用HTTPS协议")
            elif pic_url.startswith("http://"):
                print(f"   [FAIL] 仍使用HTTP协议（转换失败）")
                all_https = False
            else:
                print(f"   [WARNING] URL为空或格式异常")

        print("\n" + "=" * 60)

        if all_https:
            print("[SUCCESS] 所有图片URL已成功转换为HTTPS")
            print("\n下一步：")
            print("1. 重启Web服务: python main.py")
            print("2. 访问页面: http://localhost:3231/toview")
            print("3. 查看图片是否正常显示")
            return True
        else:
            print("[ERROR] 部分图片URL未转换，请检查代码")
            return False

    except Exception as e:
        print(f"\n[ERROR] 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = verify_image_urls()
    sys.exit(0 if success else 1)