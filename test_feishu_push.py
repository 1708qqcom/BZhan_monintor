"""
飞书推送功能测试脚本

使用方法:
    python test_feishu_push.py
"""
import sys
import yaml
from pathlib import Path

# 设置输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 加载配置
config_path = Path("config/settings.yaml")
with open(config_path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# 导入飞书推送模块
from src.feishu import FeishuNotifier

# 初始化推送器
webhook_url = config.get("feishu", {}).get("webhook_url", "")
if not webhook_url:
    print("错误: 未配置飞书 Webhook URL")
    print("请在 config/settings.yaml 中配置 feishu.webhook_url")
    exit(1)

notifier = FeishuNotifier(webhook_url)

print("=" * 50)
print("飞书推送功能测试")
print("=" * 50)

# 测试1: 发送新视频通知
print("\n[测试1] 发送新视频通知...")
success1 = notifier.send_new_video_notification(
    up_name="测试UP主",
    video_title="这是一个测试视频标题",
    video_url="https://www.bilibili.com/video/BV1test123456",
    pub_time="2026-08-02 15:30:00",
    view_count=12345
)

if success1:
    print("[OK] 新视频通知发送成功")
else:
    print("[FAIL] 新视频通知发送失败")

# 测试2: 发送错误告警
print("\n[测试2] 发送错误告警...")
success2 = notifier.send_error_notification(
    error_msg="这是一条测试错误信息，用于验证告警功能"
)

if success2:
    print("[OK] 错误告警发送成功")
else:
    print("[FAIL] 错误告警发送失败")

# 总结
print("\n" + "=" * 50)
if success1 and success2:
    print("[SUCCESS] 所有测试通过！请检查飞书群消息")
else:
    print("[FAILED] 部分测试失败，请检查配置和网络")
print("=" * 50)