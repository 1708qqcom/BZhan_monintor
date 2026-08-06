# Implementation Todo: User Onboarding Flow

## Preparation

### 环境准备

- [ ] 确认数据库备份（执行迁移前）
- [ ] 确认测试账号可用（验证引导流程）
- [ ] 确认B站测试账号可用（测试扫码登录）
- [ ] 确认飞书Webhook可用（测试推送配置）

### 技术准备

- [ ] 阅读 [src/database.py](../src/database.py) 数据库操作模式
- [ ] 阅读 [src/web.py](../src/web.py) 路由注册方式
- [ ] 阅读 [templates/bilibili_login.html](../templates/bilibili_login.html) B站登录组件
- [ ] 阅读 [templates/config.html](../templates/config.html) 配置表单组件
- [ ] 阅读 [templates/ups.html](../templates/ups.html) UP主列表组件


## Development Tasks

### Phase 1: 数据库设计

**优先级**：高 | **预计时间**：30分钟

#### Task 1.1: 创建 user_onboarding 表

- [ ] 在 `src/database.py` 的 `init_db()` 方法中添加表创建逻辑
- [ ] 定义表结构（8个字段：user_id, step1-3_completed, step1-3_skipped, current_step, created_at, updated_at）
- [ ] 创建索引 `idx_user_onboarding_user_id`
- [ ] 测试：重启服务，验证表创建成功

**验证方式**：
```bash
sqlite3 data/monitor.db ".schema user_onboarding"
```

#### Task 1.2: 实现初始化方法

- [ ] 在 `src/database.py` 添加 `init_onboarding_progress(user_id)` 方法
- [ ] 插入默认值：current_step=1, 所有completed/skipped=0
- [ ] 添加日志记录
- [ ] 测试：调用方法后查询数据库验证

#### Task 1.3: 实现查询方法

- [ ] 在 `src/database.py` 添加 `get_onboarding_progress(user_id)` 方法
- [ ] 返回字典格式结果
- [ ] 处理不存在的情况（返回None）
- [ ] 测试：查询已存在的记录和不存在的情况

#### Task 1.4: 实现更新方法

- [ ] 在 `src/database.py` 添加 `update_onboarding_step(user_id, step, completed, skipped)` 方法
- [ ] 支持完成和跳过两种状态
- [ ] 自动更新 `current_step` 和 `updated_at`
- [ ] 测试：更新步骤1为完成，验证字段变化


### Phase 2: 数据模型定义

**优先级**：高 | **预计时间**：20分钟

#### Task 2.1: 定义 Pydantic 模型

- [ ] 在 `src/models.py` 添加 `OnboardingProgress` 模型
- [ ] 添加 `OnboardingStepRequest` 模型
- [ ] 添加 `OnboardingStatusResponse` 模型
- [ ] 测试：使用 Pydantic 验证模型字段


### Phase 3: API 开发

**优先级**：高 | **预计时间**：1小时

#### Task 3.1: 创建 API 文件

- [ ] 创建 `src/api/onboarding.py` 文件
- [ ] 定义路由前缀 `/api/onboarding`
- [ ] 导入必要依赖（Database, models）

#### Task 3.2: 实现状态查询接口

- [ ] 实现 `GET /api/onboarding/status` 接口
- [ ] 从 Session 获取 user_id
- [ ] 调用 `db.get_onboarding_progress()`
- [ ] 计算进度百分比
- [ ] 返回 `OnboardingStatusResponse` 格式响应
- [ ] 测试：使用 Swagger UI 测试接口

#### Task 3.3: 实现完成步骤接口

- [ ] 实现 `POST /api/onboarding/complete-step` 接口
- [ ] 验证 step 参数（1-3）
- [ ] 调用 `db.update_onboarding_step(completed=True)`
- [ ] 返回成功消息
- [ ] 测试：调用接口后查询数据库验证

#### Task 3.4: 实现跳过步骤接口

- [ ] 实现 `POST /api/onboarding/skip-step` 接口
- [ ] 验证 step 参数（1-3）
- [ ] 调用 `db.update_onboarding_step(skipped=True)`
- [ ] 返回成功消息
- [ ] 测试：调用接口后查询数据库验证

#### Task 3.5: 注册路由

