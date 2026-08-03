# Technical Design

## Overview

在现有监控调度器架构上，通过 `threading.Event` 实现手动触发机制。前端新增时间显示和刷新按钮，复用现有 `/api/monitor/status` API 并新增 `/api/monitor/refresh` API。

## Architecture

### 系统影响范围

```
┌─────────────────────────────────────────────────────┐
│                   前端层                             │
│  templates/ups.html                                 │
│  - 新增: 下次刷新时间显示                            │
│  - 新增: 立即刷新按钮                                │
│  - 新增: loadMonitorStatus() 函数                   │
│  - 新增: triggerRefresh() 函数                      │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP
                       ▼
┌─────────────────────────────────────────────────────┐
│                   API 层                             │
│  src/web.py                                         │
│  - 现有: GET  /api/monitor/status                   │
│  - 新增: POST /api/monitor/refresh                  │
└──────────────────────┬──────────────────────────────┘
                       │ 函数调用
                       ▼
┌─────────────────────────────────────────────────────┐
│                 调度器层                             │
│  src/scheduler.py                                   │
│  - 新增: _trigger_event: threading.Event            │
│  - 新增: _is_checking: bool (受 Lock 保护)          │
│  - 新增: _check_lock: threading.Lock                │
│  - 修改: start() 主循环支持 Event 触发               │
│  - 新增: trigger_refresh() 方法                     │
└─────────────────────────────────────────────────────┘
```

### 数据流

```
用户点击刷新按钮
       │
       ▼
POST /api/monitor/refresh
       │
       ▼
scheduler.trigger_refresh()
       │
       ├─ 检查 _is_checking (需获取 Lock)
       │    ├─ True  → 返回 False (409 Conflict)
       │    └─ False → 设置 _trigger_event, 返回 True
       │
       ▼
主循环中 _trigger_event.wait() 被唤醒
       │
       ▼
执行 run_monitor_cycle()
       │
       ▼
_notify_state_change() 更新 _monitor_state
       │
       ▼
GET /api/monitor/status 返回最新时间
```

## Data Model

无数据库 schema 变化。

### 内存状态扩展

`src/web.py` 中的 `_monitor_state` 字典：

```python
_monitor_state = {
    "is_running": False,
    "last_check_time": None,
    "next_check_time": None,
    "check_interval_minutes": 10,
    "scheduler": None,
    "error_message": None,
    # 新增
    "is_checking": False,  # 当前是否正在执行检查
}
```

`src/scheduler.py` 中的 `MonitorScheduler` 类新增属性：

```python
class MonitorScheduler:
    def __init__(self, ...):
        # 现有属性...
        
        # 新增：手动触发机制
        self._trigger_event = threading.Event()
        self._is_checking = False
        self._check_lock = threading.Lock()
```

## API / Interface

### 现有 API（复用）

#### GET /api/monitor/status

```python
# 已有实现，响应结构不变
{
    "is_running": true,
    "last_check_time": "2026-08-03T10:00:00",
    "next_check_time": "2026-08-03T10:10:00",
    "check_interval_minutes": 10,
    "error_message": null
}
```

### 新增 API

#### POST /api/monitor/refresh

**功能**：手动触发立即刷新

**认证**：需要 Web 后台登录（不在白名单中）

**请求**：无请求体

**响应**：

```python
# 成功
{
    "message": "已触发刷新",
    "triggered": true
}

# 失败 - 正在检查中 (409 Conflict)
{
    "error": "Conflict",
    "detail": "正在检查中，请稍后"
}

# 失败 - 监控未运行 (400 Bad Request)
{
    "error": "Bad Request",
    "detail": "监控调度器未运行"
}
```

## Frontend Changes

### templates/ups.html

#### 修改位置 1：页面标题区域（第 8-19 行）

