# Technical Design

## Overview

在Web服务启动时，通过后台线程启动监控调度器 `MonitorScheduler`，实现Web服务和监控任务的进程内集成。

**技术方案**：
- 使用 `threading.Thread` 创建后台守护线程
- 在线程中运行 `MonitorScheduler.start()` 的无限循环
- 通过 `lifespan` 上下文管理器控制线程生命周期
- 共享数据库实例，避免连接冲突

## Architecture

### 当前架构

```
main.py --web
    ↓
src/web.py (FastAPI)
    ↓
lifespan()
    ↓
Database.init_db()
    ↓
[END]  ← 缺少监控调度器
```

### 改进架构

```
main.py --web
    ↓
src/web.py (FastAPI)
    ↓
lifespan()
    ├── Database.init_db()
    ├── _start_monitor_thread()  ← 新增
    │       ↓
    │   threading.Thread(target=_run_scheduler)
    │       ↓
    │   MonitorScheduler.start()
    │       ├── 循环检查新视频
    │       ├── 推送飞书通知
    │       └── 保存历史记录
    ↓
yield (Web服务运行中)
    ↓
lifespan cleanup
    └── scheduler.stop()  ← 新增
```

## Data Model

### 数据库表变化

无需修改数据库表结构，使用现有的 `config` 表存储配置：

```sql
-- config 表
key: 'feishu_webhook_url'
value: 'https://open.feishu.cn/open-apis/bot/v2/hook/xxx'

key: 'check_interval_minutes'
value: '30'
```

### 内存数据结构

新增监控状态追踪：

```python
# src/web.py 模块级变量
_monitor_state = {
    "is_running": False,
    "last_check_time": None,
    "next_check_time": None,
    "check_interval_minutes": 30,
    "scheduler_thread": None,
}
```

## API / Interface

### 新增 API 端点

#### GET /api/monitor/status

获取监控调度器运行状态。

**Response**:
```json
{
  "is_running": true,
  "last_check_time": "2026-08-03T10:30:00",
  "next_check_time": "2026-08-03T11:00:00",
  "check_interval_minutes": 30
}
```

#### POST /api/monitor/trigger (可选)

手动触发一次检查（用于测试）。

**Response**:
```json
{
  "message": "检查完成",
  "new_videos": 2,
  "pushed": 2
}
```

## Frontend Changes

### Dashboard 页面增加监控状态卡片

在 `templates/dashboard.html` 增加：

```html
<div class="monitor-status-card">
  <h3>监控状态</h3>
  <p>运行中: <span id="is-running">是</span></p>
  <p>上次检查: <span id="last-check">2026-08-03 10:30</span></p>
  <p>下次检查: <span id="next-check">2026-08-03 11:00</span></p>
  <button onclick="triggerCheck()">立即检查</button>
</div>
```

## Backend Changes

### 1. 修改 src/web.py

#### 1.1 新增模块级状态变量

```python
# 监控状态
_monitor_state = {
    "is_running": False,
    "last_check_time": None,
    "next_check_time": None,
    "check_interval_minutes": 30,
    "scheduler": None,
}
```

#### 1.2 新增后台线程启动函数

```python
import threading
from src.scheduler import MonitorScheduler
from src.bilibili import BilibiliClient
from src.feishu import FeishuNotifier

def _start_monitor_thread(db: Database) -> threading.Thread:
    """
    启动监控调度器后台线程

    Args:
        db: 数据库实例

    Returns:
        线程对象
    """
    def run_scheduler():
        global _monitor_state

        try:
            # 1. 获取B站Cookie
            auth = db.get_auth()
            if not auth or not auth.get("cookies"):
                logger.warning("未登录B站账号，监控调度器不启动")
                return

            cookies = auth["cookies"]

            # 2. 初始化B站客户端
            client = BilibiliClient(cookies)

            # 3. 验证Cookie
            if not client.check_cookie_valid():
                logger.error("Cookie已过期，监控调度器不启动")
                return

            # 4. 获取飞书Webhook
            webhook_url = db.get_config_value("feishu_webhook_url")
            if not webhook_url:
                # 回退到配置文件
                import yaml
                with open("config/settings.yaml") as f:
                    config = yaml.safe_load(f)
                webhook_url = config.get("feishu", {}).get("webhook_url", "")

            # 5. 初始化飞书推送器
            notifier = None
            if webhook_url:
                notifier = FeishuNotifier(webhook_url)
            else:
                logger.warning("未配置飞书Webhook，推送功能不可用")

            # 6. 获取检查间隔
            interval_str = db.get_config_value("check_interval_minutes", "30")
            check_interval = int(interval_str)

            # 7. 初始化调度器
            scheduler = MonitorScheduler(
                bilibili_client=client,
                feishu_notifier=notifier,
                database=db,
                check_interval_minutes=check_interval,
            )

            _monitor_state["scheduler"] = scheduler
            _monitor_state["is_running"] = True
            _monitor_state["check_interval_minutes"] = check_interval

            logger.info("监控调度器已启动（后台线程）")

            # 8. 启动监控循环（阻塞）
            scheduler.start()

        except Exception as e:
            logger.error(f"监控调度器异常: {e}", exc_info=True)
        finally:
            _monitor_state["is_running"] = False
            logger.info("监控调度器已停止")

    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()
    return thread
```

