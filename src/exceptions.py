"""
B站API异常类定义

功能:
- 定义API相关异常基类
- 具体异常类型细分
"""


class BilibiliAPIError(Exception):
    """B站API错误基类"""

    def __init__(self, message: str, code: int = None):
        """
        初始化异常

        Args:
            message: 错误信息
            code: API返回的错误码（可选）
        """
        self.message = message
        self.code = code
        super().__init__(self.message)

    def __str__(self):
        if self.code is not None:
            return f"[错误码:{self.code}] {self.message}"
        return self.message


class CookieExpiredError(BilibiliAPIError):
    """Cookie已过期或无效"""

    def __init__(self, message: str = "Cookie已过期或无效，请重新登录"):
        super().__init__(message, code=-101)


class WBISignError(BilibiliAPIError):
    """WBI签名失败"""

    def __init__(self, message: str = "WBI签名生成失败"):
        super().__init__(message, code=-509)


class NetworkError(BilibiliAPIError):
    """网络请求失败"""

    def __init__(self, message: str = "网络请求失败"):
        super().__init__(message, code=-1)


class RateLimitError(BilibiliAPIError):
    """请求频率超限"""

    def __init__(self, message: str = "请求频率超限，请稍后重试"):
        super().__init__(message, code=-502)


class FeishuAPIError(Exception):
    """飞书API错误"""

    def __init__(self, message: str, code: int = None):
        """
        初始化异常

        Args:
            message: 错误信息
            code: 飞书API返回的错误码（可选）
        """
        self.message = message
        self.code = code
        super().__init__(self.message)

    def __str__(self):
        if self.code is not None:
            return f"[飞书错误码:{self.code}] {self.message}"
        return self.message