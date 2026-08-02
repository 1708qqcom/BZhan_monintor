# Implementation Todo - 简易 Web 管理页面

## Preparation

- [ ] 确认需求已明确（密码认证、移动端适配、静态文件）
- [ ] 确认技术方案（FastAPI + Jinja2 + Tailwind CSS CDN）
- [ ] 确认文件结构（templates/ 和 static/ 目录）

---

## Development Tasks

### Phase 1: 基础设施

- [ ] **更新依赖文件**
  - 在 `requirements.txt` 添加 `Jinja2>=3.1.0`
  
- [ ] **创建目录结构**
  - 创建 `templates/` 目录
  - 创建 `static/js/` 目录
  - 创建 `static/css/` 目录

- [ ] **修改 src/web.py 配置**
  - 导入 Jinja2、Session 中间件相关模块
  - 配置 `Jinja2Templates(directory="templates")`
  - 挂载静态文件 `app.mount("/static", ...)`
  - 添加 SessionMiddleware（secret_key, max_age=86400）
  - 添加认证中间件（检查 Session，未认证跳转登录页）

- [ ] **创建基础布局模板**
  - 创建 `templates/base.html`
  - 添加 `<head>` 部分（meta、title、Tailwind CSS CDN）
  - 添加导航栏（桌面端横向菜单 + 移动端汉堡菜单）
  - 添加主内容区块 `{% block content %}`
  - 添加页脚
  - 引入 `/static/js/main.js`

### Phase 2: 认证页面

- [ ] **创建登录页面**
  - 创建 `templates/login.html`（继承 base.html）
  - 添加密码输入表单
  - 添加错误提示显示区域
  - 移动端居中布局

- [ ] **实现登录处理**
  - 在 `src/web.py` 添加 `POST /auth/login` 路由
  - 验证密码是否为 `123456`
  - 成功：设置 Session，重定向到 `/`
  - 失败：返回登录页，显示错误

- [ ] **实现登出处理**
  - 在 `src/web.py` 添加 `POST /auth/logout` 路由
  - 清除 Session
  - 重定向到登录页

### Phase 3: 仪表盘页面

- [ ] **创建仪表盘模板**
  - 创建 `templates/dashboard.html`
  - 继承 base.html
  - 添加统计卡片区域（监控数、今日推送、运行时间）

- [ ] **实现仪表盘数据接口**
  - 在 `src/web.py` 添加 `GET /` 路由
  - 调用 API 获取数据（监控数、推送数）
  - 渲染模板并传递数据

- [ ] **前端数据加载**
  - 在 `main.js` 添加仪表盘数据加载逻辑
  - 页面加载时 fetch `/api/health` 和 `/api/videos?page_size=5`
  - 动态更新 DOM 元素

### Phase 4: UP主管理页面

- [ ] **创建UP主管理模板**
  - 创建 `templates/ups.html`
  - 继承 base.html
  - 添加搜索筛选输入框
  - 添加 UP主列表容器
  - 添加"添加 UP主"表单（模态框或折叠面板）
  - 添加分页控件

- [ ] **实现UP主管理路由**
  - 在 `src/web.py` 添加 `GET /ups` 路由
  - 渲染模板

- [ ] **前端交互实现**
  - 在 `main.js` 添加 UP主列表加载逻辑（fetch `/api/ups`）
  - 添加搜索筛选逻辑（实时搜索）
  - 添加"添加 UP主"表单提交逻辑（fetch `/api/ups` POST）
  - 添加"移除 UP主"按钮逻辑（fetch `/api/ups/{id}` DELETE）
  - 实现分页逻辑

### Phase 5: 推送历史页面

- [ ] **创建推送历史模板**
  - 创建 `templates/videos.html`
  - 继承 base.html
  - 添加筛选区域（UP主下拉、日期范围）
  - 添加历史列表容器（桌面端表格、移动端卡片）
  - 添加分页控件

