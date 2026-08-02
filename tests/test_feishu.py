"""
飞书推送模块单元测试

测试内容:
- 播放量格式化
- Webhook发送（mock测试）
- 消息构造逻辑
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import requests

from src.feishu import FeishuNotifier
from src.exceptions import FeishuAPIError


class TestFeishuNotifier(unittest.TestCase):
    """飞书推送测试类"""

    def setUp(self):
        """测试初始化"""
        self.webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/test"
        self.notifier = FeishuNotifier(self.webhook_url)

    def test_format_view_count_less_than_10000(self):
        """测试播放量格式化 - 小于1万"""
        # 小于10000的数字，直接返回字符串
        self.assertEqual(self.notifier._format_view_count(100), "100")
        self.assertEqual(self.notifier._format_view_count(9999), "9999")
        self.assertEqual(self.notifier._format_view_count(0), "0")

    def test_format_view_count_greater_than_10000(self):
        """测试播放量格式化 - 大于等于1万"""
        # 大于等于10000的数字，转换为"X.X万"格式
        self.assertEqual(self.notifier._format_view_count(10000), "1.0万")
        self.assertEqual(self.notifier._format_view_count(12345), "1.2万")
        self.assertEqual(self.notifier._format_view_count(99999), "10.0万")

    @patch('src.feishu.requests.post')
    def test_send_webhook_success(self, mock_post):
        """测试Webhook发送 - 成功响应"""
        # 模拟成功响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "msg": "success"}
        mock_post.return_value = mock_response

        payload = {"msg_type": "text", "content": {"text": "test"}}
        result = self.notifier._send_webhook(payload)

        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch('src.feishu.requests.post')
    def test_send_webhook_http_error(self, mock_post):
        """测试Webhook发送 - HTTP错误"""
        # 模拟HTTP错误
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        payload = {"msg_type": "text", "content": {"text": "test"}}
        result = self.notifier._send_webhook(payload)

        self.assertFalse(result)

    @patch('src.feishu.requests.post')
    def test_send_webhook_feishu_error(self, mock_post):
        """测试Webhook发送 - 飞书返回错误码"""
        # 模拟飞书API返回错误
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 1001, "msg": "invalid webhook"}
        mock_post.return_value = mock_response

        payload = {"msg_type": "text", "content": {"text": "test"}}

        with self.assertRaises(FeishuAPIError) as context:
            self.notifier._send_webhook(payload)

        self.assertEqual(context.exception.code, 1001)
        self.assertIn("invalid webhook", str(context.exception))

    @patch('src.feishu.requests.post')
    def test_send_webhook_timeout(self, mock_post):
        """测试Webhook发送 - 网络超时"""
        # 模拟超时
        mock_post.side_effect = requests.Timeout("Connection timeout")

        payload = {"msg_type": "text", "content": {"text": "test"}}
        result = self.notifier._send_webhook(payload)

        self.assertFalse(result)

    @patch('src.feishu.requests.post')
    def test_send_webhook_connection_error(self, mock_post):
        """测试Webhook发送 - 连接失败"""
        # 模拟连接失败
        mock_post.side_effect = requests.ConnectionError("Connection failed")

        payload = {"msg_type": "text", "content": {"text": "test"}}
        result = self.notifier._send_webhook(payload)

        self.assertFalse(result)

    def test_send_webhook_empty_url(self):
        """测试Webhook发送 - 空URL"""
        notifier = FeishuNotifier("")
        payload = {"msg_type": "text", "content": {"text": "test"}}
        result = notifier._send_webhook(payload)

        self.assertFalse(result)

    @patch('src.feishu.FeishuNotifier._send_webhook')
    def test_send_new_video_notification(self, mock_send):
        """测试新视频通知发送"""
        # 模拟发送成功
        mock_send.return_value = True

        result = self.notifier.send_new_video_notification(
            up_name="测试UP主",
            video_title="测试视频标题",
            video_url="https://www.bilibili.com/video/BV123456789",
            pub_time="2026-08-02 12:00:00",
            view_count=10000
        )

        self.assertTrue(result)
        mock_send.assert_called_once()

        # 验证payload结构
        call_args = mock_send.call_args
        payload = call_args[0][0]

        self.assertEqual(payload["msg_type"], "interactive")
        self.assertIn("card", payload)
        self.assertIn("header", payload["card"])

    @patch('src.feishu.FeishuNotifier._send_webhook')
    def test_send_error_notification(self, mock_send):
        """测试错误告警发送"""
        # 模拟发送成功
        mock_send.return_value = True

        result = self.notifier.send_error_notification("测试错误信息")

        self.assertTrue(result)
        mock_send.assert_called_once()

        # 验证payload结构
        call_args = mock_send.call_args
        payload = call_args[0][0]

        self.assertEqual(payload["msg_type"], "interactive")
        self.assertIn("card", payload)
        # 验证使用红色主题
        self.assertEqual(payload["card"]["header"]["template"], "red")


class TestFeishuAPIError(unittest.TestCase):
    """飞书异常类测试"""

    def test_error_with_code(self):
        """测试带错误码的异常"""
        error = FeishuAPIError("测试错误", code=1001)
        self.assertEqual(error.message, "测试错误")
        self.assertEqual(error.code, 1001)
        self.assertIn("1001", str(error))
        self.assertIn("测试错误", str(error))

    def test_error_without_code(self):
        """测试不带错误码的异常"""
        error = FeishuAPIError("测试错误")
        self.assertEqual(error.message, "测试错误")
        self.assertIsNone(error.code)
        self.assertEqual(str(error), "测试错误")


if __name__ == '__main__':
    unittest.main()