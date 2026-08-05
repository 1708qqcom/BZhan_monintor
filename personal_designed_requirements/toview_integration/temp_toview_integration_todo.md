# Implementation Todo

## Preparation

### 环境准备
- [ ] 确认开发环境已配置（Python 3.10+, SQLite, Node.js）
- [ ] 确认系统当前运行正常
- [ ] 备份当前数据库（`data/monitor.db`）
- [ ] 创建开发分支（`git checkout -b feature/toview-integration`）

### 依赖检查
- [ ] 确认 APScheduler 已安装（定时任务）
- [ ] 确认 requests 库已安装
- [ ] 确认所有现有测试通过（`pytest tests/`）

### 文档准备
- [ ] 阅读需求文档（`temp_toview_integration_requirements.md`）
- [ ] 阅读设计文档（`temp_toview_integration_design.md`）
- [ ] 确认技术方案无异议

---

## Development Tasks

### Phase 1: 数据层（Day 1）

#### 1.1 数据库表设计
- [ ] 创建迁移脚本 `scripts/migrate_add_toview_tables.py`
- [ ] 定义 `toview_videos` 表结构
- [ ] 定义 `toview_push_history` 表结构
- [ ] 添加索引和外键约束
- [ ] 执行迁移脚本测试
- [ ] 验证表创建成功

#### 1.2 Database 类扩展
- [ ] 在 `src/database.py` 中新增 `save_toview_videos()` 方法
- [ ] 新增 `get_toview_videos()` 方法
- [ ] 新增 `get_all_toview_videos()` 方法
- [ ] 新增 `save_toview_push_history()` 方法
- [ ] 新增 `get_toview_push_history()` 方法
- [ ] 编写单元测试 `tests/test_database_toview.py`
- [ ] 运行测试验证

---

### Phase 2: B站API集成（Day 1）

#### 2.1 BilibiliClient 扩展
- [ ] 在 `src/bilibili.py` 中添加 `TOVIEW_API` 常量
- [ ] 实现 `get_toview_list()` 方法
- [ ] 处理API返回数据解析
- [ ] 处理错误情况（Cookie失效、API超时）
- [ ] 添加日志记录

#### 2.2 API 测试
- [ ] 使用 `scripts/test_toview_api.py` 验证API可用性
- [ ] 测试不同用户的Cookie
- [ ] 测试API超时重试机制
- [ ] 测试Cookie失效异常处理
- [ ] 编写单元测试 `tests/test_bilibili_toview.py`

---

### Phase 3: 推送功能（Day 2）

#### 3.1 飞书推送模板
- [ ] 在 `src/feishu.py` 中新增 `send_toview_notification()` 方法
- [ ] 设计飞书卡片消息格式
- [ ] 包含视频标题、UP主、播放量信息
- [ ] 添加"前往观看"链接
- [ ] 测试推送消息样式

#### 3.2 定时任务集成
- [ ] 在 `src/scheduler.py` 中新增 `setup_toview_push_scheduler()` 方法
- [ ] 实现 `_push_toview_all_users()` 核心逻辑
- [ ] 添加 21:00 定时触发（CronTrigger）
- [ ] 处理推送失败情况
- [ ] 记录推送历史
- [ ] 测试定时任务触发

---

### Phase 4: Web API开发（Day 2）

#### 4.1 创建API路由文件
- [ ] 创建 `src/api/toview.py`
- [ ] 定义 `PushRequest` 数据模型

#### 4.2 实现API端点
- [ ] 实现 `GET /api/toview` - 获取当前用户稍后再看
- [ ] 实现 `GET /api/toview/all` - 获取所有用户稍后再看（管理员）
- [ ] 实现 `POST /api/toview/push` - 手动推送（管理员）
- [ ] 实现 `GET /api/toview/history` - 获取推送历史

#### 4.3 权限验证
- [ ] 添加用户登录验证（Session中间件）
- [ ] 添加管理员权限验证
- [ ] 测试权限拦截

#### 4.4 注册路由
- [ ] 在 `src/web.py` 中注册 `toview` 路由
- [ ] 测试API可访问性

#### 4.5 API测试
- [ ] 测试获取稍后再看列表
- [ ] 测试管理员查看所有用户
- [ ] 测试手动推送功能
- [ ] 测试推送历史查询
- [ ] 测试错误处理

---

### Phase 5: 前端页面（Day 3）

#### 5.1 用户稍后再看页面
- [ ] 创建 `templates/toview.html`
- [ ] 继承 `base.html` 基础模板
- [ ] 展示视频列表（标题、UP主、播放量）
- [ ] 添加"前往观看"按钮
- [ ] 添加空状态提示
- [ ] 添加加载动画
- [ ] 测试页面渲染

#### 5.2 管理员管理页面
- [ ] 创建 `templates/admin_toview.html`
- [ ] 展示所有用户的稍后再看列表
- [ ] 添加用户筛选功能
- [ ] 添加"立即推送"按钮
- [ ] 实现推送AJAX请求
- [ ] 显示推送结果提示
- [ ] 测试管理员页面

#### 5.3 推送历史页面
- [ ] 创建 `templates/toview_history.html`
- [ ] 展示推送历史表格
- [ ] 显示推送时间、类型、状态
- [ ] 添加"查看详情"功能
- [ ] 支持分页展示

#### 5.4 导航栏更新
- [ ] 在 `templates/base.html` 中添加"稍后再看"链接
- [ ] 添加管理员专属链接
- [ ] 测试导航跳转