```html
<!-- 原有 -->
<div class="flex justify-between items-center">
    <div>
        <h1 class="text-2xl font-bold text-gray-900">UP主管理</h1>
        <p class="mt-1 text-sm text-gray-500">管理监控的UP主列表</p>
    </div>
    <button id="btn-add-up" ...>添加UP主</button>
</div>

<!-- 修改为 -->
<div class="flex justify-between items-center">
    <div>
        <h1 class="text-2xl font-bold text-gray-900">UP主管理</h1>
        <p class="mt-1 text-sm text-gray-500">管理监控的UP主列表</p>
        <p class="text-sm text-gray-400" id="monitor-status-text">加载中...</p>
    </div>
    <div class="flex items-center space-x-3">
        <!-- 新增：刷新按钮 -->
        <button
            id="btn-refresh-now"
            class="bg-white border border-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium flex items-center"
        >
            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m0 0H9"/>
            </svg>
            <span>立即刷新</span>
        </button>
        <!-- 原有：添加UP主按钮 -->
        <button id="btn-add-up" ...>添加UP主</button>
    </div>
</div>
```

#### 修改位置 2：JavaScript 脚本块

新增以下函数：

```javascript
/**
 * 加载监控状态
 */
async function loadMonitorStatus() {
    try {
        const status = await fetchAPI('/api/monitor/status');
        const statusEl = document.getElementById('monitor-status-text');
        
        if (status.is_running && status.next_check_time) {
            const nextTime = new Date(status.next_check_time);
            const now = new Date();
            const diffMinutes = Math.round((nextTime - now) / 60000);
            
            if (diffMinutes > 0) {
                statusEl.textContent = `下次刷新: ${diffMinutes}分钟后`;
                statusEl.className = 'text-sm text-gray-400';
            } else {
                statusEl.textContent = '即将刷新...';
                statusEl.className = 'text-sm text-green-500';
            }
        } else if (status.error_message) {
            statusEl.textContent = `状态异常: ${status.error_message}`;
            statusEl.className = 'text-sm text-red-500';
        } else {
            statusEl.textContent = '监控未启动';
            statusEl.className = 'text-sm text-yellow-600';
        }
    } catch (error) {
        console.error('[Ups] 加载监控状态失败:', error);
        document.getElementById('monitor-status-text').textContent = '获取状态失败';
    }
}

/**
 * 触发手动刷新
 */
async function triggerRefresh() {
    const btn = document.getElementById('btn-refresh-now');
    const btnContent = btn.querySelector('span');
    const originalText = btnContent.textContent;
    
    // 禁用按钮，显示加载状态
    btn.disabled = true;
    btnContent.textContent = '刷新中...';
    btn.classList.add('opacity-50', 'cursor-not-allowed');
    
    try {
        const response = await fetchAPI('/api/monitor/refresh', { method: 'POST' });
        showSuccess('已触发刷新，请稍后查看结果');
        
        // 5秒后重新加载状态
        setTimeout(loadMonitorStatus, 5000);
        
    } catch (error) {
        showError('刷新失败: ' + error.message);
    } finally {
        // 恢复按钮状态
        btn.disabled = false;
        btnContent.textContent = originalText;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
}
```

修改 `DOMContentLoaded` 事件处理：

```javascript
document.addEventListener('DOMContentLoaded', async function() {
    console.log('[Ups] 开始加载UP主列表');
    
    // 原有：加载UP主列表
    await loadUps();
    
    // 新增：加载监控状态
    await loadMonitorStatus();
    
    // 新增：定时刷新监控状态（每30秒）
    setInterval(loadMonitorStatus, 30000);
    
    // 原有：绑定事件
    bindEvents();
    
    // 新增：绑定刷新按钮
    document.getElementById('btn-refresh-now').addEventListener('click', triggerRefresh);
});
```

## Backend Changes

### src/scheduler.py

#### 新增属性

```python
import threading

class MonitorScheduler:
    def __init__(self, ...):
        # 现有属性...
        self._running = True
        
        # 新增：手动触发机制
        self._trigger_event = threading.Event()
        self._is_checking = False
        self._check_lock = threading.Lock()
```

#### 修改 start() 方法