- [ ] **实现推送历史路由**
  - 在 `src/web.py` 添加 `GET /videos` 路由
  - 渲染模板

- [ ] **前端交互实现**
  - 在 `main.js` 添加历史列表加载逻辑（fetch `/api/videos`）
  - 添加筛选逻辑（UP主、日期）
  - 实现分页逻辑
  - 移动端卡片布局适配

### Phase 6: 配置管理页面

- [ ] **创建配置管理模板**
  - 创建 `templates/config.html`
  - 继承 base.html
  - 添加配置表单（检查间隔、最大UP主数、Webhook）
  - 添加"保存配置"按钮
  - 添加"测试推送"按钮

- [ ] **实现配置管理路由**
  - 在 `src/web.py` 添加 `GET /config` 路由
  - 渲染模板

- [ ] **前端交互实现**
  - 在 `main.js` 添加配置加载逻辑（fetch `/api/config`）
  - 添加表单提交逻辑（fetch `/api/config` PUT）
  - 添加"测试推送"逻辑（调用飞书 API）
  - 显示保存成功/失败提示

### Phase 7: B站登录管理页面

- [ ] **创建登录管理模板**
  - 创建 `templates/bilibili_login.html`
  - 继承 base.html
  - 添加登录状态显示区域（用户名、过期时间、剩余天数）
  - 添加二维码显示区域
  - 添加"刷新二维码"按钮

- [ ] **实现登录管理路由**
  - 在 `src/web.py` 添加 `GET /bilibili-login` 路由
  - 渲染模板

- [ ] **前端交互实现**
  - 在 `main.js` 添加二维码加载逻辑（fetch `/api/login/qrcode`）
  - 添加状态轮询逻辑（setInterval 3秒，fetch `/api/login/status`）
  - 扫码成功后自动刷新页面
  - 显示登录状态变化

### Phase 8: 前端交互脚本

- [ ] **创建 main.js 基础结构**
  - 创建 `static/js/main.js`
  - 添加工具函数（fetch 封装、错误处理）
  - 添加全局状态管理

- [ ] **实现通用功能**
  - 导航栏移动端折叠/展开
  - 全局错误提示组件
  - Loading 状态显示

- [ ] **测试所有交互**
  - 测试表单提交
  - 测试搜索筛选
  - 测试分页
  - 测试二维码轮询

---

## Testing Tasks

### 单元测试

- [ ] 测试认证中间件（正确密码、错误密码、Session 过期）
- [ ] 测试页面路由（已登录、未登录）

### 集成测试

- [ ] 测试登录 → 访问页面 → 登出流程
- [ ] 测试添加 UP主 → 列表更新 → 移除 UP主流程
- [ ] 测试修改配置 → 保存成功流程

### 手动测试

- [ ] 桌面端浏览器测试（Chrome、Firefox）
- [ ] 移动端浏览器测试（iOS Safari、Android Chrome）
- [ ] 响应式布局测试（缩放浏览器窗口）

---

## Completion Checklist

### 功能完整性

- [ ] 密码 `123456` 认证成功
- [ ] 错误密码显示错误提示
- [ ] 未登录访问跳转到登录页
- [ ] 仪表盘数据正确显示
- [ ] UP主添加/移除功能正常
- [ ] 推送历史分页筛选正常
- [ ] 配置修改保存成功
- [ ] B站二维码显示正常
- [ ] 扫码登录流程正常

### 响应式设计

- [ ] 桌面端布局正常
- [ ] 移动端布局正常
- [ ] 导航栏移动端折叠
- [ ] 表格移动端自适应

### 代码质量

- [ ] 代码符合项目风格
- [ ] 无语法错误
- [ ] 无明显性能问题
- [ ] 日志输出合理

### 文档更新

- [ ] 更新 README.md（添加 Web 访问说明）
- [ ] 更新 CHANGELOG-monitor_onlineVideo.md
- [ ] 归档设计文档到 `personal_designed_requirements/`