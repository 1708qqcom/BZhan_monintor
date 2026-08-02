# Technical Design - 定时调度功能

## Overview

实现 `MonitorScheduler` 类的完整方法，协调 BilibiliClient 和 FeishuNotifier 完成定时监控流程。

调度器采用同步阻塞模式，通过 `while True` 循环 + `time.sleep()` 实现定时调度。

## Architecture

### 模块依赖关系

```
main.py
  │
  └─ start_monitor()
       │
       └─ MonitorScheduler
            ├─ BilibiliClient (已完成)
            │    ├─ check_cookie_valid()
            │    ├─ get_followed_ups()
            │    └─ get_up_videos()
            │
            ├─ FeishuNotifier (已完成)
            │    ├─ send_new_video_notification()
            │    └─ send_error_notification()
            │
            └─ video_history.json
                 ├─ load_history()
                 ├─ save_history()
                 └─ cleanup_old_records()
```

### 调用流程

```
main.py: start_monitor()
    │
    ├─ 初始化 BilibiliClient
    ├─ 初始化 FeishuNotifier
    ├─ 初始化 MonitorScheduler
    │
    └─ scheduler.start()  ← 进入调度循环
         │
         ├─ load_history()
         │
         └─ while True:
              ├─ run_monitor_cycle()
              │    ├─ check_cookie_valid()
              │    ├─ get_followed_ups()
              │    ├─ for each UP:
              │    │    ├─ get_up_videos()
              │    │    ├─ check_new_videos()
              │    │    ├─ send_new_video_notification() (如果有新视频)
              │    │    └─ _record_video()
              │    ├─ cleanup_old_records()
              │    └─ save_history()
              │
              └─ time.sleep(check_interval)
```

## Data Model

### 历史记录文件结构

**文件路径**：`data/video_history.json`

**数据结构**：

```json
{
  "videos": {
    "{bvid}": {
      "title": "视频标题",
      "up_id": 123456,
      "up_name": "UP主名称",
      "pub_time": "2026-08-02 14:30:00",
      "pushed_at": "2026-08-02 14:35:00",
      "pushed": true
    }
  },
  "updated_at": "2026-08-02 14:35:00"
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| videos | dict | 以 bvid 为 key 的视频记录字典 |
| title | str | 视频标题 |
| up_id | int | UP主ID |
| up_name | str | UP主名称 |
| pub_time | str | 视频发布时间（ISO格式） |
| pushed_at | str | 推送时间（ISO格式） |
| pushed | bool | 是否已推送（首次运行为 false） |
| updated_at | str | 最后更新时间 |

### 内存结构

`MonitorScheduler.video_history` 直接映射 JSON 结构：

```python
self.video_history: dict = {
    "videos": {},
    "updated_at": ""
}
```

## API / Interface

### MonitorScheduler 类接口

```python
class MonitorScheduler:
    def __init__(
        self,
        bilibili_client,
        feishu_notifier,
        history_file: str = "data/video_history.json",
        check_interval_minutes: int = 30,
        max_ups: int = 50,
        history_retention_days: int = 180
    ):
        """
        初始化调度器

        Args:
            bilibili_client: B站API客户端实例
            feishu_notifier: 飞书推送器实例（可为None）
            history_file: 历史记录文件路径
            check_interval_minutes: 检查间隔（分钟）
            max_ups: 最多监控UP主数量
            history_retention_days: 历史记录保留天数
        """

    def load_history(self) -> None:
        """加载历史记录，文件不存在或损坏时初始化空结构"""

    def save_history(self) -> None:
        """保存历史记录到JSON文件"""

    def cleanup_old_records(self) -> None:
        """清理超过保留期的历史记录"""

    def check_new_videos(self, up_id: int, up_name: str) -> list[dict]:
        """
        检查UP主的新视频

        Args:
            up_id: UP主ID
            up_name: UP主名称

        Returns:
            新视频列表（未推送过的视频）
        """

    def run_monitor_cycle(self) -> None:
        """
        执行一次监控循环

        流程：
        1. 验证Cookie
        2. 获取关注列表
        3. 遍历检查新视频
        4. 推送通知
        5. 清理历史
        6. 保存记录

        Raises:
            CookieExpiredError: Cookie过期
        """

    def start(self) -> None:
        """
        启动定时监控

        无限循环执行监控任务
        """

    def _record_video(self, up_id: int, up_name: str, video: dict, pushed: bool) -> None:
        """记录视频到历史"""

    def _push_video(self, up_name: str, video: dict) -> bool:
        """推送单个视频通知"""

    def _graceful_shutdown(self, signum, frame) -> None:
        """信号处理器：优雅退出"""
