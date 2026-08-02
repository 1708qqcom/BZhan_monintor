# Implementation Todo - 定时调度功能

## Preparation

- [x] 需求确认完成
- [x] 技术方案设计完成
- [ ] 阅读现有 `src/scheduler.py` 代码框架

## Development Tasks

### Task 1: 实现历史记录管理方法

**文件**：`src/scheduler.py`

**任务清单**：

- [ ] 实现 `load_history()` 方法
  - 检查文件是否存在
  - 读取 JSON 内容
  - 捕获 JSONDecodeError 异常
  - 异常时初始化空结构

- [ ] 实现 `save_history()` 方法
  - 创建父目录（`Path.parent.mkdir(parents=True, exist_ok=True)`）
  - 写入 JSON 文件（`ensure_ascii=False, indent=2`）
  - 更新 `updated_at` 字段

- [ ] 实现 `cleanup_old_records()` 方法
  - 遍历 `self.video_history["videos"]`
  - 解析每条记录的 `pushed_at` 时间
  - 计算与当前时间的天数差
  - 删除超过 `self.history_retention_days` 的记录
  - 记录清理日志

### Task 2: 实现辅助方法

**文件**：`src/scheduler.py`

**任务清单**：

- [ ] 实现 `_record_video()` 方法
  - 构造视频记录字典
  - 写入 `self.video_history["videos"][bvid]`
  - 设置 `pushed` 标志

- [ ] 实现 `_push_video()` 方法
  - 构造视频 URL（`https://www.bilibili.com/video/{bvid}`）
  - 格式化发布时间
  - 调用 `self.feishu.send_new_video_notification()`
  - 返回成功/失败状态

### Task 3: 实现新视频检测

**文件**：`src/scheduler.py`

**任务清单**：

- [ ] 实现 `check_new_videos()` 方法
  - 调用 `self.bilibili.get_up_videos(up_id, page=1, page_size=5)`
  - 遍历视频列表
  - 检查 bvid 是否在 `self.video_history["videos"]` 中
  - 收集新视频并返回

### Task 4: 实现监控循环

**文件**：`src/scheduler.py`

**任务清单**：

- [ ] 实现 `run_monitor_cycle()` 方法
  - 验证 Cookie 有效性
  - 获取关注列表（`max_count=self.max_ups`）
  - 遍历 UP 主列表
    - 调用 `check_new_videos()`
    - 首次运行标记（检查 `len(self.video_history["videos"]) == 0`）
    - 非首次运行：推送新视频
    - 调用 `_record_video()` 记录
  - 调用 `cleanup_old_records()`
  - 调用 `save_history()`
  - 异常处理：
    - CookieExpiredError 向上抛出
    - 其他异常记录日志继续

### Task 5: 实现信号处理和主循环

**文件**：`src/scheduler.py`

**任务清单**：

- [ ] 导入 signal 模块
- [ ] 实现 `_graceful_shutdown()` 方法
  - 记录退出日志
  - 调用 `save_history()`
  - 调用 `sys.exit(0)`

- [ ] 实现 `start()` 方法
  - 调用 `load_history()`
  - 注册信号处理器：`signal.signal(signal.SIGINT, self._graceful_shutdown)`
  - 记录启动日志
  - `while True:` 循环
    - `try: run_monitor_cycle()`
    - `except CookieExpiredError: break`
    - `except Exception: 记录日志，飞书告警`
    - `time.sleep(self.check_interval)`

### Task 6: 集成到主程序

**文件**：`main.py`

**任务清单**：

- [ ] 修改 `start_monitor()` 函数
  - 删除测试代码（API 调用、飞书推送测试）
  - 初始化 `MonitorScheduler`
  - 传入配置参数
  - 调用 `scheduler.start()`

- [ ] 更新导入语句
  - 在文件顶部添加 `from src.scheduler import MonitorScheduler`
  - 或在函数内部导入（延迟导入）

### Task 7: 配置参数支持

**文件**：`config/settings.yaml`（已存在，无需修改）

**确认配置项**：

- [x] `monitor.check_interval_minutes` - 检查间隔
- [x] `monitor.max_follows_to_check` - 最多监控UP主数

**调度器新增参数**（硬编码）：

- `history_retention_days: 180` - 历史保留天数

## Testing Tasks

### Task 8: 编写单元测试

**文件**：`tests/test_scheduler.py`

**任务清单**：

- [ ] 创建测试文件
- [ ] 测试 `load_history()` 空文件场景
- [ ] 测试 `load_history()` 损坏文件场景
- [ ] 测试 `save_history()` 写入正确
- [ ] 测试 `cleanup_old_records()` 清理逻辑
- [ ] 测试 `check_new_videos()` 识别新视频

### Task 9: 手动集成测试

**测试清单**：

- [ ] 启动服务：`python main.py`
- [ ] 观察日志输出，确认第一个监控循环完成
- [ ] 检查 `data/video_history.json` 内容
- [ ] 等待第二个循环（或修改间隔为1分钟测试）
- [ ] 按 Ctrl+C，验证退出行为
- [ ] 重新启动，验证历史加载正常

## Completion Checklist

### 功能完成

- [ ] 调度器能够启动并进入监控循环
- [ ] 历史记录正确加载和保存
- [ ] 新视频检测逻辑正确
- [ ] 飞书推送正常工作
- [ ] 首次运行只记录不推送
- [ ] 历史记录清理功能正常
- [ ] Ctrl+C 优雅退出

### 代码质量

- [ ] 日志输出清晰（INFO/WARNING/ERROR 级别合理）
- [ ] 异常处理完善
- [ ] 代码符合项目风格（注释、命名）

### 文档更新

- [ ] TODO 文件中该功能标记为完成
- [ ] Changelog 记录版本更新

### 测试通过

- [ ] 单元测试通过
- [ ] 手动测试通过