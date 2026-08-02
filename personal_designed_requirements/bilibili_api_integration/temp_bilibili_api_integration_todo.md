# Implementation Todo - B站API集成

## Preparation

### 环境准备
- [x] Python 3.10+ 环境已就绪
- [x] 依赖已安装（requests、pyyaml）
- [x] Cookie已保存（config/bilibili_cookies.json）
- [x] 配置文件已生成（config/settings.yaml）

### 代码准备
- [x] 创建 src/bilibili.py 文件（已存在，需实现）
- [x] 创建 src/login.py 文件（已完成）
- [ ] 创建异常类定义（可选，建议添加）

### 文档准备
- [x] 阅读yutto项目源码
- [x] 理解WBI签名算法
- [x] 确认API接口文档


## Development Tasks

### Task 1: WBI签名实现（核心）

**优先级**: P0
**预估时间**: 1小时

**子任务**:

- [ ] 实现 `_get_wbi_keys()` 方法
  ```python
  def _get_wbi_keys(self) -> tuple[str, str]:
      # 1. 调用 USER_INFO_API
      # 2. 解析响应，提取 img_url 和 sub_url
      # 3. 从URL提取密钥（文件名部分）
      # 4. 返回 (img_key, sub_key)
  ```

- [ ] 实现混淆密钥生成函数
  ```python
  def _get_mixin_key(string: str) -> str:
      # 按固定索引表提取32位字符
      char_indices = [46, 47, 18, 2, 53, 8, 23, 32, ...]
      return "".join([string[idx] for idx in char_indices[:32]])
  ```

- [ ] 实现 `_encode_wbi()` 方法
  ```python
  def _encode_wbi(self, params: dict, img_key: str, sub_key: str) -> dict:
      # 1. 生成混淆密钥
      # 2. 添加时间戳 wts
      # 3. 添加反爬参数 dm_img_str、dm_cover_img_str
      # 4. 参数排序、移除非法字符
      # 5. 计算MD5签名
      # 6. 添加 w_rid 参数
  ```

- [ ] 实现WBI缓存机制
  ```python
  # 类属性缓存
  _wbi_img_cache: Optional[WbiImg] = None
  _wbi_cache_time: float = 0

  # 在 _get_wbi_keys() 中检查缓存
  if self._wbi_img_cache and time.time() - self._wbi_cache_time < 600:
      return cached_keys
  ```

**验收标准**:
- [ ] WBI签名生成的参数包含 `wts` 和 `w_rid`
- [ ] `w_rid` 为32位MD5字符串
- [ ] 缓存机制正常工作（10分钟有效期）
- [ ] 使用真实Cookie测试签名通过


### Task 2: HTTP请求封装

**优先级**: P0
**预估时间**: 30分钟

**子任务**:

- [ ] 实现 `_make_request()` 方法
  ```python
  def _make_request(self, url: str, params: dict = None, retry: int = 3) -> dict:
      # 1. 构造Cookie请求头
      # 2. 发送GET请求（超时10秒）
      # 3. 检查HTTP状态码
      # 4. 解析JSON响应
      # 5. 检查API返回码（code字段）
      # 6. 错误重试（指数退避）
  ```

- [ ] 实现请求头构造
  ```python
  HEADERS = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
      "Referer": "https://www.bilibili.com",
      "Cookie": self._build_cookie_string()
  }
  ```

- [ ] 实现重试机制
  ```python
  for attempt in range(retry):
      try:
          response = requests.get(...)
          return response.json()["data"]
      except requests.RequestException:
          if attempt < retry - 1:
              time.sleep(2 ** attempt)  # 1, 2, 4秒
          else:
              raise
  ```

- [ ] 实现请求间隔控制（可选）
  ```python
  # 控制请求频率，避免限流
  elapsed = time.time() - self._last_request_time
  if elapsed < 1.0:
      time.sleep(1.0 - elapsed)
  ```

**验收标准**:
- [ ] 成功发送GET请求并返回JSON数据
- [ ] 网络错误时自动重试（最多3次）
- [ ] API错误时抛出明确异常
- [ ] 请求超时正常处理


### Task 3: Cookie有效性检查

**优先级**: P0
**预估时间**: 15分钟

**子任务**:

- [ ] 实现 `check_cookie_valid()` 方法（已在login.py中实现，可复用）
  ```python
  def check_cookie_valid(self) -> bool:
      # 1. 检查cookies是否为空
      # 2. 调用 USER_INFO_API
      # 3. 检查返回码是否为0
      # 4. 返回有效性布尔值
  ```

**验收标准**:
- [ ] 有效Cookie返回True
- [ ] 无效Cookie返回False
- [ ] 网络错误时抛出异常


### Task 4: 获取关注列表

**优先级**: P0
**预估时间**: 45分钟

**子任务**:

