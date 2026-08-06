"""
测试引导流程 API 接口

运行方式：python test_onboarding_api.py
"""
import requests
import json

BASE_URL = "http://localhost:3231"

def test_api():
    """测试引导流程 API"""

    # 创建 Session（保持 Cookie）
    session = requests.Session()

    # 1. 登录
    print("=" * 50)
    print("步骤1: 登录系统")
    login_data = {
        "username": "admin",
        "password": "123456"  # 尝试默认密码
    }
    response = session.post(f"{BASE_URL}/auth/login", data=login_data)
    print(f"登录状态: {response.status_code}")
    print(f"登录响应: {response.url}")

    if response.status_code != 200:
        # 尝试另一个用户
        print("admin 登录失败，尝试 aa 用户")
        login_data = {
            "username": "aa",
            "password": "aa"
        }
        response = session.post(f"{BASE_URL}/auth/login", data=login_data)
        print(f"登录状态: {response.status_code}")

    if response.status_code != 200:
        print("登录失败，停止测试")
        return

    # 2. 查询引导进度（新用户应该没有记录）
    print("\n" + "=" * 50)
    print("步骤2: 查询引导进度")
    response = session.get(f"{BASE_URL}/api/onboarding/status")
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json(), indent=2)}")

    # 3. 手动创建引导记录（模拟数据库操作）
    print("\n" + "=" * 50)
    print("步骤3: 在数据库中手动创建引导记录")
    import sqlite3
    conn = sqlite3.connect("d:/Desktop/learning_projects_2026/monitor_onlineVideo/data/monitor.db")
    cursor = conn.cursor()

    # 先删除旧记录
    cursor.execute("DELETE FROM user_onboarding WHERE user_id = 2")

    # 插入新记录
    from datetime import datetime
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO user_onboarding
        (user_id, step1_completed, step1_skipped, step2_completed, step2_skipped,
         step3_completed, step3_skipped, current_step, created_at, updated_at)
        VALUES (2, 0, 0, 0, 0, 0, 0, 1, ?, ?)
    """, (now, now))
    conn.commit()
    print("引导记录已创建")
    conn.close()

    # 4. 再次查询引导进度
    print("\n" + "=" * 50)
    print("步骤4: 再次查询引导进度")
    response = session.get(f"{BASE_URL}/api/onboarding/status")
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json(), indent=2)}")

    # 5. 完成步骤1
    print("\n" + "=" * 50)
    print("步骤5: 完成步骤1")
    response = session.post(
        f"{BASE_URL}/api/onboarding/complete-step",
        json={"step": 1}
    )
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json(), indent=2)}")

    # 6. 查询进度
    print("\n" + "=" * 50)
    print("步骤6: 查询进度（步骤1完成后）")
    response = session.get(f"{BASE_URL}/api/onboarding/status")
    print(f"状态码: {response.status_code}")
    progress = response.json()["progress"]
    print(f"进度百分比: {progress['progress_percent']}%")
    print(f"当前步骤: {progress['current_step']}")

    # 7. 跳过步骤2
    print("\n" + "=" * 50)
    print("步骤7: 跳过步骤2")
    response = session.post(
        f"{BASE_URL}/api/onboarding/skip-step",
        json={"step": 2}
    )
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json(), indent=2)}")

    # 8. 完成步骤3
    print("\n" + "=" * 50)
    print("步骤8: 完成步骤3")
    response = session.post(
        f"{BASE_URL}/api/onboarding/complete-step",
        json={"step": 3}
    )
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json(), indent=2)}")

    # 9. 最终查询进度
    print("\n" + "=" * 50)
    print("步骤9: 最终查询进度")
    response = session.get(f"{BASE_URL}/api/onboarding/status")
    print(f"状态码: {response.status_code}")
    progress = response.json()["progress"]
    print(f"进度百分比: {progress['progress_percent']}%")
    print(f"是否完成: {progress['is_completed']}")

    print("\n" + "=" * 50)
    print("✅ API 接口测试完成")

if __name__ == "__main__":
    test_api()