```python
def start(self, skip_signals: bool = False) -> None:
    """启动定时监控（支持手动触发）"""
    logger.info("=" * 50)
    logger.info("监控调度器启动")
    logger.info("=" * 50)

    self.load_history()

    if not skip_signals:
        try:
            signal.signal(signal.SIGINT, self._graceful_shutdown)
            logger.debug("已注册 SIGINT 信号处理器")
        except ValueError as e:
            logger.warning(f"无法注册信号处理器: {e}")

    logger.info(f"监控间隔: {self.check_interval // 60} 分钟")
    logger.info(f"历史保留: {self.history_retention_days} 天")

    cycle_count = 0
    while self._running:
        cycle_count += 1
        logger.info(f"\n第 {cycle_count} 次监控循环")

        try:
            self.run_monitor_cycle()

        except CookieExpiredError:
            logger.error("Cookie已过期，请重新登录")
            if self.feishu:
                try:
                    self.feishu.send_error_notification("Cookie已过期，请重新登录")
                except Exception:
                    pass
            break

        except Exception as e:
            logger.error(f"监控循环异常: {e}")

        # 等待下一次循环，但可被手动触发打断
        if self._running:
            logger.info(f"等待 {self.check_interval // 60} 分钟后进行下次检查...")
            # 使用 Event.wait() 替代 time.sleep()
            triggered = self._trigger_event.wait(timeout=self.check_interval)
            if triggered:
                self._trigger_event.clear()
                logger.info("收到手动触发信号，立即执行检查")

    logger.info("调度器已退出")
```

#### 修改 run_monitor_cycle() 方法

```python
def run_monitor_cycle(self) -> None:
    """执行一次监控循环（线程安全）"""
    
    # 设置检查状态
    with self._check_lock:
        if self._is_checking:
            logger.warning("已有检查在进行中，跳过本次")
            return
        self._is_checking = True
    
    # 通知开始检查
    self._notify_state_change(
        is_running=True,
        is_checking=True,
        last_check_time=datetime.now().isoformat()
    )

    try:
        # ... 原有监控逻辑 ...
        
    finally:
        # 清除检查状态
        with self._check_lock:
            self._is_checking = False
        
        # 通知检查完成
        from datetime import timedelta
        next_check = datetime.now() + timedelta(seconds=self.check_interval)
        self._notify_state_change(
            is_running=True,
            is_checking=False,
            last_check_time=datetime.now().isoformat(),
            next_check_time=next_check.isoformat(),
            check_interval_minutes=self.check_interval // 60
        )
```

#### 新增 trigger_refresh() 方法

```python
def trigger_refresh(self) -> bool:
    """
    手动触发立即刷新
    
    Returns:
        True: 触发成功
        False: 正在检查中，触发失败
    """
    with self._check_lock:
        if self._is_checking:
            logger.info("当前正在检查中，拒绝手动触发")
            return False
    
    logger.info("手动触发刷新")
    self._trigger_event.set()
    return True
```

#### 修改 _notify_state_change() 方法

```python
def _notify_state_change(self, **kwargs) -> None:
    """通知状态变化"""
    if self._state_callback:
        try:
            # 确保传递 is_checking 状态
            self._state_callback(**kwargs)
        except Exception as e:
            logger.warning(f"状态回调执行失败: {e}")
```

### src/web.py

#### 新增 API 端点

```python
@app.post(
    "/api/monitor/refresh",
    tags=["监控"],
    summary="手动触发刷新",
    description="立即执行一次监控检查",
    responses={
        200: {"description": "触发成功"},
        400: {"description": "监控调度器未运行"},
        409: {"description": "正在检查中，请稍后"},
    }
)
async def trigger_monitor_refresh():
    """
    手动触发监控刷新
    
    Returns:
        触发结果
    """
    logger.debug("API调用: POST /api/monitor/refresh")
    
    scheduler = _monitor_state.get("scheduler")
    
    if not scheduler:
        logger.warning("监控调度器未运行")
        raise HTTPException(
            status_code=400,
            detail="监控调度器未运行"
        )
    
    success = scheduler.trigger_refresh()
    
    if not success:
        logger.info("当前正在检查中，触发失败")
        raise HTTPException(
            status_code=409,
            detail="正在检查中，请稍后"
        )
    
    logger.info("手动刷新已触发")
    return {
        "message": "已触发刷新",
        "triggered": True
    }
```

#### 修改 _on_state_change() 回调

