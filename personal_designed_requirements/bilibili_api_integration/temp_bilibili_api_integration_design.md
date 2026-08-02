# Technical Design - B站API集成

## Overview

本设计文档描述如何在现有项目架构中实现B站API调用功能，核心是WBI签名机制和HTTP请求封装。

**技术选型**：
- HTTP库：`requests`（同步，简单易用）
- 签名算法：MD5（Python标准库 `hashlib`）
- 缓存机制：类属性缓存（WBI密钥、用户信息）

**参考项目**：yutto（B站视频下载器），采用其成熟的WBI签名实现。


## Architecture

### 系统架构图

```
┌─────────────────────────────────────────────────────┐
│                   main.py                            │
│              (主入口 & 配置加载)                      │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              BilibiliClient                          │
│           (src/bilibili.py)                         │
├─────────────────────────────────────────────────────┤
│  • get_followed_ups()    获取关注列表               │
│  • get_up_videos()       获取UP主视频（WBI签名）    │
│  • get_video_info()      获取视频详情               │
│  • check_cookie_valid()  Cookie验证                 │
├─────────────────────────────────────────────────────┤
│  • _make_request()       HTTP请求封装               │
│  • _get_wbi_keys()       获取WBI密钥                │
│  • _encode_wbi()         WBI签名                    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              BilibiliLogin                           │
│           (src/login.py) ✅ 已实现                   │
├─────────────────────────────────────────────────────┤
│  • load_cookies()        加载Cookie                 │
│  • check_cookie_valid()  验证有效性                 │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│      config/bilibili_cookies.json                    │
│              (Cookie存储)                            │
└─────────────────────────────────────────────────────┘
```

### 模块依赖关系

```
main.py
  └── BilibiliClient
        ├── 需要 Cookie（从 login.py 加载）
        ├── 需要 WBI签名逻辑（内部实现）
        └── 需要 HTTP请求封装（内部实现）
```


## Data Model

### Cookie数据结构

已保存在 `config/bilibili_cookies.json`：

```json
{
  "cookies": {
    "SESSDATA": "xxx",
    "bili_jct": "xxx",
    "DedeUserID": "661205625",
    "DedeUserID__ckMd5": "xxx"
  },
  "created_at": "2026-08-02T07:00:45Z",
  "updated_at": "2026-08-02T07:00:45Z"
}
```

### WBI密钥缓存结构

```python
class WbiImg(TypedDict):
    img_key: str   # 从 wbi_img.img_url 提取
    sub_key: str   # 从 wbi_img.sub_url 提取
```

### UP主数据结构

```python
class UPInfo(TypedDict):
    mid: int           # UP主ID
    uname: str         # UP主名称
    face: str          # 头像URL
    sign: str          # 个性签名（可选）
```

### 视频数据结构

```python
class VideoInfo(TypedDict):
    aid: int           # AV号
    bvid: str          # BV号
    title: str         # 标题
    description: str   # 简介
    pic: str           # 封面URL
    pubdate: int       # 发布时间戳
    play: int          # 播放量
    video_review: int  # 弹幕数
```


## API / Interface

### BilibiliClient 类接口

```python
class BilibiliClient:
    """B站API客户端"""

    def __init__(self, cookies: dict):
        """
        初始化客户端

        Args:
            cookies: Cookie字典，包含SESSDATA、bili_jct等
        """

    def check_cookie_valid(self) -> bool:
        """
        检查Cookie有效性

        Returns:
            有效返回True

        Raises:
            CookieExpiredError: Cookie已过期
        """

    def get_followed_ups(
        self,
        page: int = 1,
        page_size: int = 50,
        max_count: int = 50
    ) -> list[dict]:
        """
        获取关注列表

        Args:
            page: 页码（从1开始）
            page_size: 每页数量（最大50）
            max_count: 最多获取数量

        Returns:
            UP主列表 [{"mid": 123, "uname": "名字", "face": "URL"}, ...]

        Raises:
            APIError: API调用失败
            NetworkError: 网络请求失败
        """

    def get_up_videos(
        self,
        up_id: int,
        page: int = 1,
        page_size: int = 30
    ) -> list[dict]:
        """
        获取UP主视频列表

        Args:
            up_id: UP主ID
            page: 页码（从1开始）
            page_size: 每页数量（固定30）

        Returns:
            视频列表 [{"aid": 123, "title": "标题", "pubdate": 123456}, ...]

        Raises:
            APIError: API调用失败
            WBISignError: WBI签名失败
        """

    def get_video_info(self, aid: int) -> dict:
        """
        获取视频详细信息

        Args:
            aid: 视频AV号

        Returns:
            视频详细信息字典

        Raises:
            VideoNotFoundError: 视频不存在
        """

    # 私有方法

    def _make_request(
        self,
        url: str,
        params: dict = None,
        retry: int = 3
    ) -> dict:
        """
        发起HTTP请求（内部方法）

        Args:
            url: 请求地址
            params: 查询参数
            retry: 重试次数

        Returns:
            响应JSON的data部分

        Raises:
            NetworkError: 网络错误
            APIError: API返回错误
        """

    def _get_wbi_keys(self, use_cache: bool = True) -> tuple[str, str]:
        """
        获取WBI签名密钥（内部方法）

        Args:
            use_cache: 是否使用缓存

        Returns:
            (img_key, sub_key)
        """

    def _encode_wbi(
        self,
        params: dict,
        img_key: str,
        sub_key: str
    ) -> dict:
        """
        WBI签名（内部方法）

        Args:
            params: 原始参数
            img_key: 图片密钥
            sub_key: 子密钥

        Returns:
            签名后的参数（包含wts、w_rid等）
        """
```


