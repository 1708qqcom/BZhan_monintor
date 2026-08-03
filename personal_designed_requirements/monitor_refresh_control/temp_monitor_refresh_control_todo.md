# Implementation Todo

## Preparation

- [ ] 确认开发环境正常（Python 3.10+, FastAPI 已安装）
- [ ] 确认现有监控系统运行正常
- [ ] 确认测试数据库可用

## Development Tasks

### Task 1: 修改 scheduler.py 添加触发机制

**文件**: `src/scheduler.py`

**步骤**:

1. 在 `__init__` 方法中添加三个属性：
   ```python
   self._trigger_event = threading.Event()
   self._is_checking = False
   self._check_lock = threading.Lock()
   ```

2. 修改 `start()` 方法的等待逻辑：
   - 将 `time.sleep(self.check_interval)` 改为 `self._trigger_event.wait(timeout=self.check_interval)`
   - 触发后调用 `self._trigger_event.clear()`

3. 修改 `run_monitor_cycle()` 方法：
   - 在方法开头添加状态锁：
     ```python
     with self._check_lock:
         if self._is_checking:
             return
         self._is_checking = True
     ```
   - 在 `finally` 块中清除状态：
     ```python
     finally:
         with self._check_lock:
             self._is_checking = False
     ```
   - 修改 `_notify_state_change()` 调用，传递 `is_checking` 参数

4. 添加 `trigger_refresh()` 方法：
   ```python
   def trigger_refresh(self) -> bool:
       with self._check_lock:
           if self._is_checking:
               return False
       self._trigger_event.set()
       return True
   ```

**验收**:
- 调度器正常启动和运行
- `trigger_refresh()` 可以打断等待
- 检查状态正确更新

---

### Task 2: 修改 web.py 添加刷新 API

**文件**: `src/web.py`

**步骤**:

1. 在 `_on_state_change()` 函数中更新：
   ```python
   def _on_state_change(**kwargs):
       global _monitor_state
       _monitor_state.update(kwargs)
       _monitor_state["error_message"] = None
       if "is_checking" not in kwargs:
           _monitor_state["is_checking"] = False
   ```

2. 在监控状态端点下方添加新端点：
   ```python
   @app.post(
       "/api/monitor/refresh",
       tags=["监控"],
       summary="手动触发刷新",
       ...
   )
   async def trigger_monitor_refresh():
       scheduler = _monitor_state.get("scheduler")
       if not scheduler:
           raise HTTPException(status_code=400, detail="监控调度器未运行")
       
       success = scheduler.trigger_refresh()
       if not success:
           raise HTTPException(status_code=409, detail="正在检查中，请稍后")
       
       return {"message": "已触发刷新", "triggered": True}
   ```

**验收**:
- `POST /api/monitor/refresh` 返回正确响应
- 未启动时返回 400
- 检查中时返回 409

---

### Task 3: 修改 ups.html 添加 UI 元素

**文件**: `templates/ups.html`

**步骤**:

1. 修改页面标题区域（第 8-19 行），添加时间显示和刷新按钮：
   - 在标题下方添加 `<p id="monitor-status-text">加载中...</p>`
   - 在"添加UP主"按钮左侧添加刷新按钮

2. 在 JavaScript 块中添加 `loadMonitorStatus()` 函数：
   - 调用 `/api/monitor/status`
   - 根据 `next_check_time` 计算剩余分钟数
   - 更新状态文本

3. 添加 `triggerRefresh()` 函数：
   - 禁用按钮，显示"刷新中..."
   - 调用 `POST /api/monitor/refresh`
   - 显示成功/失败提示
   - 5 秒后重新加载状态

4. 修改 `DOMContentLoaded` 处理：
   - 调用 `loadMonitorStatus()`
   - 设置 30 秒定时刷新
   - 绑定刷新按钮点击事件

**验收**:
- 页面显示下次刷新时间
- 时间每 30 秒更新
- 点击按钮触发刷新

---

### Task 4: 测试验证

**步骤**:

1. 启动 Web 服务，访问 `/ups` 页面
2. 验证时间显示正确
3. 点击刷新按钮，验证：
   - 按钮状态变化
   - 成功提示显示
   - 时间更新
4. 验证错误场景：
   - 监控未启动时的提示
   - 快速点击按钮不重复触发

---

## Testing Tasks

### Unit Tests

- [ ] 测试 `scheduler.trigger_refresh()` 成功返回 True
- [ ] 测试 `scheduler.trigger_refresh()` 检查中返回 False
- [ ] 测试 `/api/monitor/refresh` API 响应

### Integration Tests

- [ ] 测试完整触发流程：API → scheduler → 执行检查
- [ ] 测试并发触发：多个请求同时触发

### Manual Tests

- [ ] 页面加载时时间显示正确
- [ ] 点击刷新按钮后状态正确
- [ ] 监控未启动时正确提示
- [ ] 时间每 30 秒自动更新

---

## Completion Checklist

### 功能完整性

- [ ] 下次刷新时间显示在 `/ups` 页面
- [ ] 时间格式正确（"X分钟后" 或 "即将刷新..."）
- [ ] 点击刷新按钮可触发后端
- [ ] 按钮状态正确切换（正常/刷新中/禁用）
- [ ] 操作结果有明确提示

### 错误处理

- [ ] 监控未启动时正确提示
- [ ] 正在检查时返回 409
- [ ] 网络错误时显示错误提示
- [ ] 快速点击不会重复触发

### 代码质量

- [ ] 线程安全（使用 Lock 保护状态）
- [ ] 日志记录完整
- [ ] 代码符合项目风格

### 文档更新

- [ ] API 文档更新（如有）
- [ ] README 更新（如有需要）