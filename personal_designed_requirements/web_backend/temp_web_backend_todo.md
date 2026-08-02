# Implementation Todo - Web Backend

## Preparation

- [ ] 更新 `requirements.txt`，添加 FastAPI 相关依赖
  - fastapi
  - uvicorn[standard]
  - pydantic
  - aiosqlite（异步 SQLite 支持，可选）

- [ ] 确认数据库文件存储位置
  - 默认：`data/monitor.db`
  - 配置到 `config/settings.yaml`

## Development Tasks

### Phase 1: 数据库层

- [ ] 创建 `src/database.py`
  - [ ] 实现 `Database` 类
  - [ ] 实现 `init_db()` 创建表结构
  - [ ] 实现 `get_connection()` 连接管理
  - [ ] 启用 WAL 模式

- [ ] 实现 UP主 CRUD 操作
  - [ ] `get_ups(is_monitoring=None)` - 查询列表
  - [ ] `get_up_by_mid(mid)` - 按 mid 查询
  - [ ] `add_up(mid, name, face)` - 添加 UP主
  - [ ] `remove_up(up_id)` - 软删除（设置 is_monitoring=0）

- [ ] 实现视频历史 CRUD 操作
  - [ ] `get_videos(page, page_size, filters)` - 分页查询
  - [ ] `get_video_by_bvid(bvid)` - 按 BV号查询
  - [ ] `add_video(...)` - 添加视频记录
  - [ ] `update_video_pushed(bvid, pushed)` - 更新推送状态

- [ ] 实现配置管理操作
  - [ ] `get_config()` - 获取所有配置
  - [ ] `get_config_value(key)` - 获取单个配置
  - [ ] `update_config(key, value)` - 更新配置

- [ ] 实现登录信息操作
  - [ ] `get_auth()` - 获取登录信息
  - [ ] `save_auth(cookies, expires_at)` - 保存登录信息

- [ ] 编写数据迁移脚本 `scripts/migrate_json_to_sqlite.py`
  - [ ] 备份 `data/video_history.json`
  - [ ] 解析 JSON 提取 UP主 去重
  - [ ] 插入 UP主 到 `ups` 表
  - [ ] 插入视频记录到 `videos` 表
  - [ ] 校验迁移前后记录数一致
  - [ ] 输出迁移报告

### Phase 2: 数据模型

- [ ] 创建 `src/models.py`
  - [ ] UP主响应模型 `UpResponse`
  - [ ] UP主添加请求模型 `UpCreateRequest`
  - [ ] 视频历史响应模型 `VideoResponse`
  - [ ] 配置响应模型 `ConfigResponse`
  - [ ] 配置更新请求模型 `ConfigUpdateRequest`
  - [ ] 登录状态响应模型 `LoginStatusResponse`
  - [ ] 二维码响应模型 `QrCodeResponse`
  - [ ] 错误响应模型 `ErrorResponse`
  - [ ] 分页响应模型 `PaginatedResponse`

### Phase 3: FastAPI 框架

- [ ] 创建 `src/web.py`
  - [ ] 创建 FastAPI 应用实例
  - [ ] 配置 CORS 中间件
  - [ ] 配置日志中间件
  - [ ] 注册路由
  - [ ] 配置 Swagger 文档（自动）

- [ ] 创建 `src/api/__init__.py`
  - [ ] 导出所有路由模块

- [ ] 创建 `src/api/ups.py`
  - [ ] `GET /api/ups` - 获取 UP主列表
  - [ ] `POST /api/ups` - 添加 UP主
    - 调用 `BilibiliClient` 验证 mid
    - 获取 UP主 名称和头像
  - [ ] `DELETE /api/ups/{id}` - 移除 UP主

- [ ] 创建 `src/api/videos.py`
  - [ ] `GET /api/videos` - 获取推送历史
    - 实现分页逻辑
    - 实现 UP主 筛选
    - 实现日期范围筛选