- [ ] 实现 `get_followed_ups()` 方法
  ```python
  def get_followed_ups(self, page: int = 1, page_size: int = 50, max_count: int = 50) -> list[dict]:
      # 1. 构造请求参数
      params = {
          "vmid": self.user_id,  # 从Cookie中的DedeUserID获取
          "pn": page,
          "ps": page_size,
          "order": "desc"  # 按关注时间倒序
      }

      # 2. 调用 FOLLOWINGS_API
      data = self._make_request(FOLLOWINGS_API, params)

      # 3. 解析返回数据
      ups = [
          {
              "mid": item["mid"],
              "uname": item["uname"],
              "face": item["face"],
              "sign": item["sign"]
          }
          for item in data["list"]
      ]

      # 4. 分页逻辑（如果需要）
      if len(ups) >= page_size and len(all_ups) < max_count:
          ups += self.get_followed_ups(page + 1, page_size, max_count)

      # 5. 截取前max_count个
      return ups[:max_count]
  ```

- [ ] 实现用户ID提取
  ```python
  @property
  def user_id(self) -> str:
      return self.cookies.get("DedeUserID", "")
  ```

**验收标准**:
- [ ] 成功返回UP主列表
- [ ] 列表包含 `mid`、`uname`、`face` 字段
- [ ] 分页逻辑正确
- [ ] 最多返回 `max_count` 个UP主


### Task 5: 获取UP主视频列表

**优先级**: P0
**预估时间**: 1小时

**子任务**:

- [ ] 实现 `get_up_videos()` 方法
  ```python
  def get_up_videos(self, up_id: int, page: int = 1, page_size: int = 30) -> list[dict]:
      # 1. 获取WBI密钥
      img_key, sub_key = self._get_wbi_keys()

      # 2. 构造请求参数
      params = {
          "mid": up_id,
          "ps": page_size,
          "tid": 0,
          "pn": page,
          "order": "pubdate",  # 按发布时间排序
      }

      # 3. WBI签名
      params = self._encode_wbi(params, img_key, sub_key)

      # 4. 调用 SPACE_SEARCH_API
      data = self._make_request(SPACE_SEARCH_API, params)

      # 5. 解析返回数据
      videos = [
          {
              "aid": item["aid"],
              "bvid": item["bvid"],
              "title": item["title"],
              "pic": item["pic"],
              "pubdate": item["pubdate"],
              "play": item["play"],
              "video_review": item["video_review"]
          }
          for item in data["list"]["vlist"]
      ]

      return videos
  ```

- [ ] 添加反爬参数生成（可选）
  ```python
  import random
  import string
  import base64

  dm_img_str = base64.b64encode(
      "".join(random.choices(string.printable, k=random.randint(16, 64))).encode()
  )[:-2].decode()
  ```

**验收标准**:
- [ ] WBI签名正确，API返回成功
- [ ] 返回视频列表包含 `aid`、`title`、`pubdate` 等字段
- [ ] 视频按发布时间倒序排列
- [ ] 签名失败时能重试


### Task 6: 获取视频详情

**优先级**: P1（可选）
**预估时间**: 20分钟

**子任务**:

- [ ] 实现 `get_video_info()` 方法
  ```python
  def get_video_info(self, aid: int) -> dict:
      params = {"aid": aid}
      data = self._make_request(VIDEO_INFO_API, params)

      return {
          "aid": data["aid"],
          "bvid": data["bvid"],
          "title": data["title"],
          "description": data["desc"],
          "pic": data["pic"],
          "pubdate": data["pubdate"],
          "owner": {
              "mid": data["owner"]["mid"],
              "name": data["owner"]["name"]
          },
          "stat": {
              "view": data["stat"]["view"],
              "like": data["stat"]["like"],
              "coin": data["stat"]["coin"]
          }
      }
  ```

**验收标准**:
- [ ] 成功返回视频详细信息
- [ ] 包含UP主信息和统计数据


### Task 7: 异常处理与日志

**优先级**: P1
**预估时间**: 30分钟

**子任务**:

