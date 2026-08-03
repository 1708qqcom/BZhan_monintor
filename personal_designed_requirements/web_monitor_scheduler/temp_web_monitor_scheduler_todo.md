# Implementation Todo

## Preparation

- [ ] 确认开发环境：Python 3.x 已安装
- [ ] 确认依赖已安装：fastapi, uvicorn, requests, pyyaml
- [ ] 备份数据库：复制 `data/monitor.db` 到 `data/monitor.db.backup`
- [ ] 创建开发分支：`git checkout -b feature/web-monitor-scheduler`

## Development Tasks

### 阶段一：基础功能（必须）

#### 1. 修改 src/web.py - 增加监控线程启动逻辑

- [ ] 在文件顶部增加导入：
  ```python
  import threading
  import yaml
  from src.scheduler import MonitorScheduler
  from src.bilibili import BilibiliClient
  from src.feishu import FeishuNotifier
  ```

- [ ] 增加模块级状态变量：
  ```python
  _monitor_state = {
      "is_running": False,
      "last_check_time": None,
      "next_check_time": None,
      "check_interval_minutes": 30,
      "scheduler": None,
  }
  ```

- [ ] 实现 `_start_monitor_thread(db: Database)` 函数：
  - 获取B站Cookie
  - 验证Cookie有效性
  - 获取飞书Webhook配置
  - 初始化BilibiliClient、FeishuNotifier、MonitorScheduler
  - 创建daemon线程运行 `scheduler.start()`

- [ ] 修改 `lifespan()` 函数：
  - 在 `yield` 前调用 `_start_monitor_thread(db)`
  - 保存线程引用到 `_monitor_state["scheduler_thread"]`

#### 2. 测试基础功能

- [ ] 启动Web服务：`python main.py --web`
- [ ] 检查日志，确认看到 "监控调度器已启动（后台线程）"
- [ ] 等待一个监控周期（30分钟或修改配置缩短）
- [ ] 检查日志，确认监控循环正常执行
- [ ] 模拟UP主发布新视频（可手动测试）
- [ ] 检查飞书群是否收到通知

### 阶段二：状态查询（推荐）

#### 3. 增加监控状态API

- [ ] 在 `src/web.py` 增加 `GET /api/monitor/status` 端点：
  ```python
  @app.get("/api/monitor/status", tags=["监控"])
  async def get_monitor_status():
      # 返回 _monitor_state 的相关字段
  ```

- [ ] 计算 `next_check_time`：
  - 从 `last_check_time` + `check_interval_minutes` 计算

- [ ] 测试状态API：
  ```bash
  curl http://127.0.0.1:3231/api/monitor/status
  ```

#### 4. 修改 src/scheduler.py - 增加状态更新

- [ ] 在 `MonitorScheduler` 类增加回调函数支持：
  ```python
  def set_state_callback(self, callback):
      self._update_state_callback = callback
  ```

- [ ] 在 `run_monitor_cycle()` 中调用回调更新状态：
  - 开始时更新 `last_check_time`
  - 结束时计算 `next_check_time`

- [ ] 在 `src/web.py` 的 `_start_monitor_thread()` 中设置回调：
  ```python
  scheduler.set_state_callback(lambda **kwargs: _monitor_state.update(kwargs))
  ```

### 阶段三：前端展示（可选）

#### 5. 修改前端页面

- [ ] 修改 `templates/dashboard.html`：
  - 增加监控状态卡片
  - 显示：运行状态、上次检查时间、下次检查时间

- [ ] 增加前端JS代码：
  - 页面加载时调用 `/api/monitor/status`
  - 定时刷新状态（每30秒）

- [ ] （可选）增加"立即检查"按钮：
  - 实现 `POST /api/monitor/trigger` 端点
  - 触发一次立即检查

## Testing Tasks

### 单元测试

- [ ] 创建 `tests/test_web_monitor.py`
- [ ] 测试场景：
  - 未登录B站账号时，监控线程不启动
  - Cookie有效时，监控线程正常启动
  - Cookie过期时，监控线程不启动
  - 状态API返回正确数据

### 集成测试

- [ ] 端到端测试：
  - 启动Web服务
  - 等待监控线程启动
  - 查询状态API
  - 确认数据正确

### 手动验收测试

- [ ] 场景1：正常启动
  - 有有效Cookie
  - 启动Web服务
  - 日志显示 "监控调度器已启动（后台线程）"
  - 状态API返回 `is_running: true`

- [ ] 场景2：未登录
  - 清空数据库中的Cookie
  - 启动Web服务
  - 日志显示 "未登录B站账号，监控调度器不启动"
  - Web界面正常访问

- [ ] 场景3：推送验证
  - 监控UP主发布新视频
  - 等待监控周期
  - 飞书群收到通知

## Completion Checklist

### 功能验收

- [ ] Web服务启动时自动启动监控线程
- [ ] 监控线程在后台运行，不阻塞Web服务
- [ ] 检测到新视频时发送飞书通知
- [ ] 状态API返回正确的监控状态
- [ ] Web服务关闭时监控线程优雅终止

### 代码质量

- [ ] 代码符合项目编码规范
- [ ] 关键逻辑有详细注释
- [ ] 异常处理完善
- [ ] 日志输出完整

### 文档更新

- [ ] 更新 `README.md` 说明Web服务包含监控功能
- [ ] 更新 API 文档（Swagger 自动生成）

### Git 提交

- [ ] 提交代码：`git add . && git commit -m "feat: Web服务集成监控调度器"`
- [ ] 合并到主分支：`git checkout main && git merge feature/web-monitor-scheduler`