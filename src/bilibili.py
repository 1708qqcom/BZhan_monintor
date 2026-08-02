"""
B站API封装模块

功能：
- 获取用户关注列表
- 获取UP主视频列表
- 视频信息查询
"""
from typing import Optional


class BilibiliClient:
    """B站API客户端"""

    def __init__(self, cookies: Optional[dict] = None):
        """
        初始化客户端

        Args:
            cookies: 登录Cookie字典
        """
        self.cookies = cookies
        self.base_url = "https://api.bilibili.com"

    def get_followed_ups(self, page: int = 1, page_size: int = 50) -> list[dict]:
        """
        获取关注列表

        Args:
            page: 页码
            page_size: 每页数量

        Returns:
            UP主信息列表 [{"mid": 123, "uname": "名字", "face": "头像"}, ...]
        """
        # TODO: 调用 /x/relation/followings 接口
        raise NotImplementedError

    def get_up_videos(
        self, up_id: int, page: int = 1, page_size: int = 30
    ) -> list[dict]:
        """
        获取UP主视频列表

        Args:
            up_id: UP主ID
            page: 页码
            page_size: 每页数量

        Returns:
            视频信息列表 [{"aid": 123, "title": "标题", "pubdate": 123456, "view": 1000}, ...]
        """
        # TODO: 调用 /x/space/wbi/arc/search 接口
        raise NotImplementedError

    def get_video_info(self, aid: int) -> Optional[dict]:
        """
        获取视频详细信息

        Args:
            aid: 视频AV号

        Returns:
            视频信息字典
        """
        # TODO: 调用 /x/web-interface/view 接口
        raise NotImplementedError

    def set_cookies(self, cookies: dict) -> None:
        """设置Cookie"""
        self.cookies = cookies

    def _make_request(self, url: str, params: dict = None) -> dict:
        """
        发起HTTP请求

        Args:
            url: 请求地址
            params: 查询参数

        Returns:
            响应JSON数据
        """
        # TODO: 使用requests发起请求，携带Cookie
        raise NotImplementedError