#### 1.3 修改 lifespan 函数

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _monitor_state

    logger.info("=" * 50)
    logger.info("Web 应用启动中...")
    logger.info("=" * 50)

    # 1. 初始化数据库
    try:
        db = Database()
        db.init_db()
        logger.info("数据库初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

    # 2. 启动监控调度器
    _monitor_state["scheduler_thread"] = _start_monitor_thread(db)

    yield

    # 3. 关闭时停止调度器
    logger.info("Web 应用关闭")
    if _monitor_state["scheduler"]:
        # MonitorScheduler 通过 daemon=True 自动终止
        logger.info("监控调度器将在后台线程终止")
```

#### 1.4 新增状态API端点

```python
from datetime import datetime

@app.get("/api/monitor/status", tags=["监控"])
async def get_monitor_status():
    """
    获取监控调度器状态
    """
    global _monitor_state

    scheduler = _monitor_state.get("scheduler")

    if scheduler:
        # 计算下次检查时间
        last_check = _monitor_state.get("last_check_time")
        interval = _monitor_state.get("check_interval_minutes", 30)

        if last_check:
            from datetime import timedelta
            last_dt = datetime.fromisoformat(last_check)
            next_dt = last_dt + timedelta(minutes=interval)
            next_check = next_dt.isoformat()
        else:
            next_check = None
    else:
        next_check = None

    return {
        "is_running": _monitor_state.get("is_running", False),
        "last_check_time": _monitor_state.get("last_check_time"),
        "next_check_time": next_check,
        "check_interval_minutes": _monitor_state.get("check_interval_minutes", 30),
    }
```

### 2. 修改 src/scheduler.py

#### 2.1 增加状态更新回调

在 `run_monitor_cycle()` 中更新状态：

```python
def run_monitor_cycle(self) -> None:
    """执行一次监控循环"""
    logger.info("========== 开始监控循环 ==========")
    cycle_start = time.time()

    # 更新状态（供Web API使用）
    if hasattr(self, '_update_state_callback'):
        self._update_state_callback(last_check_time=datetime.now().isoformat())

    # ... 原有逻辑 ...

    # 更新下次检查时间
    if hasattr(self, '_update_state_callback'):
        from datetime import timedelta
        next_time = datetime.now() + timedelta(seconds=self.check_interval)
        self._update_state_callback(next_check_time=next_time.isoformat())
```

## File Changes

### 需要修改的文件

| 文件 | 修改内容 | 复杂度 |
|------|---------|--------|
| `src/web.py` | 增加监控线程启动逻辑、状态API | 🔴 高 |
| `src/scheduler.py` | 增加状态更新回调（可选） | 🟡 中 |
| `src/api/__init__.py` | 注册监控状态路由 | 🟢 低 |

### 需要新增的文件

无

## Implementation Flow

### 阶段一：基础功能（必须）

1. 修改 `src/web.py`，增加 `_start_monitor_thread()` 函数
2. 修改 `lifespan()` 函数，启动监控线程
3. 测试启动流程，确认监控线程正常运行
4. 测试推送功能，确认飞书通知正常发送

### 阶段二：状态查询（推荐）

1. 增加 `GET /api/monitor/status` API端点
2. 增加模块级状态变量 `_monitor_state`
3. 修改 `src/scheduler.py`，增加状态更新回调
4. 测试状态查询，确认返回正确数据

### 阶段三：前端展示（可选）

1. 修改 `templates/dashboard.html`，增加监控状态卡片
2. 增加前端JS代码，定时刷新状态
3. 增加"立即检查"按钮（需实现 `POST /api/monitor/trigger`）

## Error Handling

### 错误场景处理

| 场景 | 处理方式 | 日志级别 |
|------|---------|---------|
| 未登录B站账号 | 跳过启动调度器，Web正常启动 | WARNING |
| Cookie已过期 | 跳过启动调度器，Web正常启动 | ERROR |
| 飞书Webhook未配置 | 调度器启动但不推送 | WARNING |
| 监控线程异常退出 | 记录异常日志，线程终止 | ERROR |
| 数据库操作失败 | 捕获异常，记录日志，继续运行 | ERROR |

### 日志示例

```
[INFO] Web 应用启动中...
[INFO] 数据库初始化成功
[WARNING] 未登录B站账号，监控调度器不启动
[INFO] 监控调度器已启动（后台线程）
[INFO] 监控循环完成: 新视频=2, 已推送=2
[ERROR] Cookie已过期，监控调度器不启动
[INFO] 监控调度器已停止
```

## Testing Strategy

### 单元测试

1. 测试 `_start_monitor_thread()` 函数：
   - 模拟有效Cookie，确认线程启动
   - 模拟无效Cookie，确认线程不启动
   - 模拟无Cookie，确认线程不启动

2. 测试 `GET /api/monitor/status`：
   - 调度器运行时返回正确状态
   - 调度器未运行时返回 `is_running=false`

### 集成测试

1. 端到端测试：
   - 启动Web服务
   - 等待监控线程启动
   - 模拟UP主发布新视频
   - 确认飞书推送成功

2. 边界测试：
   - 启动时无Cookie
   - 启动时Cookie过期
   - 飞书Webhook无效

### 手动测试

```bash
# 1. 启动Web服务
python main.py --web

# 2. 查看日志，确认监控线程启动
# 应看到: "监控调度器已启动（后台线程）"

# 3. 访问Web界面
open http://127.0.0.1:3231

# 4. 等待监控循环执行
# 应看到日志: "监控循环完成: 新视频=X, 已推送=Y"

# 5. 检查飞书群是否收到通知

# 6. 查询监控状态
curl http://127.0.0.1:3231/api/monitor/status
```