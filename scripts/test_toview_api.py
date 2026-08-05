"""
测试B站"稍后再看"API是否可用

这个脚本会：
1. 从数据库读取用户的B站Cookie
2. 尝试多个可能的API端点
3. 验证返回数据结构
"""
import sys
import os
from pathlib import Path

# 设置控制台编码为UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
from src.database import Database

# 可能的API端点（根据不同来源）
TOVIEW_API_CANDIDATES = [
    # 方案1: 历史记录相关（"稍后再看"可能归属历史记录模块）
    {
        "name": "历史记录模块 - toview",
        "url": "https://api.bilibili.com/x/v2/history/toview",
        "params": {"pn": 1, "ps": 10}
    },
    # 方案2: 收藏夹相关
    {
        "name": "收藏夹模块 - toview",
        "url": "https://api.bilibili.com/x/v2/fav/video",
        "params": {"fid": "toview", "pn": 1, "ps": 10}
    },
    # 方案3: 稍后再看专用接口（最可能的）
    {
        "name": "专用稍后再看接口 v1",
        "url": "https://api.bilibili.com/x/v2/history/toview/web",
        "params": {"pn": 1, "ps": 10}
    },
    # 方案4: 新版接口
    {
        "name": "新版接口",
        "url": "https://api.bilibili.com/x/v3/fav/folder/space4",
        "params": {"pn": 1, "ps": 10}
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


def get_user_cookies():
    """从数据库获取第一个用户的Cookie"""
    db = Database()

    # 获取所有有效B站登录的用户
    users = db.get_all_users_with_valid_auth()

    if not users:
        print("[ERROR] 数据库中没有找到已登录的用户")
        print("请先在Web界面完成B站扫码登录")
        return None

    user = users[0]
    print(f"[OK] 使用用户: {user['username']}")
    print(f"[OK] 用户ID: {user['id']}")

    return user['cookies']


def test_api_endpoint(endpoint: dict, cookies: dict):
    """测试单个API端点"""
    print(f"\n{'='*60}")
    print(f"测试: {endpoint['name']}")
    print(f"URL: {endpoint['url']}")
    print(f"参数: {endpoint['params']}")
    print(f"{'='*60}")

    # 构造Cookie字符串
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    headers = HEADERS.copy()
    headers["Cookie"] = cookie_str

    try:
        response = requests.get(
            endpoint["url"],
            params=endpoint["params"],
            headers=headers,
            timeout=10
        )

        print(f"HTTP状态码: {response.status_code}")

        if response.status_code != 200:
            print(f"[FAIL] HTTP请求失败")
            return False

        result = response.json()
        code = result.get("code")
        message = result.get("message", "")

        print(f"业务码: {code}")
        print(f"消息: {message}")

        if code == 0:
            print(f"[SUCCESS] 接口调用成功！")

            # 分析返回数据
            data = result.get("data", {})
            print(f"\n返回数据结构:")
            print(f"- data 字段类型: {type(data)}")

            if isinstance(data, dict):
                print(f"- data 包含的键: {list(data.keys())}")

                # 检查是否有视频列表
                if "list" in data:
                    vlist = data["list"]
                    # list 可能是列表或字典
                    if isinstance(vlist, list):
                        print(f"- 视频数量: {len(vlist)}")
                        if vlist:
                            print(f"- 第一个视频:")
                            first = vlist[0]
                            print(f"  标题: {first.get('title', 'N/A')}")
                            print(f"  BV号: {first.get('bvid', 'N/A')}")
                            print(f"  UP主: {first.get('author', 'N/A')}")
                    elif isinstance(vlist, dict):
                        print(f"- list 是字典，包含键: {list(vlist.keys())}")
                        if "vlist" in vlist:
                            videos = vlist["vlist"]
                            print(f"- 视频数量: {len(videos)}")
                            if videos:
                                first = videos[0]
                                print(f"- 第一个视频:")
                                print(f"  标题: {first.get('title', 'N/A')}")
                                print(f"  BV号: {first.get('bvid', 'N/A')}")

                if "archives" in data:
                    archives = data["archives"]
                    print(f"- 视频数量: {len(archives)}")
                    if archives:
                        first = archives[0]
                        print(f"- 第一个视频:")
                        print(f"  标题: {first.get('title', 'N/A')}")
                        print(f"  BV号: {first.get('bvid', 'N/A')}")
                        print(f"  UP主: {first.get('owner', {}).get('name', 'N/A')}")

            return True
        else:
            print(f"[FAIL] 业务错误: {message}")

            # 常见错误码分析
            if code == -101:
                print("   -> Cookie已过期或无效")
            elif code == -400:
                print("   -> 请求参数错误")
            elif code == -404:
                print("   -> 接口不存在")
            elif code == -509:
                print("   -> 请求过于频繁")

            return False

    except requests.Timeout:
        print("[FAIL] 请求超时")
        return False
    except requests.ConnectionError:
        print("[FAIL] 连接失败")
        return False
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        return False


def main():
    print("B站'稍后再看'API验证测试")
    print("="*60)

    # 1. 获取Cookie
    cookies = get_user_cookies()
    if not cookies:
        return

    print(f"\n[OK] Cookie字段: {list(cookies.keys())}")

    # 2. 测试各个API端点
    success_count = 0
    for endpoint in TOVIEW_API_CANDIDATES:
        if test_api_endpoint(endpoint, cookies):
            success_count += 1

    # 3. 总结
    print(f"\n{'='*60}")
    print(f"测试完成: {success_count}/{len(TOVIEW_API_CANDIDATES)} 个接口可用")

    if success_count == 0:
        print("\n[建议]")
        print("1. 检查Cookie是否有效（可在Web界面重新登录）")
        print("2. 使用浏览器开发者工具抓取真实API:")
        print("   - 打开 https://www.bilibili.com/account/history")
        print("   - 点击'稍后再看'标签")
        print("   - 查看Network面板的XHR请求")
        print("3. 查阅社区维护的API文档:")
        print("   - https://github.com/SocialSisterYi/bilibili-API-collect")


if __name__ == "__main__":
    main()