```

## Frontend Changes

无前端变更（Web管理后台将在后续 P1 阶段实现）。

## Backend Changes

### 文件：src/scheduler.py

**当前状态**：类框架已定义，所有方法抛出 `NotImplementedError`

**修改内容**：实现所有方法

**关键实现**：

1. **load_history()**
   - 检查文件存在性
   - JSON 解析，捕获异常
   - 损坏时初始化空结构

2. **save_history()**
   - 创建父目录（如果不存在）
   - 写入 JSON，ensure_ascii=False，indent=2

3. **cleanup_old_records()**
   - 遍历 videos 字典
   - 解析 pushed_at 时间
   - 计算与当前时间的差值
   - 删除超过 180 天的记录

4. **check_new_videos()**
   - 调用 `bilibili.get_up_videos(up_id, page=1, page_size=5)`
   - 过滤已存在 bvid

5. **run_monitor_cycle()**
   - 核心流程编排
   - 异常处理隔离

6. **start()**
   - 加载历史
   - 注册信号处理器（signal.signal）
   - while True 循环
   - 捕获 Ctrl+C 保存退出

### 文件：main.py

**修改位置**：`start_monitor()` 函数

**当前代码**：
```python
# TODO: 启动调度器
print("\n提示: 定时调度功能将在后续版本实现")
```

**修改为**：
```python
# 初始化调度器
from src.scheduler import MonitorScheduler

scheduler = MonitorScheduler(
    bilibili_client=client,
    feishu_notifier=notifier,
    history_file="data/video_history.json",
    check_interval_minutes=config.get('monitor', {}).get('check_interval_minutes', 30),
    max_ups=config.get('monitor', {}).get('max_follows_to_check', 50),
    history_retention_days=180
)

# 启动调度器（阻塞运行）
scheduler.start()
```

## File Changes

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/scheduler.py` | 重写 | 实现所有方法 |
| `main.py` | 修改 | 集成调度器到 start_monitor() |
| `data/video_history.json` | 运行时写入 | 历史记录存储 |

## Implementation Flow

### Step 1: 实现历史记录管理

1. 实现 `load_history()`
2. 实现 `save_history()`
3. 实现 `cleanup_old_records()`

### Step 2: 实现新视频检测

1. 实现 `check_new_videos()`
2. 实现 `_record_video()` 辅助方法

### Step 3: 实现监控循环

1. 实现 `_push_video()` 辅助方法
2. 实现 `run_monitor_cycle()`

### Step 4: 实现定时调度

1. 实现 `_graceful_shutdown()` 信号处理
2. 实现 `start()` 主循环

### Step 5: 集成到主程序

1. 修改 `main.py` 的 `start_monitor()` 函数
2. 传入配置参数
3. 启动调度器

## Error Handling

### CookieExpiredError

**触发场景**：`check_cookie_valid()` 返回 False

**处理流程**：
```python
if not self.bilibili.check_cookie_valid():
    error_msg = "Cookie已过期，请重新登录"
    logger.error(error_msg)
    if self.feishu:
        self.feishu.send_error_notification(error_msg)
    raise CookieExpiredError(error_msg)
```

**结果**：异常向上传播到 `start()` 方法，退出循环，程序终止。

### 单个UP主检查失败

**触发场景**：`get_up_videos()` 抛出异常

**处理流程**：
```python
try:
    new_videos = self.check_new_videos(up_id, up_name)
    # ...
except Exception as e:
    logger.error(f"检查UP主 {up_name} (mid={up_id}) 失败: {e}")
    continue  # 继续下一个UP主
```

**结果**：跳过该UP主，继续检查其他UP主。

### 历史文件损坏

**触发场景**：`json.load()` 抛出异常

**处理流程**：
```python
try:
    with open(self.history_file, 'r', encoding='utf-8') as f:
        self.video_history = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logger.warning(f"加载历史记录失败: {e}，将初始化空记录")
    self.video_history = {"videos": {}, "updated_at": ""}
```

**结果**：重新初始化，相当于首次运行。

### 飞书推送失败

**触发场景**：`send_new_video_notification()` 返回 False

**处理流程**：
```python
success = self._push_video(up_name, video)
if not success:
    logger.warning(f"视频推送失败: {video['title']}")
# 继续记录到历史（即使推送失败）
```

**结果**：记录日志，继续流程，不中断调度。

### 用户中断 (Ctrl+C)

**触发场景**：SIGINT 信号

**处理流程**：
```python
def _graceful_shutdown(self, signum, frame):
    logger.info("接收到退出信号，正在保存历史记录...")
    self.save_history()
    logger.info("历史记录已保存，程序退出")
    sys.exit(0)
```

**结果**：保存历史，正常退出。

## Testing Strategy

### 单元测试

**测试文件**：`tests/test_scheduler.py`

**测试用例**：

1. `test_load_history_empty` - 空文件初始化
2. `test_load_history_corrupted` - 损坏文件恢复
3. `test_save_history` - 正确保存
4. `test_cleanup_old_records` - 清理过期记录
5. `test_check_new_videos` - 新视频识别
6. `test_check_new_videos_no_new` - 无新视频
7. `test_record_video` - 记录写入

### 集成测试

**测试场景**：

1. 完整监控循环模拟（Mock API）
2. Cookie过期退出流程
3. Ctrl+C 信号处理

### 手动测试

1. 启动服务，观察日志输出
2. 等待第一个循环完成
3. 检查 `video_history.json` 内容
4. 按 Ctrl+C，验证退出行为
5. 重新启动，验证历史加载