#### 5.5 页面路由
- [ ] 在 `src/web.py` 中添加页面路由
- [ ] `/toview` - 用户页面
- [ ] `/admin/toview` - 管理员页面
- [ ] `/toview/history` - 推送历史

---

### Phase 6: 前端优化（Day 3）

#### 6.1 样式优化
- [ ] 使用 Tailwind CSS 美化卡片样式
- [ ] 添加响应式布局（移动端适配）
- [ ] 优化加载动画

#### 6.2 交互优化
- [ ] 添加刷新按钮（重新同步B站数据）
- [ ] 添加加载状态提示
- [ ] 优化错误提示样式

---

## Testing Tasks

### 单元测试

#### 数据库测试
- [ ] 测试 `save_toview_videos()` 正常保存
- [ ] 测试 `get_toview_videos()` 查询结果
- [ ] 测试 `get_all_toview_videos()` 管理员查询
- [ ] 测试 `save_toview_push_history()` 保存历史
- [ ] 测试 `get_toview_push_history()` 查询历史

#### B站API测试
- [ ] 测试 `get_toview_list()` 成功返回
- [ ] 测试 Cookie 失效异常
- [ ] 测试 API 超时重试
- [ ] 测试数据解析正确性

#### 飞书推送测试
- [ ] 测试 `send_toview_notification()` 推送成功
- [ ] 测试卡片消息格式
- [ ] 测试推送失败处理

### 集成测试

#### 定时推送流程
- [ ] 模拟21:00触发
- [ ] 验证所有用户推送成功
- [ ] 验证Cookie失效用户跳过
- [ ] 验证未配置Webhook用户跳过
- [ ] 验证推送历史记录正确

#### 手动推送流程
- [ ] 测试管理员手动推送API
- [ ] 验证推送消息正确发送
- [ ] 验证推送历史记录

#### 权限测试
- [ ] 测试普通用户访问自己的数据
- [ ] 测试普通用户无法访问他人数据
- [ ] 测试管理员访问所有数据
- [ ] 测试管理员手动推送权限

### 手动测试清单

#### 功能测试
- [ ] 用户登录后进入"稍后再看"页面
- [ ] 页面正确展示自己的稍后再看列表
- [ ] 视频信息完整（标题、UP主、播放量）
- [ ] "前往观看"链接可跳转
- [ ] 管理员可查看所有用户数据
- [ ] 管理员可手动推送
- [ ] 推送历史可查询

#### 异常测试
- [ ] Cookie失效显示提示
- [ ] 稍后再看为空显示提示
- [ ] 未配置Webhook显示警告
- [ ] API超时重试成功
- [ ] 推送失败记录日志

#### UI测试
- [ ] 页面样式正常
- [ ] 移动端显示正常
- [ ] 错误提示友好
- [ ] 加载动画流畅

---

## Completion Checklist

### 代码完成
- [ ] 所有代码已编写完成
- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 代码已提交到开发分支

### 文档完成
- [ ] API文档已更新
- [ ] README 已更新（功能说明）
- [ ] 代码注释完整

### 部署准备
- [ ] 数据库迁移脚本已准备
- [ ] 配置文件无变更需求
- [ ] 部署步骤已确认

### 验收测试
- [ ] 产品需求验收（对照 Requirements 文档）
  - [ ] FR-001: 用户查看自己的稍后再看列表
  - [ ] FR-002: 管理员查看所有用户的稍后再看列表
  - [ ] FR-003: 每天21点自动推送
  - [ ] FR-004: 管理员手动推送
  - [ ] FR-005: 推送历史记录

- [ ] 技术设计验收（对照 Design 文档）
  - [ ] 数据库表创建成功
  - [ ] API端点可访问
  - [ ] 定时任务正常运行
  - [ ] 飞书推送正常
  - [ ] 权限控制正确

### 上线准备
- [ ] 合并到主分支（`git checkout main && git merge feature/toview-integration`）
- [ ] 备份生产数据库
- [ ] 执行数据库迁移
- [ ] 重启服务
- [ ] 验证线上功能

### 监控验证
- [ ] 查看21:00推送日志
- [ ] 检查推送历史记录
- [ ] 确认无异常错误

---

## 预计工时

| 阶段 | 预计时间 |
|------|----------|
| Phase 1: 数据层 | 4小时 |
| Phase 2: B站API集成 | 3小时 |
| Phase 3: 推送功能 | 4小时 |
| Phase 4: Web API | 4小时 |
| Phase 5: 前端页面 | 5小时 |
| Phase 6: 测试验收 | 4小时 |
| **总计** | **24小时（3个工作日）** |

---

## 风险提示

### 技术风险
- B站API可能变更：使用已验证的API端点，添加异常处理
- Cookie失效频率：添加有效期监控和提前告警
- 定时任务冲突：确保与现有监控任务无冲突

### 业务风险
- 推送骚扰：第一期每天仅推送一次，后续可扩展用户配置
- 用户未配置Webhook：显示友好提示，记录日志

### 时间风险
- 前端样式可能需要调整：预留优化时间
- 测试发现Bug：每个Phase后立即测试，避免问题堆积

---

## 后续优化（Out of Scope）

以下功能不在当前版本实现范围：
- 自定义推送时间
- 推送频次限制
- 多时区支持
- 添加/删除稍后再看视频
- 视频观看进度同步
- 用户级配置页面