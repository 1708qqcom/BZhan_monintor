# Implementation Todo

## Preparation

### 环境准备

- [x] 已有项目代码库
- [x] 已有飞书推送模块 `src/feishu.py`
- [x] 已有数据库模块 `src/database.py`
- [x] 已有 B站 API 模块 `src/bilibili.py`


### 依赖检查

- [x] FastAPI 已安装
- [x] SQLite 数据库已启用
- [x] 飞书 Webhook 已测试可用


---

## Development Tasks

### Task 1: 数据库层扩展

#### 1.1 创建 push_history 表

**文件**：`src/database.py`

**任务**：
- [ ] 添加 `init_push_history_table()` 方法
- [ ] 在 `init_db()` 中调用该方法
- [ ] 定义表结构：
  ```sql
  CREATE TABLE push_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      video_id INTEGER NOT NULL,
      pushed_at TEXT NOT NULL,
      push_type TEXT NOT NULL DEFAULT 'manual',
      success INTEGER NOT NULL DEFAULT 0,
      error_message TEXT,
      created_at TEXT NOT NULL,
      FOREIGN KEY (video_id) REFERENCES videos(id)
  )
  ```
- [ ] 创建索引：`idx_push_history_video_id`, `idx_push_history_pushed_at`

**验证**：
- 运行应用，检查数据库文件是否创建该表
- 使用 SQLite 客户端查看表结构


#### 1.2 添加数据库操作方法

**文件**：`src/database.py`

**任务**：
- [ ] 添加 `get_video_by_bvid(bvid: str) -> Optional[dict]` 方法
- [ ] 添加 `update_video(bvid: str, video_data: dict) -> bool` 方法
- [ ] 添加 `add_push_history(video_id, push_type, success, error_message) -> int` 方法
- [ ] 添加 `get_push_history(video_id: int, limit: int = 10) -> list` 方法（可选）

**验证**：
- 编写单元测试验证各方法
- 测试查询不存在记录返回 None
- 测试更新和插入操作


---

### Task 2: B站 API 扩展

#### 2.1 添加视频详情查询方法

**文件**：`src/bilibili.py`

**任务**：
- [ ] 添加 `get_video_detail(bvid: str) -> dict` 方法
- [ ] 调用 B站 API：`https://api.bilibili.com/x/web-interface/view?bvid={bvid}`
- [ ] 解析响应，提取字段：`title`, `view_count`, `pub_date`, `desc`
- [ ] 处理异常：
  - 网络超时
  - Cookie 过期
  - API 返回错误

**验证**：
- 测试正常视频查询
- 测试不存在视频查询
- 测试网络异常处理


---

### Task 3: 后端 API 开发

#### 3.1 创建推送 API 端点

**文件**：`src/api/videos.py`

**任务**：
- [ ] 添加路由：`POST /{bvid}/push`
- [ ] 定义响应模型：`SuccessResponse`
- [ ] 定义错误响应：`ErrorResponse`（400, 404, 500）


#### 3.2 实现推送逻辑

**文件**：`src/api/videos.py`

**任务**：
- [ ] 根据 `bvid` 查询视频记录
- [ ] 检查视频是否存在（404 错误）
- [ ] 检查视频信息完整性（title, url, pub_time, view_count）
- [ ] 如果缺失，调用 `BilibiliClient.get_video_detail()` 补全
- [ ] 更新数据库中的视频记录
- [ ] 查询 UP主信息（获取 `up_name`）
- [ ] 从配置表读取 `feishu_webhook`
- [ ] 检查 Webhook 是否配置（400 错误）
- [ ] 初始化 `FeishuNotifier`
- [ ] 调用 `send_new_video_notification()`
- [ ] 记录推送历史到 `push_history` 表
- [ ] 返回推送结果


#### 3.3 添加异常处理

**文件**：`src/api/videos.py`

**任务**：
- [ ] 捕获 `HTTPException` 并向上抛出
- [ ] 捕获 `FeishuAPIError`，返回 500 错误
- [ ] 捕获通用异常，记录日志并返回 500 错误
- [ ] 所有错误情况都记录到 `push_history`（`success=false`）


#### 3.4 添加日志记录

**文件**：`src/api/videos.py`

