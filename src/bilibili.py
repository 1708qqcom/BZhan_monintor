"""
B站API封装模块

功能：
- 获取用户关注列表
- 获取UP主视频列表
- 视频信息查询
- WBI签名算法实现
- HTTP请求封装（重试、超时）
"""
import hashlib
import logging
import time
from typing import Optional

import requests

from src.exceptions import (
    BilibiliAPIError,
    CookieExpiredError,
    NetworkError,
    RateLimitError,
    WBISignError,
)

logger = logging.getLogger("monitor.bilibili")


class BilibiliClient:
    """B站API客户端"""

    # API端点
    USER_INFO_API = "https://api.bilibili.com/x/space/wbi/acc/info"
    NAV_API = "https://api.bilibili.com/x/web-interface/nav"  # 用户信息接口（无需WBI）
    FOLLOWINGS_API = "https://api.bilibili.com/x/relation/followings"
    SPACE_SEARCH_API = "https://api.bilibili.com/x/space/wbi/arc/search"
    VIDEO_INFO_API = "https://api.bilibili.com/x/web-interface/view"

    # 请求头
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com",
    }

    # WBI混淆密钥索引表（固定值，来自yutto项目）
    MIXIN_KEY_ENC_TAB = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
        33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
        61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 11, 59, 6, 20, 44, 36, 52,
        34, 56, 57, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77,
        78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96,
        97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112,
        113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127,
        128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142,
        143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157,
        158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172,
        173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187,
        188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202,
        203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217,
        218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232,
        233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247,
        248, 249, 250, 251, 252, 253, 254, 255,
    ]

    # WBI缓存（类属性，所有实例共享）
    _wbi_img_key: Optional[str] = None
    _wbi_sub_key: Optional[str] = None
    _wbi_cache_time: float = 0
    _wbi_cache_ttl: int = 600  # 10分钟缓存

    def __init__(self, cookies: Optional[dict] = None):
        """
        初始化客户端

        Args:
            cookies: 登录Cookie字典
        """
        self.cookies = cookies
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._last_request_time: float = 0
        self._min_request_interval: float = 1.0  # 最小请求间隔（秒）

    @property
    def user_id(self) -> str:
        """获取当前用户ID"""
        return self.cookies.get("DedeUserID", "") if self.cookies else ""

    def _build_cookie_string(self) -> str:
        """构造Cookie字符串"""
        if not self.cookies:
            return ""
        return "; ".join([f"{k}={v}" for k, v in self.cookies.items()])

    def _get_wbi_keys(self) -> tuple[str, str]:
        """
        获取WBI签名密钥

        Returns:
            (img_key, sub_key) 密钥元组

        Raises:
            WBISignError: 获取密钥失败
        """
        # 检查缓存
        if (
            self._wbi_img_key
            and self._wbi_sub_key
            and time.time() - self._wbi_cache_time < self._wbi_cache_ttl
        ):
            logger.debug("使用缓存的WBI密钥")
            return self._wbi_img_key, self._wbi_sub_key

        try:
            logger.info("获取WBI密钥...")

            # 使用nav接口获取WBI密钥（无需签名）
            data = self._make_request(self.NAV_API, params={}, use_wbi=False)

            # 从nav接口的wbi_img字段提取密钥
            wbi_img = data.get("wbi_img", {})
            img_url = wbi_img.get("img_url", "")
            sub_url = wbi_img.get("sub_url", "")

            if not img_url or not sub_url:
                raise WBISignError("响应中缺少WBI密钥")

            # 从URL提取密钥（文件名部分，不含扩展名）
            # URL格式: https://i0.hdslb.com/bfs/wbi/xxx.png
            img_key = img_url.split("/")[-1].split(".")[0]
            sub_key = sub_url.split("/")[-1].split(".")[0]

            # 更新缓存
            BilibiliClient._wbi_img_key = img_key
            BilibiliClient._wbi_sub_key = sub_key
            BilibiliClient._wbi_cache_time = time.time()

            logger.info(f"WBI密钥获取成功，缓存{self._wbi_cache_ttl}秒")
            return img_key, sub_key

        except Exception as e:
            logger.error(f"获取WBI密钥失败: {e}")
            raise WBISignError(f"获取WBI密钥失败: {e}")

    def _get_mixin_key(self, orig: str) -> str:
        """
        生成混淆密钥

        Args:
            orig: 原始密钥字符串

        Returns:
            32位混淆密钥
        """
        # 按固定索引表提取字符
        return "".join([orig[i % len(orig)] for i in self.MIXIN_KEY_ENC_TAB[:32]])

    def _encode_wbi(self, params: dict, img_key: str, sub_key: str) -> dict:
        """
        WBI签名算法

        Args:
            params: 请求参数
            img_key: img密钥
            sub_key: sub密钥

        Returns:
            签名后的参数字典
        """
        # 1. 生成混淆密钥
        mixin_key = self._get_mixin_key(img_key + sub_key)

        # 2. 添加时间戳
        params["wts"] = int(time.time())

        # 3. 添加反爬参数（可选，提高成功率）
        params["dm_img_str"] = "V2ViRzFzZEdGdGJIbHVadz09"
        params["dm_cover_img_str"] = "QU5J"

        # 4. 参数排序、移除非法字符
        # 移除 ! * ' ( ) 等特殊字符（除了字母、数字、-、_、.、~）
        def sanitize(value):
            if isinstance(value, (int, float)):
                return str(value)
            # 过滤非法字符
            return "".join(
                c for c in str(value) if c.isalnum() or c in "-_.~"
            )

        # 按key排序
        sorted_params = sorted(params.items())

        # 5. 构造查询字符串
        query_string = "&".join([f"{k}={sanitize(v)}" for k, v in sorted_params])

        # 6. 计算MD5签名
        w_rid = hashlib.md5((query_string + mixin_key).encode("utf-8")).hexdigest()

        # 7. 添加签名参数
        params["w_rid"] = w_rid

        return params

    def _make_request(
        self,
        url: str,
        params: dict = None,
        retry: int = 3,
        use_wbi: bool = False,
    ) -> dict:
        """
        发起HTTP请求（带重试）

        Args:
            url: 请求地址
            params: 查询参数
            retry: 重试次数
            use_wbi: 是否使用WBI签名

        Returns:
            响应data字段内容

        Raises:
            NetworkError: 网络请求失败
            BilibiliAPIError: API返回错误
            CookieExpiredError: Cookie过期
        """
        if params is None:
            params = {}

        # WBI签名
        if use_wbi:
            img_key, sub_key = self._get_wbi_keys()
            params = self._encode_wbi(params, img_key, sub_key)

        # 请求间隔控制
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)

        # 构造请求头
        headers = self.HEADERS.copy()
        if self.cookies:
            headers["Cookie"] = self._build_cookie_string()

        # 重试循环
        last_error = None
        for attempt in range(retry):
            try:
                logger.debug(f"请求 {url} (尝试 {attempt + 1}/{retry})")
                response = self.session.get(
                    url, params=params, headers=headers, timeout=10
                )

                self._last_request_time = time.time()

                # 检查HTTP状态码
                response.raise_for_status()

                # 解析JSON
                result = response.json()

                # 检查API返回码
                code = result.get("code")
                if code == 0:
                    # 成功
                    data = result.get("data", {})
                    logger.debug(f"请求成功: {url}")
                    return data

                # 处理特定错误码
                message = result.get("message", "未知错误")

                if code == -101:
                    raise CookieExpiredError()
                elif code == -502 or code == -509:
                    raise RateLimitError(message)
                elif code == -509:
                    raise WBISignError(message)
                else:
                    raise BilibiliAPIError(message, code)

            except requests.Timeout:
                last_error = NetworkError(f"请求超时: {url}")
                logger.warning(f"请求超时，尝试 {attempt + 1}/{retry}")

            except requests.ConnectionError:
                last_error = NetworkError(f"连接失败: {url}")
                logger.warning(f"连接失败，尝试 {attempt + 1}/{retry}")

            except requests.RequestException as e:
                last_error = NetworkError(f"请求失败: {e}")
                logger.warning(f"请求失败，尝试 {attempt + 1}/{retry}")

            # 指数退避
            if attempt < retry - 1:
                sleep_time = 2 ** attempt  # 1, 2, 4秒
                logger.info(f"等待 {sleep_time} 秒后重试...")
                time.sleep(sleep_time)

        # 所有重试失败
        logger.error(f"请求失败，已重试 {retry} 次: {url}")
        raise last_error or NetworkError("请求失败")

    def check_cookie_valid(self) -> bool:
        """
        检查Cookie是否有效

        Returns:
            有效返回True
        """
        if not self.cookies:
            logger.warning("Cookie为空")
            return False

        try:
            # 使用nav接口验证Cookie（无需WBI签名）
            data = self._make_request(self.NAV_API, params={}, use_wbi=False)

            # nav接口返回成功表示Cookie有效
            if data and "uname" in data:
                logger.info(f"Cookie有效性检查通过，用户: {data.get('uname')}")
                return True

            logger.warning("Cookie验证响应异常")
            return False

        except CookieExpiredError:
            logger.warning("Cookie已过期")
            return False
        except Exception as e:
            logger.error(f"Cookie检查失败: {e}")
            return False

    def get_followed_ups(
        self, page: int = 1, page_size: int = 50, max_count: int = 50
    ) -> list[dict]:
        """
        获取关注列表

        Args:
            page: 页码（从1开始）
            page_size: 每页数量（最大50）
            max_count: 最多获取数量

        Returns:
            UP主信息列表 [{"mid": 123, "uname": "名字", "face": "头像"}, ...]

        Raises:
            BilibiliAPIError: API调用失败
        """
        if not self.user_id:
            raise BilibiliAPIError("缺少用户ID，请检查Cookie")

        logger.info(f"获取关注列表 (page={page}, page_size={page_size})")

        all_ups = []
        current_page = page

        while len(all_ups) < max_count:
            params = {
                "vmid": self.user_id,
                "pn": current_page,
                "ps": page_size,
                "order": "desc",  # 按关注时间倒序
                "order_type": "attention",
            }

            try:
                data = self._make_request(self.FOLLOWINGS_API, params)
                items = data.get("list", [])

                if not items:
                    logger.info(f"第 {current_page} 页无数据，停止翻页")
                    break

                # 解析UP主信息
                for item in items:
                    up_info = {
                        "mid": item.get("mid"),
                        "uname": item.get("uname"),
                        "face": item.get("face"),
                        "sign": item.get("sign", ""),
                    }
                    all_ups.append(up_info)

                logger.info(f"第 {current_page} 页获取 {len(items)} 个UP主")

                # 检查是否需要继续翻页
                if len(items) < page_size:
                    # 本页未满，说明已到底
                    break

                current_page += 1

            except Exception as e:
                logger.error(f"获取关注列表失败: {e}")
                raise

        # 截取到max_count
        result = all_ups[:max_count]
        logger.info(f"获取关注列表成功，共 {len(result)} 个UP主")
        return result

    def get_up_videos(
        self, up_id: int, page: int = 1, page_size: int = 30
    ) -> list[dict]:
        """
        获取UP主视频列表

        Args:
            up_id: UP主ID (mid)
            page: 页码（从1开始）
            page_size: 每页数量（最大30）

        Returns:
            视频信息列表 [{"aid": 123, "bvid": "BV...", "title": "标题", "pubdate": 123456, ...}, ...]

        Raises:
            BilibiliAPIError: API调用失败
        """
        logger.info(f"获取UP主 {up_id} 的视频列表 (page={page}, page_size={page_size})")

        params = {
            "mid": up_id,
            "ps": page_size,
            "tid": 0,  # 0表示全部分区
            "pn": page,
            "order": "pubdate",  # 按发布时间排序
            "order_avoided": "true",  # 避免排序优化，保证顺序稳定
        }

        try:
            # 需要WBI签名
            data = self._make_request(self.SPACE_SEARCH_API, params, use_wbi=True)

            # 解析视频列表
            vlist = data.get("list", {}).get("vlist", [])

            if not vlist:
                logger.info(f"UP主 {up_id} 暂无视频")
                return []

            videos = []
            for item in vlist:
                # B站API返回的字段名可能是 created 或 pubdate
                pubdate = item.get("pubdate") or item.get("created")

                video_info = {
                    "aid": item.get("aid"),
                    "bvid": item.get("bvid"),
                    "title": item.get("title"),
                    "pic": item.get("pic"),
                    "pubdate": pubdate,  # Unix时间戳
                    "play": item.get("play"),  # 播放量
                    "video_review": item.get("comment"),  # 评论数（字段名是comment）
                    "description": item.get("description", ""),
                    "length": item.get("length", ""),  # 视频时长
                }
                videos.append(video_info)

                # 调试日志：记录第一个视频的字段
                if len(videos) == 1:
                    logger.debug(f"视频数据字段: {list(item.keys())}")

            logger.info(f"获取UP主 {up_id} 视频成功，共 {len(videos)} 个视频")
            return videos

        except Exception as e:
            logger.error(f"获取UP主 {up_id} 视频列表失败: {e}")
            raise

    def get_video_info(self, aid: int = None, bvid: str = None) -> Optional[dict]:
        """
        获取视频详细信息

        Args:
            aid: 视频AV号（与bvid二选一）
            bvid: 视频BV号（与aid二选一）

        Returns:
            视频信息字典，包含UP主、统计数据等

        Raises:
            BilibiliAPIError: API调用失败
        """
        if not aid and not bvid:
            raise BilibiliAPIError("必须提供aid或bvid")

        params = {}
        if aid:
            params["aid"] = aid
        else:
            params["bvid"] = bvid

        logger.info(f"获取视频信息: {aid or bvid}")

        try:
            data = self._make_request(self.VIDEO_INFO_API, params)

            video_info = {
                "aid": data.get("aid"),
                "bvid": data.get("bvid"),
                "title": data.get("title"),
                "description": data.get("desc"),
                "pic": data.get("pic"),
                "pubdate": data.get("pubdate"),
                "owner": {
                    "mid": data.get("owner", {}).get("mid"),
                    "name": data.get("owner", {}).get("name"),
                },
                "stat": {
                    "view": data.get("stat", {}).get("view"),
                    "like": data.get("stat", {}).get("like"),
                    "coin": data.get("stat", {}).get("coin"),
                    "favorite": data.get("stat", {}).get("favorite"),
                    "share": data.get("stat", {}).get("share"),
                    "danmaku": data.get("stat", {}).get("danmaku"),
                },
                "duration": data.get("duration"),  # 视频时长（秒）
                "dimension": data.get("dimension", {}),  # 分辨率
            }

            logger.info(f"获取视频信息成功: {video_info['title']}")
            return video_info

        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            raise

    def get_video_detail(self, bvid: str) -> dict:
        """
        获取视频详情（简化版，用于补全视频信息）

        Args:
            bvid: 视频BV号

        Returns:
            包含 title, view_count, pub_date, desc 的字典

        Raises:
            BilibiliAPIError: API调用失败
        """
        logger.info(f"获取视频详情: bvid={bvid}")

        try:
            # 复用 get_video_info 方法
            full_info = self.get_video_info(bvid=bvid)

            if not full_info:
                raise BilibiliAPIError(f"视频不存在: {bvid}")

            # 提取需要的字段
            stat = full_info.get("stat", {})
            pubdate_ts = full_info.get("pubdate")

            # 转换发布时间戳为字符串
            pub_date = None
            if pubdate_ts:
                from datetime import datetime
                pub_date = datetime.fromtimestamp(pubdate_ts).strftime("%Y-%m-%d %H:%M:%S")

            detail = {
                "title": full_info.get("title", ""),
                "view_count": stat.get("view", 0) or 0,
                "pub_date": pub_date,
                "desc": full_info.get("description", ""),
            }

            logger.info(f"视频详情获取成功: title={detail['title']}")
            return detail

        except Exception as e:
            logger.error(f"获取视频详情失败: {e}")
            raise

    def get_up_info(self, mid: int) -> dict:
        """
        获取UP主详细信息

        Args:
            mid: UP主ID

        Returns:
            UP主信息字典 {"mid": 123, "name": "名字", "face": "头像URL", "sign": "签名"}

        Raises:
            BilibiliAPIError: API调用失败
        """
        logger.info(f"获取UP主信息: mid={mid}")

        params = {"mid": mid}

        try:
            # 需要WBI签名
            data = self._make_request(self.USER_INFO_API, params, use_wbi=True)

            # 检查返回数据是否为字典
            if not isinstance(data, dict):
                logger.error(f"UP主信息返回格式错误: type={type(data)}, value={data}")
                raise BilibiliAPIError(f"返回数据格式错误: {type(data)}")

            # 安全提取字段
            level_data = data.get("level")
            fans_data = data.get("fans")

            up_info = {
                "mid": data.get("mid"),
                "name": data.get("name"),
                "face": data.get("face"),
                "sign": data.get("sign", ""),
                "level": level_data if isinstance(level_data, int) else 0,
                "fans": fans_data if isinstance(fans_data, int) else 0,
            }

            logger.info(f"获取UP主信息成功: {up_info['name']}")
            return up_info

        except Exception as e:
            logger.error(f"获取UP主信息失败: {e}")
            raise

    def set_cookies(self, cookies: dict) -> None:
        """设置Cookie"""
        self.cookies = cookies