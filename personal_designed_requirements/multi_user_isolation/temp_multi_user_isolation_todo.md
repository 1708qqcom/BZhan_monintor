# Implementation Todo - 多用户隔离系统

## Preparation

### 环境准备
- [ ] 确认数据库备份（data/monitor.db）
- [ ] 创建开发分支（git checkout -b feature/multi-user）

---

## Development Tasks

### 阶段1：数据库改造

#### 1.1 编写数据迁移脚本
- [ ] 创建 scripts/migrate_to_multi_user.py
- [ ] 实现 create_users_table() - 创建用户表
- [ ] 实现 rebuild_auth_table() - 重建 auth 表（添加 user_id）
- [ ] 实现 alter_ups_table() - ups 表添加 user_id 字段
- [ ] 实现 alter_config_table() - config 表添加 user_id 字段
- [ ] 实现 create_default_admin() - 创建默认管理员
- [ ] 实现 migrate_data() - 迁移现有数据到默认用户
- [ ] 实现 rollback() - 回滚函数（失败时恢复）

#### 1.2 执行数据迁移
- [ ] 备份当前数据库
- [ ] 运行迁移脚本
- [ ] 验证数据完整性
- [ ] 更新 src/database.py 的 init_db() 方法（新用户首次启动时自动创建表）

---

### 阶段2：用户系统实现

#### 2.1 数据库层（src/database.py）
- [ ] 新增 add_user(username, password, is_admin=False) 方法
- [ ] 新增 get_user_by_username(username) 方法
- [ ] 新增 get_user_by_id(user_id) 方法
- [ ] 新增 get_all_users() 方法（管理员用）
- [ ] 新增 delete_user(user_id) 方法（管理员用）
- [ ] 新增 get_all_users_with_valid_auth() 方法（监控线程用）

#### 2.2 模型层（src/models.py）
- [ ] 新增 UserResponse 模型
- [ ] 新增 UserCreateRequest 模型
- [ ] 新增 UserListResponse 模型
- [ ] 新增 RegisterRequest 模型

#### 2.3 Web层（src/web.py）
- [ ] 改造认证中间件：从 authenticated 改为 user_id
- [ ] 新增 GET /auth/register - 渲染注册页面
- [ ] 新增 POST /auth/register - 处理注册逻辑
- [ ] 改造 POST /auth/login - 数据库验证，Session 存储 user_id/username/is_admin
- [ ] 新增 GET /api/users - 管理员获取用户列表
- [ ] 新增 DELETE /api/users/{id} - 管理员删除用户

#### 2.4 前端页面
- [ ] 创建 templates/register.html - 注册页面
- [ ] 改造 templates/login.html - 增加注册入口链接
- [ ] 改造 templates/base.html - 显示当前用户、退出按钮、管理员入口

---

### 阶段3：API 改造

#### 3.1 B站登录 API（src/api/login.py）
- [ ] 改造 _auth_code_store - 从单值改为 {user_id: auth_code} 字典
- [ ] 改造 GET /api/login/qrcode - auth_code 关联到 user_id
- [ ] 改造 POST /api/login/poll - Cookie 保存到 db.save_auth(user_id, cookies)
- [ ] 改造 GET /api/login/status - 查询当前用户的 B站登录状态
- [ ] 改造 POST /api/login/logout - 清除当前用户的 B站登录信息

#### 3.2 UP主管理 API（src/api/ups.py）
- [ ] 改造 GET /api/ups - 增加用户过滤（管理员可查看所有）
- [ ] 改造 POST /api/ups - 添加 UP主时关联到 user_id
- [ ] 改造 POST /api/ups/sync - 使用当前用户的 B站 Cookie
- [ ] 改造 DELETE /api/ups/{id} - 验证 UP主归属（只能删除自己的）

#### 3.3 视频历史 API（src/api/videos.py）
- [ ] 改造 GET /api/videos - 增加用户过滤（管理员可查看所有）

#### 3.4 配置管理 API（src/api/config.py）
- [ ] 改造 GET /api/config - 返回当前用户的配置
- [ ] 改造 PUT /api/config - 更新当前用户的配置

#### 3.5 同步服务（src/sync_service.py）
- [ ] 改造 sync_followed_ups() - 增加 user_id 参数
- [ ] 调用 db.add_up() 时传入 user_id

---

### 阶段4：监控线程改造

#### 4.1 调度器改造（src/scheduler.py）
- [ ] 改造 _check_loop() - 改为轮询所有用户
- [ ] 新增 _check_user_videos(user_id) - 检查单个用户的新视频
- [ ] 改造推送逻辑 - 使用用户自己的飞书 Webhook
- [ ] 改造错误处理 - 单用户失败不影响其他用户

#### 4.2 数据库支持（src/database.py）
- [ ] 新增 get_all_users_with_valid_auth() - 获取所有有效 B站登录的用户

---

### 阶段5：前端改造

#### 5.1 模板改造
- [ ] 改造 templates/base.html - 显示当前用户名、退出按钮
- [ ] 改造 templates/ups.html - 管理员增加用户筛选下拉框
- [ ] 改造 templates/videos.html - 管理员增加用户筛选下拉框
- [ ] 改造 templates/dashboard.html - 管理员显示全局统计

#### 5.2 JavaScript 改造（static/js/main.js）
- [ ] 改造 API 调用 - 适配新的响应结构
- [ ] 增加用户筛选功能（管理员）

#### 5.3 用户管理页面（管理员）
- [ ] 创建 templates/users.html - 用户列表页面
- [ ] 实现用户删除功能

---

## Testing Tasks

### 单元测试
- [ ] 测试用户注册（用户名重复、正常注册）
- [ ] 测试用户登录（密码错误、正常登录）
- [ ] 测试用户数据隔离（UP主、视频、配置）
- [ ] 测试 B站登录关联用户

### 集成测试
- [ ] 测试多用户同步关注列表
- [ ] 测试多用户监控线程
- [ ] 测试管理员权限（查看所有用户数据）

### 端到端测试
- [ ] 注册两个用户
- [ ] 分别登录并绑定 B站账号
- [ ] 分别同步关注列表
- [ ] 验证用户1看不到用户2的 UP主
- [ ] 管理员登录，验证可以看到所有用户数据

---

## Completion Checklist

### 功能完成
- [ ] 用户可以注册账号
- [ ] 用户可以登录/登出
- [ ] 用户可以绑定自己的 B站账号
- [ ] 用户只能看到自己的 UP主列表
- [ ] 用户只能看到自己的推送历史
- [ ] 管理员可以查看所有用户数据
- [ ] 监控线程支持多用户

### 数据迁移
- [ ] 现有数据已迁移到默认管理员用户
- [ ] 数据完整性验证通过

### 文档更新
- [ ] 更新 README.md（用户注册说明）
- [ ] 更新 PRD（多用户功能）
- [ ] 更新 API 文档

### 代码质量
- [ ] 无明显 Bug
- [ ] 日志输出完整
- [ ] 错误处理健全

---

## Notes

### 简化设计（根据用户确认）
- 密码明文存储（不使用 bcrypt）
- 用户量 < 10，不优化性能
- 开放注册（无需邮箱验证）
- 临时状态使用数据库存储（不使用 Redis）

### 数据迁移注意事项
- 迁移前必须备份数据库
- 迁移脚本需要支持回滚
- 建议先在测试环境验证

### 监控线程注意事项
- 单线程轮询所有用户
- 某用户失败不影响其他用户
- 需要记录每个用户的检查时间