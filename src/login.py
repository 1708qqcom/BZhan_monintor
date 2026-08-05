"""
B站扫码登录模块

功能:
- 生成二维码供用户扫描
- 轮询扫码状态
- 保存登录Cookie
- 检查Cookie有效性
- 自动刷新过期Cookie
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

import segno
import requests


class BilibiliLogin:
    """B站扫码登录管理"""

    # B站Web端扫码登录接口
    QRCODE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
    RESULT_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
    USER_INFO_URL = "https://api.bilibili.com/x/space/acc/info"

    # 模拟浏览器请求头
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://passport.bilibili.com/",
    }

    # 扫码状态码(轮询接口返回的data.code)
    STATUS_NOT_SCAN = 86101      # 未扫描
    STATUS_SCANNED = 86090       # 已扫描未确认
    STATUS_SUCCESS = 0           # 成功
    STATUS_EXPIRED = 86038       # 二维码过期

    def __init__(self, cookie_file: str = "config/bilibili_cookies.json"):
        self.cookie_file = Path(cookie_file)
        self.cookies: Optional[dict] = None
        self.auth_code: Optional[str] = None
        # 使用session保持cookies
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def generate_qrcode(self) -> Tuple[str, str]:
        """
        生成登录二维码

        Returns:
            (auth_code, qrcode_url) 授权码和二维码URL

        Raises:
            RuntimeError: 获取二维码失败
        """
        try:
            # 先访问登录页获取必要cookies
            self.session.get("https://passport.bilibili.com/", timeout=10)

            # 生成二维码
            response = self.session.get(self.QRCODE_URL, timeout=10)
            response.raise_for_status()
            result = response.json()

            if result.get("code") != 0:
                raise RuntimeError(f"B站API返回错误: {result.get('message', '未知错误')}")

            auth_code = result["data"]["qrcode_key"]
            qrcode_url = result["data"]["url"]
            self.auth_code = auth_code

            return auth_code, qrcode_url

        except requests.RequestException as e:
            raise RuntimeError(f"网络请求失败: {e}")

    def show_qrcode_terminal(self, qrcode_url: str, mode: str = "terminal") -> None:
        """
        在终端显示二维码

        Args:
            qrcode_url: 二维码内容URL
            mode: 显示模式，"terminal" 或 "web"
        """
        print("\n" + "=" * 60)
        print("请使用B站App扫描以下二维码:")
        print("=" * 60 + "\n")

        qr = segno.make(qrcode_url)

        if mode == "web":
            try:
                qr.show()
                print("\n二维码已在图片查看器中打开")
                print("二维码有效期: 180秒")
                return
            except Exception:
                print("\n无法打开图片查看器，使用终端模式...\n")

        # 终端模式
        qr.terminal(compact=True)
        print("\n二维码有效期: 180秒")

    def poll_scan_result(self, auth_code: str, timeout: int = 180) -> Optional[dict]:
        """
        轮询扫码结果

        Args:
            auth_code: 授权码(qrcode_key)
            timeout: 超时时间(秒)

        Returns:
            登录成功返回Cookie字典, 失败返回None
        """
        deadline = time.monotonic() + timeout
        poll_interval = 2
        last_status = None

        status_messages = {
            self.STATUS_NOT_SCAN: "二维码待扫描...",
            self.STATUS_SCANNED: "已扫描，请在App内确认登录...",
        }

        while time.monotonic() < deadline:
            try:
                params = {"qrcode_key": auth_code, "source": "main-fe-header"}

                response = self.session.get(self.RESULT_URL, params=params, timeout=10)
                response.raise_for_status()
                result = response.json()

                if result.get("code") != 0:
                    print(f"\n轮询接口返回错误: {result}")
                    time.sleep(poll_interval)
                    continue

                data = result.get("data", {})
                status = data.get("code")

                # 只在状态变化时输出
                if status != last_status:
                    if status in status_messages:
                        print(f"\n{status_messages[status]}")
                    last_status = status

                if status == self.STATUS_SUCCESS:
                    print("\n登录成功!")
                    # 获取 redirect_url
                    redirect_url = data.get("url")
                    if not redirect_url:
                        print("错误: 未返回跳转链接")
                        return None

                    # 请求 redirect_url 让 cookie 写入 session
                    try:
                        self.session.get(redirect_url, timeout=10)
                    except Exception:
                        pass  # 忽略错误，Cookie 可能已在轮询请求中获取

                    # 从 session.cookies 提取
                    cookies_dict = {}
                    for cookie in self.session.cookies:
                        if cookie.name in ["SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5"]:
                            cookies_dict[cookie.name] = cookie.value

                    # 如果某些必要 cookie 不在 session.cookies 中，尝试从 URL 参数提取
                    if "SESSDATA" not in cookies_dict or "DedeUserID" not in cookies_dict:
                        query = parse_qs(urlparse(redirect_url).query)

                        # 提取所有可能的 cookie
                        if "SESSDATA" in query and "SESSDATA" not in cookies_dict:
                            cookies_dict["SESSDATA"] = query["SESSDATA"][0]
                        if "bili_jct" in query and "bili_jct" not in cookies_dict:
                            cookies_dict["bili_jct"] = query["bili_jct"][0]
                        if "DedeUserID" in query and "DedeUserID" not in cookies_dict:
                            cookies_dict["DedeUserID"] = query["DedeUserID"][0]
                        if "DedeUserID__ckMd5" in query and "DedeUserID__ckMd5" not in cookies_dict:
                            cookies_dict["DedeUserID__ckMd5"] = query["DedeUserID__ckMd5"][0]

                    # 验证必要字段
                    required_cookies = ["SESSDATA", "DedeUserID"]
                    missing_cookies = []
                    for cookie_name in required_cookies:
                        if cookie_name not in cookies_dict:
                            missing_cookies.append(cookie_name)

                    if missing_cookies:
                        print(f"警告: 缺少必要的 cookie: {', '.join(missing_cookies)}")

                    if cookies_dict:
                        print(f"成功提取 Cookie: {list(cookies_dict.keys())}")

                    return cookies_dict if cookies_dict else None

                elif status == self.STATUS_EXPIRED:
                    print("\n二维码已过期，请重新运行")
                    return None

                time.sleep(poll_interval)

            except requests.RequestException as e:
                print(f"\n网络请求失败: {e}，重试中...")
                time.sleep(poll_interval)

        print(f"\n登录超时({timeout}秒)")
        return None

    def save_cookies(self, cookies: dict) -> None:
        """
        保存Cookie到文件

        Args:
            cookies: Cookie字典

        Raises:
            IOError: 文件写入失败
        """
        # 确保目录存在
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)

        # 构造保存数据
        data = {
            "cookies": cookies,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            with open(self.cookie_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Cookie已保存到: {self.cookie_file}")
        except IOError as e:
            raise IOError(f"文件写入失败: {e}")

    def load_cookies(self) -> Optional[dict]:
        """
        从文件加载Cookie

        Returns:
            Cookie字典, 文件不存在返回None
        """
        if not self.cookie_file.exists():
            return None

        try:
            with open(self.cookie_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.cookies = data.get("cookies")
            return self.cookies
        except (IOError, json.JSONDecodeError) as e:
            print(f"读取Cookie文件失败: {e}")
            return None

    def check_cookie_valid(self) -> bool:
        """
        检查当前Cookie是否有效

        Returns:
            有效返回True
        """
        if not self.cookies:
            # 尝试从文件加载
            self.cookies = self.load_cookies()

        if not self.cookies:
            return False

        try:
            # 构造Cookie字符串
            cookie_str = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Cookie": cookie_str,
            }

            response = requests.get(
                self.USER_INFO_URL,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()

            # code为0表示成功
            return result.get("code") == 0

        except requests.RequestException:
            return False

    def refresh_cookies(self) -> Optional[dict]:
        """
        刷新过期Cookie

        Returns:
            新Cookie字典, 失败返回None
        """
        # B站TV端不支持Cookie刷新, 需要重新登录
        print("Cookie已过期, 请重新登录")
        return None

    def login(self) -> bool:
        """
        执行完整登录流程

        Returns:
            登录成功返回True
        """
        try:
            # 1. 检查现有Cookie
            existing_cookies = self.load_cookies()
            if existing_cookies and self.check_cookie_valid():
                print("当前登录状态有效")
                return True

            # 2. 生成二维码
            print("正在获取登录二维码...")
            auth_code, qrcode_url = self.generate_qrcode()

            # 3. 显示二维码
            self.show_qrcode_terminal(qrcode_url)

            # 4. 轮询扫码结果
            cookies = self.poll_scan_result(auth_code)

            if not cookies:
                return False

            # 5. 保存Cookie
            self.save_cookies(cookies)
            self.cookies = cookies

            return True

        except Exception as e:
            print(f"登录失败: {e}")
            return False