## Frontend Changes

本功能为纯后端实现，不涉及前端改动。


## Backend Changes

### 文件修改清单

#### 1. src/bilibili.py（核心实现）

**当前状态**：仅有接口定义，方法抛出 `NotImplementedError`

**修改内容**：

```python
# 新增导入
import hashlib
import time
import urllib.parse
import re
import random
import string
import base64
from typing import Optional, TypedDict

# 新增常量
USER_INFO_API = "https://api.bilibili.com/x/web-interface/nav"
FOLLOWINGS_API = "https://api.bilibili.com/x/relation/followings"
SPACE_SEARCH_API = "https://api.bilibili.com/x/space/wbi/arc/search"
VIDEO_INFO_API = "https://api.bilibili.com/x/web-interface/view"

# 新增类型定义
class WbiImg(TypedDict):
    img_key: str
    sub_key: str

# 新增类属性（缓存）
_wbi_img_cache: Optional[WbiImg] = None
_wbi_cache_time: float = 0  # 缓存时间戳

# 实现所有TODO方法
def _get_wbi_keys(self) -> tuple[str, str]: ...
def _encode_wbi(self, params: dict, ...) -> dict: ...
def _make_request(self, url: str, ...) -> dict: ...
def get_followed_ups(self, ...) -> list[dict]: ...
def get_up_videos(self, ...) -> list[dict]: ...
def get_video_info(self, ...) -> dict: ...
```

**新增代码行数估算**：约200行


#### 2. main.py（集成调用）

**修改内容**：

```python
# start_monitor() 函数中添加
def start_monitor(config: dict) -> None:
    # 加载Cookie
    from src.login import BilibiliLogin
    login = BilibiliLogin()
    cookies = login.load_cookies()

    if not cookies:
        print("请先运行 'python main.py --login' 完成登录")
        return

    # 初始化客户端
    from src.bilibili import BilibiliClient
    client = BilibiliClient(cookies)

    # 测试API调用
    ups = client.get_followed_ups(page=1, page_size=10)
    print(f"获取到 {len(ups)} 个UP主")
```

**新增代码行数估算**：约20行


#### 3. requirements.txt（可选）

**当前依赖**：
```
requests
pyyaml
segno
```

**无需新增依赖**：
- WBI签名使用标准库 `hashlib`
- 已满足所有需求


## Implementation Flow

### Phase 1: WBI签名基础（核心）

**任务**：
1. 实现 `_get_wbi_keys()` 方法
   - 调用 `USER_INFO_API` 获取密钥URL
   - 从URL提取 `img_key` 和 `sub_key`
   - 实现缓存机制（有效期10分钟）

2. 实现混淆密钥生成
   ```python
   def _get_mixin_key(string: str) -> str:
       char_indices = [46, 47, 18, 2, 53, 8, ...]
       return "".join([string[idx] for idx in char_indices[:32]])
   ```

3. 实现 `_encode_wbi()` 方法
   - 添加时间戳 `wts`
   - 添加反爬参数 `dm_img_str`、`dm_cover_img_str`
   - 参数排序、非法字符移除
   - MD5签名生成 `w_rid`

**验证**：
```python
# 测试签名
params = {"mid": 123456, "ps": 30}
signed_params = client._encode_wbi(params, img_key, sub_key)
assert "wts" in signed_params
assert "w_rid" in signed_params
```


### Phase 2: HTTP请求封装