- [ ] 定义异常类
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
  ```

- [ ] 添加日志记录
  ```python
  import logging

  logger = logging.getLogger("monitor.bilibili")

  # 在关键位置添加日志
  logger.info(f"获取关注列表成功，共 {len(ups)} 个UP主")
  logger.error(f"API调用失败: {url}, 错误: {e}")
  logger.warning(f"WBI签名失败，重新获取密钥")
  ```

**验收标准**:
- [ ] 异常类定义清晰
- [ ] 关键操作有日志记录
- [ ] 错误信息明确


### Task 8: 集成到main.py

**优先级**: P1
**预估时间**: 20分钟

**子任务**:

- [ ] 修改 `start_monitor()` 函数
  ```python
  def start_monitor(config: dict) -> None:
      # 1. 加载Cookie
      from src.login import BilibiliLogin
      login = BilibiliLogin()
      cookies = login.load_cookies()

      if not cookies:
          print("请先运行 'python main.py --login' 完成登录")
          return

      # 2. 初始化客户端
      from src.bilibili import BilibiliClient
      client = BilibiliClient(cookies)

      # 3. 验证Cookie
      if not client.check_cookie_valid():
          print("Cookie已过期，请重新登录")
          return

      # 4. 测试API调用
      print("正在获取关注列表...")
      ups = client.get_followed_ups(max_count=10)
      print(f"获取到 {len(ups)} 个UP主")

      if ups:
          print("正在获取视频列表...")
          videos = client.get_up_videos(ups[0]["mid"], page=1, page_size=5)
          print(f"获取到 {len(videos)} 个视频")

      # TODO: 启动调度器
  ```

**验收标准**:
- [ ] `python main.py` 能成功获取关注列表
- [ ] 能成功获取视频列表
- [ ] 错误提示清晰


## Testing Tasks

### 单元测试

- [ ] 测试WBI签名生成
  ```python
  def test_wbi_sign():
      client = BilibiliClient({})
      img_key, sub_key = client._get_wbi_keys()
      params = {"mid": 123456}
      signed = client._encode_wbi(params, img_key, sub_key)
      assert "wts" in signed
      assert "w_rid" in signed
  ```

- [ ] 测试获取关注列表
  ```python
  def test_get_followed_ups():
      client = BilibiliClient(test_cookies)
      ups = client.get_followed_ups(max_count=10)
      assert len(ups) > 0
      assert "mid" in ups[0]
  ```

- [ ] 测试获取视频列表
  ```python
  def test_get_up_videos():
      client = BilibiliClient(test_cookies)
      videos = client.get_up_videos(up_id=123456)
      assert len(videos) > 0
      assert "aid" in videos[0]
  ```

- [ ] 测试错误处理
  ```python
  def test_cookie_expired():
      client = BilibiliClient(invalid_cookies)
      with pytest.raises(CookieExpiredError):
          client.check_cookie_valid()
  ```


### 集成测试

- [ ] 完整流程测试
  ```bash
  python -c "
  from src.login import BilibiliLogin
  from src.bilibili import BilibiliClient

  login = BilibiliLogin()
  cookies = login.load_cookies()
  client = BilibiliClient(cookies)

  # 测试完整流程
  assert client.check_cookie_valid()
  ups = client.get_followed_ups(max_count=10)
  videos = client.get_up_videos(ups[0]['mid'])

  print('✓ 所有测试通过')
  "
  ```


### 性能测试

- [ ] 测试50个UP主获取时间
  ```python
  import time
  start = time.time()

  ups = client.get_followed_ups(max_count=50)
  for up in ups:
      client.get_up_videos(up['mid'])
      time.sleep(1)

  elapsed = time.time() - start
  print(f"耗时: {elapsed:.1f}秒")
  assert elapsed < 300  # < 5分钟
  ```


## Completion Checklist

### 功能检查

- [ ] Cookie有效性检查正常工作
- [ ] 成功获取关注列表（包含mid、uname、face）
- [ ] 成功获取UP主视频列表（包含aid、title、pubdate）
- [ ] WBI签名算法正确实现
- [ ] 分页逻辑正确
- [ ] 错误处理完善（重试、日志、告警）


### 代码质量检查

- [ ] 代码符合项目规范（中文注释、英文代码）
- [ ] 异常处理完善
- [ ] 日志记录清晰
- [ ] 无硬编码（配置项可调整）
- [ ] 函数有完整docstring


### 测试检查

- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 性能测试达标（50个UP主 < 5分钟）


### 文档检查

- [ ] 更新 README.md（如有必要）
- [ ] 更新 CHANGELOG-monitor_onlineVideo.md
- [ ] 更新 TODO-monitor_onlineVideo.md（标记完成项）


### Git提交检查

- [ ] 提交信息清晰
- [ ] 不包含敏感信息（Cookie等）
- [ ] 代码已通过review


## Next Steps

完成本功能后，后续任务：

1. **实现飞书推送** (src/feishu.py)
   - 构造消息卡片格式
   - 发送Webhook请求

2. **实现定时调度** (src/scheduler.py)
   - 加载/保存历史记录
   - 新视频检测逻辑
   - 监控循环（30分钟间隔）

3. **SQLite数据库集成**
   - 创建数据库表结构
   - 数据库连接管理
   - CRUD操作封装


## Notes

- yutto项目源码：https://github.com/yutto-dev/yutto
- WBI签名参考：`src/yutto/api/user_info.py`
- HTTP封装参考：`src/yutto/utils/fetcher.py`
- B站API文档（非官方）：https://github.com/SocialSisterYi/bilibili-API-collect