- [ ] 创建 `src/api/config.py`
  - [ ] `GET /api/config` - 获取配置
  - [ ] `PUT /api/config` - 更新配置
    - 验证检查间隔 ≥ 5 分钟
    - 验证 Webhook URL 格式

- [ ] 创建 `src/api/login.py`
  - [ ] `GET /api/login/status` - 查询登录状态
    - 检查 Cookie 有效性
    - 计算剩余天数
  - [ ] `GET /api/login/qrcode` - 获取登录二维码
    - 复用 `BilibiliLogin.generate_qrcode()`

- [ ] 添加健康检查端点
  - [ ] `GET /api/health` - 服务健康检查

### Phase 4: 调度器改造

- [ ] 修改 `src/scheduler.py`
  - [ ] 添加 `Database` 实例属性
  - [ ] 改造 `load_history()` - 从数据库加载
  - [ ] 改造 `save_history()` - 写入数据库
  - [ ] 改造 `_record_video()` - 使用数据库插入
  - [ ] 添加 `load_config_from_db()` - 每次循环开始读取配置
  - [ ] 改造构造函数，接收 `Database` 实例

- [ ] 修改 `main.py`
  - [ ] 添加 `--web` 命令行参数
  - [ ] 实现 Web 服务启动逻辑
  - [ ] 修改 `start_monitor()` 初始化 `Database` 实例

- [ ] 更新 `config/settings.yaml`
  - [ ] 添加 `database.path` 配置项

## Testing Tasks

### 单元测试

- [ ] 创建 `tests/test_database.py`
  - [ ] 测试 UP主 CRUD 操作
  - [ ] 测试视频历史 CRUD 操作
  - [ ] 测试配置管理操作
  - [ ] 测试登录信息操作
  - [ ] 使用内存数据库 `:memory:`

- [ ] 创建 `tests/test_api_ups.py`
  - [ ] 测试获取 UP主列表
  - [ ] 测试添加 UP主（正常情况）
  - [ ] 测试添加无效 mid
  - [ ] 测试移除 UP主

- [ ] 创建 `tests/test_api_videos.py`
  - [ ] 测试分页查询
  - [ ] 测试 UP主 筛选
  - [ ] 测试日期范围筛选

- [ ] 创建 `tests/test_api_config.py`
  - [ ] 测试获取配置
  - [ ] 测试更新配置
  - [ ] 测试无效参数验证

- [ ] 创建 `tests/test_api_login.py`
  - [ ] 测试登录状态查询
  - [ ] 测试二维码获取

- [ ] 创建 `tests/test_migration.py`
  - [ ] 测试迁移脚本
  - [ ] 验证数据完整性

### 集成测试

- [ ] 手动测试完整流程
  - [ ] 启动 Web 服务
  - [ ] 通过 API 添加 UP主
  - [ ] 启动监控进程
  - [ ] 验证配置热更新
  - [ ] 验证数据写入数据库

- [ ] 测试并发场景
  - [ ] Web API 和监控进程同时写入
  - [ ] 验证无数据丢失

## Completion Checklist

### 功能验收

- [ ] Web 服务正常启动，访问 `http://localhost:8000/docs` 显示 Swagger 文档
- [ ] 所有 API 端点可通过 Swagger 测试
- [ ] UP主添加时调用 B站 API 验证有效性
- [ ] 推送历史支持分页和筛选
- [ ] 配置修改后监控进程下次循环生效
- [ ] 登录二维码可正常获取
- [ ] 数据迁移成功，记录数与 JSON 一致

### 代码质量

- [ ] 所有单元测试通过
- [ ] 代码符合项目风格
- [ ] 异常处理完善
- [ ] 日志输出清晰

### 文档更新

- [ ] 更新 `README.md`，添加 Web 服务使用说明
- [ ] 更新 `PRD-monitor_onlineVideo.md`，标记 Web 后端已完成
- [ ] 更新 `CHANGELOG-monitor_onlineVideo.md`，记录本次更新

### 部署准备

- [ ] systemd 服务配置文件更新
- [ ] 依赖版本锁定