```python
def _on_state_change(**kwargs):
    global _monitor_state
    _monitor_state.update(kwargs)
    _monitor_state["error_message"] = None
    
    # 确保 is_checking 状态也被更新
    if "is_checking" not in kwargs:
        _monitor_state["is_checking"] = False
```

## File Changes

| 文件 | 修改类型 | 改动行数 | 说明 |
|------|----------|----------|------|
| `src/scheduler.py` | 修改 + 新增 | ~50 行 | 添加 Event 触发机制、状态锁、trigger_refresh() 方法 |
| `src/web.py` | 新增 | ~30 行 | 添加 POST /api/monitor/refresh API |
| `templates/ups.html` | 修改 + 新增 | ~80 行 | 添加时间显示、刷新按钮、JS 函数 |

## Implementation Flow

```
1. 后端实现
   ├── 1.1 修改 scheduler.py
   │   ├── 添加 _trigger_event, _is_checking, _check_lock 属性
   │   ├── 修改 start() 使用 Event.wait()
   │   ├── 修改 run_monitor_cycle() 添加状态锁
   │   └── 添加 trigger_refresh() 方法
   │
   ├── 1.2 修改 web.py
   │   ├── 添加 POST /api/monitor/refresh 端点
   │   └── 修改 _on_state_change() 更新 is_checking
   │
   └── 1.3 启动测试
       └── 验证 API 响应正确

2. 前端实现
   ├── 2.1 修改 ups.html
   │   ├── 添加时间显示元素
   │   ├── 添加刷新按钮
   │   └── 添加 JS 函数
   │
   └── 2.2 界面测试
       ├── 验证时间显示正确
       └── 验证按钮交互正确

3. 集成测试
   ├── 3.1 功能测试
   │   ├── 测试时间显示更新
   │   ├── 测试手动触发刷新
   │   └── 测试错误场景
   │
   └── 3.2 边界测试
       ├── 测试重复点击
       └── 测试并发触发
```

## Error Handling

### 后端错误处理

| 错误场景 | HTTP 状态码 | 响应 |
|----------|-------------|------|
| 监控未启动 | 400 | `{"error": "Bad Request", "detail": "监控调度器未运行"}` |
| 正在检查中 | 409 | `{"error": "Conflict", "detail": "正在检查中，请稍后"}` |
| Cookie 过期 | - | 调度器内部处理，不暴露给此 API |

### 前端错误处理

| 错误场景 | 处理方式 |
|----------|----------|
| API 请求失败 | 显示错误提示，恢复按钮状态 |
| 网络错误 | 显示"刷新失败: 网络错误" |
| 监控未启动 | 显示"监控未启动"状态 |

## Testing Strategy

### 单元测试

#### scheduler.py 测试

```python
def test_trigger_refresh_success():
    """测试手动触发成功"""
    scheduler = MonitorScheduler(...)
    scheduler._is_checking = False
    
    result = scheduler.trigger_refresh()
    
    assert result is True
    assert scheduler._trigger_event.is_set()

def test_trigger_refresh_while_checking():
    """测试检查中触发失败"""
    scheduler = MonitorScheduler(...)
    scheduler._is_checking = True
    
    result = scheduler.trigger_refresh()
    
    assert result is False
```

#### web.py 测试

```python
def test_refresh_api_success(client):
    """测试刷新 API 成功"""
    response = client.post("/api/monitor/refresh")
    
    assert response.status_code == 200
    assert response.json()["triggered"] is True

def test_refresh_api_conflict(client):
    """测试刷新 API 冲突"""
    # Mock scheduler._is_checking = True
    response = client.post("/api/monitor/refresh")
    
    assert response.status_code == 409
```

### 集成测试

```python
def test_manual_trigger_flow():
    """测试完整手动触发流程"""
    # 1. 启动调度器
    # 2. 调用 trigger_refresh()
    # 3. 验证立即执行检查
    # 4. 验证 next_check_time 更新
```

### 手动测试清单

- [ ] 页面加载时显示时间
- [ ] 时间每 30 秒自动更新
- [ ] 点击刷新按钮触发后端
- [ ] 按钮状态正确切换
- [ ] 刷新完成后时间更新
- [ ] 监控未启动时正确提示
- [ ] 快速点击按钮不会重复触发