**任务**：
1. 实现 `_make_request()` 方法
   - 构造Cookie请求头
   - 发送GET请求
   - 解析JSON响应
   - 错误处理（重试、日志）

2. 实现重试机制
   ```python
   max_retries = 3
   for attempt in range(max_retries):
       try:
           response = requests.get(url, params=params, headers=headers, timeout=10)
           return response.json()["data"]
       except requests.RequestException as e:
           if attempt == max_retries - 1:
               raise
           time.sleep(2 ** attempt)  # 指数退避
   ```

**验证**：
```python
# 测试请求
data = client._make_request(USER_INFO_API)
assert "wbi_img" in data
```


### Phase 3: 核心API实现

**任务**：
1. 实现 `check_cookie_valid()`
   - 调用用户信息接口
   - 返回有效性布尔值

2. 实现 `get_followed_ups()`
   - 调用 `FOLLOWINGS_API`
   - 分页逻辑（循环请求直到达到max_count）
   - 解析返回数据

3. 实现 `get_up_videos()`
   - 获取WBI密钥
   - 构造参数并签名
   - 调用 `SPACE_SEARCH_API`
   - 分页逻辑

4. 实现 `get_video_info()`
   - 调用 `VIDEO_INFO_API`
   - 解析返回数据

**验证**：
```python
# 测试完整流程
ups = client.get_followed_ups(max_count=10)
assert len(ups) > 0

videos = client.get_up_videos(ups[0]["mid"])
assert len(videos) > 0
```


## Error Handling

### 异常类型定义

```python
class BilibiliAPIError(Exception):
    """B站API错误基类"""
    pass

class CookieExpiredError(BilibiliAPIError):
    """Cookie已过期"""
    pass

class WBISignError(BilibiliAPIError):
    """WBI签名失败"""
    pass

class NetworkError(BilibiliAPIError):
    """网络请求失败"""
    pass

class APIError(BilibiliAPIError):
    """API返回错误"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"API错误 {code}: {message}")
```


### 错误处理策略

| 错误类型 | 处理方式 | 重试 | 日志 | 告警 |
|---------|---------|------|------|------|
| CookieExpiredError | 提示重新登录 | ❌ | ✅ | ✅ |
| WBISignError | 重新获取密钥 | ✅ 1次 | ✅ | ❌ |
| NetworkError | 指数退避重试 | ✅ 3次 | ✅ | ❌ |
| APIError (412) | 延长间隔重试 | ✅ 3次 | ✅ | ❌ |
| APIError (其他) | 抛出异常 | ❌ | ✅ | ✅ |


### 日志记录

```python
import logging

logger = logging.getLogger("monitor.bilibili")

# 请求成功
logger.info(f"获取关注列表成功，共 {len(ups)} 个UP主")

# 请求失败
logger.error(f"API调用失败: {url}, 错误: {e}")

# 重试
logger.warning(f"请求失败，第 {attempt} 次重试: {url}")

# Cookie过期
logger.critical("Cookie已过期，请重新登录")
```


## Testing Strategy

### 单元测试

**测试文件**：`tests/test_bilibili.py`

**测试用例**：

```python
import pytest
from src.bilibili import BilibiliClient

class TestBilibiliClient:

    def test_wbi_sign(self):
        """测试WBI签名"""
        client = BilibiliClient({})
        params = {"mid": 123456, "ps": 30}

        # 获取密钥
        img_key, sub_key = client._get_wbi_keys()
        assert img_key is not None
        assert sub_key is not None

        # 签名
        signed = client._encode_wbi(params, img_key, sub_key)
        assert "wts" in signed
        assert "w_rid" in signed
        assert len(signed["w_rid"]) == 32  # MD5长度

    def test_get_followed_ups(self, mock_cookies):
        """测试获取关注列表"""
        client = BilibiliClient(mock_cookies)
        ups = client.get_followed_ups(max_count=10)

        assert len(ups) > 0
        assert "mid" in ups[0]
        assert "uname" in ups[0]
        assert "face" in ups[0]

    def test_get_up_videos(self, mock_cookies):
        """测试获取视频列表"""
        client = BilibiliClient(mock_cookies)
        videos = client.get_up_videos(up_id=123456, page=1)

        assert len(videos) > 0
        assert "aid" in videos[0]
        assert "title" in videos[0]
        assert "pubdate" in videos[0]

    def test_cookie_expired(self, expired_cookies):
        """测试Cookie过期处理"""
        client = BilibiliClient(expired_cookies)

        with pytest.raises(CookieExpiredError):
            client.check_cookie_valid()

    def test_network_retry(self, mock_server):
        """测试网络重试"""
        mock_server.set_timeout_mode(True)

        client = BilibiliClient({})

        with pytest.raises(NetworkError):
            client._make_request("http://test.com/api")

        assert mock_server.request_count == 3  # 重试3次
```