- [ ] 在 `src/web.py` 导入 `onboarding_router`
- [ ] 使用 `app.include_router(onboarding_router)` 注册
- [ ] 测试：访问 `/docs` 查看新接口


### Phase 4: 前端页面开发

**优先级**：高 | **预计时间**：2小时

#### Task 4.1: 创建引导页面基础结构

- [ ] 创建 `templates/onboarding.html` 文件
- [ ] 继承 `base.html` 模板
- [ ] 添加顶部进度条（步骤1-3指示器）
- [ ] 添加内容区域 `<div id="step-content">`
- [ ] 添加底部按钮区域（上一步、下一步、跳过、完成）

#### Task 4.2: 实现步骤1 - B站登录

- [ ] 在 `onboarding.html` 添加步骤1内容区域
- [ ] 复用 [templates/bilibili_login.html](../templates/bilibili_login.html) 的二维码组件代码
- [ ] 显示二维码和状态提示
- [ ] 扫码成功后自动调用 `/api/onboarding/complete-step`
- [ ] 添加"跳过"按钮，调用 `/api/onboarding/skip-step`
- [ ] 测试：使用测试账号扫码验证

#### Task 4.3: 实现步骤2 - 飞书配置

- [ ] 在 `onboarding.html` 添加步骤2内容区域
- [ ] 复用 [templates/config.html](../templates/config.html) 的飞书配置表单
- [ ] 添加图文教程链接（可选）
- [ ] 提供"测试推送"按钮
- [ ] 保存成功后调用 `/api/onboarding/complete-step`
- [ ] 添加"跳过"按钮
- [ ] 测试：填写Webhook并测试推送

#### Task 4.4: 实现步骤3 - UP主选择

- [ ] 在 `onboarding.html` 添加步骤3内容区域
- [ ] 调用 `/api/ups` 获取UP主列表
- [ ] 渲染为批量勾选列表（复选框）
- [ ] 默认全选，允许取消勾选
- [ ] 点击"完成"保存选择并调用 `/api/onboarding/complete-step`
- [ ] 添加"跳过"按钮
- [ ] 测试：勾选UP主并保存

#### Task 4.5: 创建前端交互脚本

- [ ] 创建 `static/js/onboarding.js` 文件
- [ ] 实现 `OnboardingManager` 类
- [ ] 实现 `loadProgress()` 加载引导进度
- [ ] 实现 `renderStep(step)` 渲染步骤内容
- [ ] 实现 `completeStep(step)` 完成步骤
- [ ] 实现 `skipStep(step)` 跳过步骤
- [ ] 实现 `updateProgressBar()` 更新进度条样式
- [ ] 测试：切换步骤，验证状态保存


### Phase 5: 流程集成

**优先级**：高 | **预计时间**：1小时

#### Task 5.1: 添加引导页面路由

- [ ] 在 `src/web.py` 添加 `GET /onboarding` 路由
- [ ] 渲染 `onboarding.html` 模板
- [ ] 将路由添加到认证白名单（登录后访问）
- [ ] 测试：访问 `http://localhost:8000/onboarding`

#### Task 5.2: 修改注册流程

- [ ] 在 `src/web.py` 的 `register_submit()` 函数中添加引导初始化逻辑
- [ ] 调用 `db.init_onboarding_progress(user_id)`
- [ ] 修改跳转地址为 `/onboarding`
- [ ] 测试：注册新账号，验证跳转到引导页

#### Task 5.3: 修改仪表盘

- [ ] 在 `templates/dashboard.html` 添加引导进度提示卡片
- [ ] 在 `src/web.py` 的 `root()` 函数查询引导进度
- [ ] 传递 `onboarding_completed` 和 `onboarding_progress` 变量到模板
- [ ] 未完成引导时显示进度卡片，点击跳转到 `/onboarding`
- [ ] 测试：使用未完成引导的账号登录，验证卡片显示


### Phase 6: 兼容性处理

**优先级**：中 | **预计时间**：30分钟

#### Task 6.1: 老用户兼容逻辑

- [ ] 在 `src/web.py` 的 `AuthMiddleware` 中添加老用户判断逻辑
- [ ] 如果没有 `user_onboarding` 记录，视为"已完成引导"
- [ ] 或创建 `user_onboarding` 记录并标记为"已完成"
- [ ] 测试：使用老用户账号登录，验证不触发引导