**任务**：
- [ ] 推送开始：`[INFO] 开始手动推送视频: bvid=xxx`
- [ ] 信息补全：`[WARNING] 视频信息不完整，调用B站API补全`
- [ ] 推送成功：`[INFO] 手动推送视频成功: bvid=xxx, title=xxx`
- [ ] 推送失败：`[ERROR] 手动推送视频失败: bvid=xxx, error=xxx`
- [ ] 异常堆栈：使用 `exc_info=True` 记录完整堆栈


**验证**：
- 使用 Postman 或 curl 测试 API
- 测试成功推送
- 测试各种错误情况
- 检查数据库 `push_history` 表记录


---

### Task 4: 前端交互开发

#### 4.1 修改视频卡片渲染

**文件**：`templates/ups.html`

**任务**：
- [ ] 修改 `renderLatestVideos()` 函数
- [ ] 将 `<a>` 标签改为 `<div>` 容器
- [ ] 在容器内保留 `<a>` 标签用于跳转
- [ ] 在右上角添加"推送"按钮
- [ ] 按钮样式：`text-bilibili-pink hover:text-pink-600`
- [ ] 按钮绑定点击事件：`pushVideoToFeishu(bvid, title)`


#### 4.2 添加推送函数

**文件**：`templates/ups.html`

**任务**：
- [ ] 添加 `pushVideoToFeishu(bvid, title)` 函数
- [ ] 弹出确认对话框：`confirm('确定推送视频 "{title}" 到飞书？')`
- [ ] 用户取消时直接返回
- [ ] 调用 `fetchAPI('/api/videos/${bvid}/push', {method: 'POST'})`
- [ ] 成功时调用 `showSuccess('推送成功')`
- [ ] 失败时调用 `showError('推送失败: ' + error.message)`


#### 4.3 优化移动端体验

**文件**：`templates/ups.html`

**任务**：
- [ ] 检查移动端按钮大小是否合适
- [ ] 确保按钮点击区域足够大（min-height: 32px）
- [ ] 测试移动端点击体验


**验证**：
- 访问 `/ups` 页面
- 展开视频列表，检查按钮显示
- 点击推送按钮，检查确认对话框
- 确认推送，检查成功/失败提示
- 检查飞书群是否收到消息


---

### Task 5: 集成与测试

#### 5.1 端到端测试

**任务**：
- [ ] 测试正常推送流程
- [ ] 测试重复推送
- [ ] 测试未配置 Webhook 情况
- [ ] 测试视频不存在情况
- [ ] 测试网络断开情况
- [ ] 测试视频信息补全


#### 5.2 数据库验证

**任务**：
- [ ] 检查 `push_history` 表记录
- [ ] 验证字段：`video_id`, `push_type`, `success`, `pushed_at`
- [ ] 检查失败记录的 `error_message` 字段


#### 5.3 日志验证

**任务**：
- [ ] 检查控制台日志输出
- [ ] 验证错误日志包含详细异常信息
- [ ] 验证信息补全日志


---

## Testing Tasks

### 单元测试（可选）

- [ ] 测试 `Database.get_video_by_bvid()`
- [ ] 测试 `Database.update_video()`
- [ ] 测试 `Database.add_push_history()`
- [ ] 测试 `BilibiliClient.get_video_detail()`


### 集成测试

- [ ] 测试 API：`POST /api/videos/{bvid}/push`
- [ ] 测试成功响应（200）
- [ ] 测试视频不存在（404）
- [ ] 测试 Webhook 未配置（400）
- [ ] 测试推送失败（500）


### 手动验收测试

- [ ] 前端按钮显示正确
- [ ] 点击按钮弹出确认对话框
- [ ] 确认后显示加载状态
- [ ] 推送成功显示成功提示
- [ ] 飞书群收到正确格式的消息
- [ ] 推送失败显示失败提示
- [ ] 重复推送功能正常
- [ ] 移动端体验正常


---

## Completion Checklist

### 功能完成检查

- [ ] 数据库 `push_history` 表已创建
- [ ] 数据库操作方法已添加
- [ ] B站 API 扩展方法已添加
- [ ] 后端 API 端点已实现
- [ ] 前端推送按钮已添加
- [ ] 前端推送函数已实现
- [ ] 推送成功流程正常
- [ ] 推送失败流程正常
- [ ] 推送历史记录正常
- [ ] 视频信息补全功能正常


### 代码质量检查

- [ ] 代码符合项目风格
- [ ] 日志记录完整
- [ ] 异常处理完善
- [ ] 无明显性能问题


### 文档更新（可选）

- [ ] 更新 API 文档（Swagger 已自动生成）
- [ ] 更新用户使用说明（如有）