### 集成测试

**测试流程**：

```bash
# 1. 使用真实Cookie测试
python -c "
from src.login import BilibiliLogin
from src.bilibili import BilibiliClient

# 加载Cookie
login = BilibiliLogin()
cookies = login.load_cookies()

if not cookies:
    print('请先运行 python main.py --login')
    exit(1)

# 初始化客户端
client = BilibiliClient(cookies)

# 测试Cookie有效性
print('测试Cookie有效性...')
assert client.check_cookie_valid()
print('✓ Cookie有效')

# 测试获取关注列表
print('测试获取关注列表...')
ups = client.get_followed_ups(max_count=10)
print(f'✓ 获取到 {len(ups)} 个UP主')

# 测试获取视频列表
if ups:
    print('测试获取视频列表...')
    videos = client.get_up_videos(ups[0]['mid'], page=1, page_size=5)
    print(f'✓ 获取到 {len(videos)} 个视频')
    print(f'  最新视频: {videos[0][\"title\"]}')

print('\\n所有测试通过!')
"
```


### 性能测试

**测试目标**：
- 50个UP主的视频列表获取时间 < 5分钟
- WBI密钥缓存生效（避免重复获取）
- 请求间隔可控（1-2秒）

**测试代码**：

```python
import time

start = time.time()

ups = client.get_followed_ups(max_count=50)
for up in ups:
    videos = client.get_up_videos(up['mid'], page=1)
    time.sleep(1)  # 控制频率

elapsed = time.time() - start
print(f"耗时: {elapsed:.1f}秒")
assert elapsed < 300  # 5分钟
```


## Performance Optimization

### 1. WBI密钥缓存

```python
# 类属性缓存
_wbi_img_cache: Optional[WbiImg] = None
_wbi_cache_time: float = 0

def _get_wbi_keys(self, use_cache: bool = True) -> tuple[str, str]:
    # 缓存有效期10分钟
    if use_cache and self._wbi_img_cache:
        if time.time() - self._wbi_cache_time < 600:
            return self._wbi_img_cache["img_key"], self._wbi_img_cache["sub_key"]

    # 重新获取
    ...
    self._wbi_img_cache = wbi_img
    self._wbi_cache_time = time.time()
    return img_key, sub_key
```


### 2. 请求间隔控制

```python
import time

_last_request_time: float = 0
_request_interval: float = 1.0  # 1秒间隔

def _make_request(self, url: str, params: dict = None) -> dict:
    # 控制请求频率
    elapsed = time.time() - self._last_request_time
    if elapsed < self._request_interval:
        time.sleep(self._request_interval - elapsed)

    response = requests.get(...)
    self._last_request_time = time.time()
    return response.json()["data"]
```


### 3. 批量请求优化

```python
# 使用会话复用连接
self.session = requests.Session()
self.session.headers.update(headers)

# 批量请求时复用session
def get_up_videos_batch(self, up_ids: list[int]) -> dict[int, list]:
    results = {}
    for up_id in up_ids:
        results[up_id] = self.get_up_videos(up_id)
        time.sleep(1)
    return results
```


## Security Considerations

### 1. Cookie安全

- Cookie文件权限设为 `0o600`（仅所有者可读写）
- 日志中不打印完整Cookie值
- 使用HTTPS传输

### 2. 请求安全

- 验证API返回的域名
- 不执行重定向到外部域名
- 超时设置（避免长时间阻塞）


## Monitoring & Alerting

### 监控指标

- API调用成功率
- 平均响应时间
- WBI签名失败次数
- Cookie过期告警

### 日志记录

```python
# 结构化日志
{
    "timestamp": "2026-08-02T15:30:00Z",
    "level": "INFO",
    "api": "get_followed_ups",
    "duration_ms": 234,
    "result_count": 50
}
```


## Deployment Considerations

### 配置项

```yaml
# config/settings.yaml
bilibili:
  api:
    request_interval: 1.0      # 请求间隔（秒）
    max_retries: 3             # 最大重试次数
    timeout: 10                # 请求超时（秒）
    wbi_cache_ttl: 600         # WBI缓存时间（秒）
```


## References

- yutto项目源码：https://github.com/yutto-dev/yutto
- WBI签名实现：https://github.com/yutto-dev/yutto/blob/main/src/yutto/api/user_info.py
- B站API文档（非官方）：https://github.com/SocialSisterYi/bilibili-API-collect
