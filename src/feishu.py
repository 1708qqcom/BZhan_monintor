"""
飞书推送模块

功能：
- 发送新视频通知
- 发送错误告警
- 消息卡片格式化
"""
import json
import logging
from datetime import datetime
from typing import Optional

import requests

from src.exceptions import FeishuAPIError


class FeishuNotifier:
    """飞书消息推送"""

    def __init__(self, webhook_url: str):
        """
        初始化推送器

        Args:
            webhook_url: 飞书群机器人Webhook地址
        """
        self.webhook_url = webhook_url
        self.logger = logging.getLogger("monitor.feishu")

    def send_new_video_notification(
        self, up_name: str, video_title: str, video_url: str, pub_time: str, view_count: int
    ) -> bool:
        """
        发送新视频通知

        Args:
            up_name: UP主名称
            video_title: 视频标题
            video_url: 视频链接
            pub_time: 发布时间
            view_count: 播放量

        Returns:
            发送成功返回True
        """
        self.logger.info(f"准备发送新视频通知: {video_title}")

        # 构造飞书交互式卡片
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "🎬 新视频发布"
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "fields": [
                            {
                                "is_short": True,
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**UP主**\n{up_name}"
                                }
                            },
                            {
                                "is_short": True,
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**发布时间**\n{pub_time}"
                                }
                            }
                        ]
                    },
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"🎬 **[{video_title}]({video_url})**"
                        }
                    },
                    {
                        "tag": "div",
                        "fields": [
                            {
                                "is_short": True,
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**播放量**\n{self._format_view_count(view_count)}"
                                }
                            }
                        ]
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {
                                    "tag": "plain_text",
                                    "content": "观看视频"
                                },
                                "type": "primary",
                                "url": video_url
                            }
                        ]
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"通知时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            }
                        ]
                    }
                ]
            }
        }

        result = self._send_webhook(payload)
        if result:
            self.logger.info(f"新视频通知发送成功: {video_title}")
        else:
            self.logger.warning(f"新视频通知发送失败: {video_title}")
        return result

    def send_error_notification(self, error_msg: str) -> bool:
        """
        发送错误告警

        Args:
            error_msg: 错误信息

        Returns:
            发送成功返回True
        """
        self.logger.error(f"准备发送错误告警: {error_msg}")

        # 构造红色主题告警卡片
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "⚠️ 监控异常告警"
                    },
                    "template": "red"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**错误信息**\n{error_msg}"
                        }
                    },
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**发生时间**\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": "B站UP主监控服务异常"
                            }
                        ]
                    }
                ]
            }
        }

        result = self._send_webhook(payload)
        if result:
            self.logger.info("错误告警发送成功")
        else:
            self.logger.warning("错误告警发送失败")
        return result

    def _format_view_count(self, view_count: int) -> str:
        """
        格式化播放量显示

        Args:
            view_count: 播放量数值

        Returns:
            格式化字符串（如 "1.2万"）
        """
        if view_count >= 10000:
            return f"{view_count / 10000:.1f}万"
        return str(view_count)

    def send_toview_notification(self, username: str, videos: list[dict]) -> bool:
        """
        发送稍后再看推送通知

        Args:
            username: 用户名
            videos: 视频列表，每个元素包含 bvid, title, author, play

        Returns:
            发送成功返回 True
        """
        if not videos:
            self.logger.info("视频列表为空，跳过推送")
            return False

        self.logger.info(f"准备发送稍后再看通知: username={username}, video_count={len(videos)}")

        # 构造视频列表内容
        video_items = []
        for i, video in enumerate(videos, 1):
            bvid = video.get("bvid", "")
            title = video.get("title", "未知标题")
            author = video.get("author", "未知UP主")
            play = video.get("play", 0)

            video_items.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**{i}. 🎬 [{title}](https://www.bilibili.com/video/{bvid})**\n"
                        f"UP主: {author} | 播放: {self._format_view_count(play)}"
                    )
                }
            })

        # 构造飞书交互式卡片
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"📺 {username}的稍后再看提醒"
                    },
                    "template": "blue"
                },
                "elements": video_items + [
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"共 {len(videos)} 个视频待观看"
                            }
                        ]
                    }
                ]
            }
        }

        result = self._send_webhook(payload)
        if result:
            self.logger.info(f"稍后再看通知发送成功: username={username}")
        else:
            self.logger.warning(f"稍后再看通知发送失败: username={username}")
        return result

    def send_message(self, message: str) -> bool:
        """
        发送简单文本消息（用于测试）

        Args:
            message: 消息内容

        Returns:
            发送成功返回True
        """
        self.logger.info(f"准备发送测试消息: {message}")

        payload = {
            "msg_type": "text",
            "content": {
                "text": message
            }
        }

        result = self._send_webhook(payload)
        if result:
            self.logger.info("测试消息发送成功")
        else:
            self.logger.warning("测试消息发送失败")
        return result

    def _send_webhook(self, payload: dict) -> bool:
        """
        发送Webhook请求

        Args:
            payload: 消息载荷

        Returns:
            成功返回True

        Raises:
            FeishuAPIError: 发送失败时抛出
        """
        if not self.webhook_url:
            self.logger.error("Webhook URL 为空，无法发送消息")
            return False

        try:
            self.logger.info("正在发送飞书消息...")
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            # 检查HTTP状态码
            if response.status_code != 200:
                self.logger.error(f"HTTP请求失败，状态码: {response.status_code}")
                return False

            # 解析JSON响应
            result = response.json()
            code = result.get("code")

            # 检查飞书返回的code字段
            if code != 0:
                msg = result.get("msg", "未知错误")
                self.logger.error(f"飞书API返回错误: code={code}, msg={msg}")
                raise FeishuAPIError(msg, code)

            self.logger.info("飞书消息发送成功")
            return True

        except requests.Timeout:
            self.logger.error("请求飞书API超时")
            return False

        except requests.ConnectionError:
            self.logger.error("连接飞书API失败")
            return False

        except requests.RequestException as e:
            self.logger.error(f"请求飞书API异常: {e}")
            return False

        except json.JSONDecodeError:
            self.logger.error("飞书响应JSON解析失败")
            return False