#### Task 6.2: 步骤依赖检查

- [ ] 在步骤3渲染时检查步骤1是否完成
- [ ] 如果步骤1跳过，显示提示："请先完成B站账号绑定"
- [ ] 提供"返回步骤1"按钮
- [ ] 测试：跳过步骤1，验证步骤3提示


### Phase 7: 样式优化

**优先级**：中 | **预计时间**：30分钟

#### Task 7.1: 添加引导页面样式

- [ ] 在 `templates/onboarding.html` 添加自定义样式
- [ ] 进度条激活状态样式（绿色）
- [ ] 步骤内容区域居中和间距
- [ ] 按钮样式和悬浮效果
- [ ] 移动端响应式适配

#### Task 7.2: 添加进度卡片样式

- [ ] 在 `templates/dashboard.html` 添加进度卡片样式
- [ ] 卡片位置（顶部固定）
- [ ] 卡片样式（背景色、边框、阴影）
- [ ] 关闭按钮（可选）


## Testing Tasks

### 单元测试

**优先级**：中 | **预计时间**：30分钟

#### Test 1: 数据库方法测试

- [ ] 测试 `init_onboarding_progress()` 初始化逻辑
- [ ] 测试 `get_onboarding_progress()` 查询逻辑
- [ ] 测试 `update_onboarding_step()` 更新逻辑（完成和跳过）
- [ ] 测试重复初始化（唯一约束）

#### Test 2: API 接口测试

- [ ] 测试 `GET /api/onboarding/status` 返回格式
- [ ] 测试 `POST /api/onboarding/complete-step` 参数验证
- [ ] 测试 `POST /api/onboarding/skip-step` 参数验证
- [ ] 测试未登录访问（401错误）


### 集成测试

**优先级**：高 | **预计时间**：30分钟

#### Test 3: 完整引导流程测试

- [ ] 测试新用户注册 → 自动跳转引导页
- [ ] 测试完成所有步骤 → 跳转仪表盘
- [ ] 测试仪表盘进度显示正确
- [ ] 测试已完成引导的用户不显示进度卡片

#### Test 4: 中断恢复测试

- [ ] 测试完成步骤1后关闭浏览器
- [ ] 再次登录，验证跳转到步骤2
- [ ] 测试跳过步骤2，验证步骤3可访问

#### Test 5: 跳过功能测试

- [ ] 测试跳过步骤1，验证状态记录
- [ ] 测试跳过步骤2，验证状态记录
- [ ] 测试跳过所有步骤，验证跳转仪表盘

#### Test 6: 老用户测试

- [ ] 使用已有账号登录
- [ ] 验证不触发引导流程
- [ ] 验证仪表盘不显示进度卡片


### 性能测试

**优先级**：低 | **预计时间**：15分钟

#### Test 7: 页面加载性能

- [ ] 测试引导页面加载时间（< 2秒）
- [ ] 测试API响应时间（< 500ms）
- [ ] 测试步骤切换动画流畅度（60fps）


## Completion Checklist

### 功能完整性检查

- [ ] 新用户注册后自动跳转引导页
- [ ] 三个步骤可正常完成或跳过
- [ ] 进度正确保存和恢复
- [ ] 仪表盘显示进度提示
- [ ] 老用户不受影响

### 代码质量检查

- [ ] 代码符合项目规范（命名、注释）
- [ ] 日志记录完整（关键操作记录）
- [ ] 错误处理完善（异常捕获、用户提示）
- [ ] 无明显性能问题

### 文档检查

- [ ] API 文档更新（Swagger）
- [ ] 数据库表结构文档更新（可选）
- [ ] 用户使用文档更新（可选）

### 部署检查

- [ ] 数据库迁移脚本测试
- [ ] 回滚方案验证
- [ ] 生产环境测试（可选）


## Notes

### 依赖关系

- Task 3.* 依赖 Task 1.* 和 Task 2.*
- Task 4.* 依赖 Task 3.*
- Task 5.* 依赖 Task 4.*

### 风险提示

- 数据库迁移需谨慎（先备份）
- 老用户兼容性需充分测试
- 步骤依赖逻辑需验证（步骤3依赖步骤1）

### 优化建议

- 可以先实现最小可用版本（只有步骤1）
- 前端组件可逐步复用，避免一次性开发过多
- 移动端适配可在最后优化