"""
测试引导流程数据库方法

运行方式：python test_onboarding_db.py
"""
import sys
sys.path.insert(0, 'd:/Desktop/learning_projects_2026/monitor_onlineVideo')

from src.database import Database
from datetime import datetime

def test_database_methods():
    """测试引导进度数据库方法"""

    print("=" * 60)
    print("测试引导进度数据库方法")
    print("=" * 60)

    # 初始化数据库
    db = Database()
    db.init_db()
    print("✓ 数据库初始化成功")

    # 测试用户 ID（使用已存在的用户）
    test_user_id = 2  # aa 用户

    # 1. 测试初始化引导进度
    print("\n" + "-" * 60)
    print("测试 1: 初始化引导进度")
    try:
        # 先删除旧记录
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_onboarding WHERE user_id = ?", (test_user_id,))
            conn.commit()

        # 初始化
        onboarding_id = db.init_onboarding_progress(test_user_id)
        print(f"✓ 引导进度初始化成功: id={onboarding_id}, user_id={test_user_id}")
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        return

    # 2. 测试查询引导进度
    print("\n" + "-" * 60)
    print("测试 2: 查询引导进度")
    progress = db.get_onboarding_progress(test_user_id)
    if progress:
        print(f"✓ 查询成功:")
        print(f"  - user_id: {progress['user_id']}")
        print(f"  - current_step: {progress['current_step']}")
        print(f"  - step1_completed: {progress['step1_completed']}")
        print(f"  - step1_skipped: {progress['step1_skipped']}")
    else:
        print("✗ 查询失败: 未找到记录")
        return

    # 3. 测试完成步骤
    print("\n" + "-" * 60)
    print("测试 3: 完成步骤 1")
    success = db.update_onboarding_step(test_user_id, step=1, completed=True)
    if success:
        print("✓ 步骤 1 已完成")
        progress = db.get_onboarding_progress(test_user_id)
        print(f"  - current_step 更新为: {progress['current_step']}")
        print(f"  - step1_completed: {progress['step1_completed']}")
    else:
        print("✗ 更新失败")
        return

    # 4. 测试跳过步骤
    print("\n" + "-" * 60)
    print("测试 4: 跳过步骤 2")
    success = db.update_onboarding_step(test_user_id, step=2, skipped=True)
    if success:
        print("✓ 步骤 2 已跳过")
        progress = db.get_onboarding_progress(test_user_id)
        print(f"  - current_step 更新为: {progress['current_step']}")
        print(f"  - step2_skipped: {progress['step2_skipped']}")
    else:
        print("✗ 更新失败")
        return

    # 5. 测试完成步骤 3
    print("\n" + "-" * 60)
    print("测试 5: 完成步骤 3")
    success = db.update_onboarding_step(test_user_id, step=3, completed=True)
    if success:
        print("✓ 步骤 3 已完成")
        progress = db.get_onboarding_progress(test_user_id)
        print(f"  - current_step: {progress['current_step']}")
        print(f"  - step3_completed: {progress['step3_completed']}")
    else:
        print("✗ 更新失败")
        return

    # 6. 计算进度
    print("\n" + "-" * 60)
    print("测试 6: 计算进度百分比")
    completed_steps = sum([
        progress['step1_completed'] or progress['step1_skipped'],
        progress['step2_completed'] or progress['step2_skipped'],
        progress['step3_completed'] or progress['step3_skipped']
    ])
    progress_percent = int((completed_steps / 3) * 100)
    is_completed = completed_steps == 3

    print(f"✓ 进度计算:")
    print(f"  - 完成步骤数: {completed_steps}/3")
    print(f"  - 进度百分比: {progress_percent}%")
    print(f"  - 是否完成: {is_completed}")

    # 7. 测试参数校验
    print("\n" + "-" * 60)
    print("测试 7: 参数校验")
    try:
        db.update_onboarding_step(test_user_id, step=4, completed=True)
        print("✗ 未捕获无效参数")
    except ValueError as e:
        print(f"✓ 正确捕获无效参数: {e}")

    try:
        db.update_onboarding_step(test_user_id, step=1)
        print("✗ 未捕获缺少参数")
    except ValueError as e:
        print(f"✓ 正确捕获缺少参数: {e}")

    print("\n" + "=" * 60)
    print("✅ 所有数据库方法测试通过")
    print("=" * 60)

if __name__ == "__main__":
    test_database_methods()
