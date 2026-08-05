# Implementation Todo


## Preparation

- [ ] 确认数据库 `ups` 表已有 `user_id` 字段（支持用户隔离）
- [ ] 确认数据库 `videos` 表已有 `pushed_at` 字段（支持日期筛选）
- [ ] 备份当前代码（可选，建议创建 git 分支）


## Development Tasks

### 阶段一：后端改造（UP主分页）

#### 1. 修改 src/database.py

- [ ] 在 `get_ups()` 方法中添加 `page`、`page_size`、`keyword` 参数
- [ ] 实现 SQL 分页查询（LIMIT OFFSET）
- [ ] 实现关键词搜索（name LIKE 或 mid LIKE）
- [ ] 新增 `get_ups_count()` 方法，查询符合条件的 UP主总数

#### 2. 修改 src/models.py

- [ ] 新增 `PaginatedUpResponse` 响应模型
- [ ] 包含字段：`items`、`total`、`page`、`page_size`

#### 3. 修改 src/api/ups.py

- [ ] 在 `get_ups()` 函数中添加 `page`、`page_size`、`keyword` 查询参数
- [ ] 调用 `get_ups_count()` 查询总数
- [ ] 调用 `get_ups()` 时传入分页参数
- [ ] 返回 `PaginatedUpResponse` 格式响应

#### 4. 验证后端改造

- [ ] 使用浏览器访问 `/api/ups?page=1&page_size=5` 验证分页
- [ ] 使用浏览器访问 `/api/ups?keyword=测试` 验证搜索
- [ ] 检查响应格式是否包含 `total`、`page`、`page_size`


### 阶段二：前端改造（推送历史日期默认值）

#### 1. 修改 templates/videos.html

- [ ] 在 `DOMContentLoaded` 事件中添加日期默认值设置逻辑
- [ ] 使用 `new Date().toISOString().split('T')[0]` 获取今天日期
- [ ] 设置 `filter-date-from` 和 `filter-date-to` 的 value 属性
- [ ] 修改重置按钮逻辑：恢复到今天日期而非清空

#### 2. 验证推送历史改造

- [ ] 刷新推送历史页面，检查日期是否自动设置为今天
- [ ] 检查是否自动加载今日推送数据
- [ ] 点击重置按钮，确认日期恢复到今天


### 阶段三：前端改造（UP主列表懒加载）

#### 1. 修改 templates/ups.html - 状态变量

- [ ] 添加分页状态变量：`currentPage`、`pageSize`、`totalPages`、`total`、`isLoading`
- [ ] 添加搜索状态变量：`searchKeyword`、`searchDebounceTimer`

#### 2. 修改 templates/ups.html - 加载函数

- [ ] 改造 `loadUps()` 函数，支持 `page` 和 `append` 参数
- [ ] 添加 `isLoading` 状态控制，防止重复请求
- [ ] 构造 URL 参数：`page`、`page_size`、`keyword`（如有）
- [ ] `append=true` 时追加数据，`append=false` 时替换数据
- [ ] 更新分页状态：`totalPages`、`currentPage`

#### 3. 修改 templates/ups.html - 滚动监听

- [ ] 添加 `setupScrollListener()` 函数
- [ ] 监听滚动容器（`.ups-list-container`）的 scroll 事件
- [ ] 判断是否滚动到底部（距底部 < 100px）
- [ ] 触发加载下一页（`loadUps(currentPage + 1, true)`）

#### 4. 修改 templates/ups.html - 搜索功能

- [ ] 移除原有前端搜索逻辑
- [ ] 添加搜索输入防抖处理（500ms）
- [ ] 防抖触发后调用 `loadUps(1, false)`，传入搜索关键词
- [ ] 清空搜索框时恢复全量数据

#### 5. 修改 templates/ups.html - 加载状态 UI

- [ ] 在列表底部添加 `<div id="load-status">` 元素
- [ ] 添加 `updateLoadStatus()` 函数，根据状态显示提示
- [ ] 加载中：显示"加载中..."
- [ ] 未加载完：显示"下拉加载更多..."
- [ ] 已加载完：显示"已加载全部 N 个 UP主"

#### 6. 修改 templates/ups.html - 初始化

- [ ] 在 `DOMContentLoaded` 中调用 `setupScrollListener()`
- [ ] 初始加载改为 `loadUps(1, false)`


### 阶段四：UI 优化

#### 1. 加载状态样式

- [ ] 添加加载中动画效果（可选使用骨架屏）
- [ ] 添加"加载更多"区域样式

#### 2. 响应式适配

- [ ] 测试移动端滚动加载效果
- [ ] 确认移动端搜索功能正常


## Testing Tasks

### 功能测试

- [ ] **UP主分页加载**
  - [ ] 初始加载显示 20 条数据
  - [ ] 滚动到底部自动加载下一页
  - [ ] 加载过程显示状态提示
  - [ ] 全部加载完毕显示"已加载全部"

- [ ] **UP主搜索**
  - [ ] 输入关键词后 500ms 触发搜索
  - [ ] 搜索结果支持分页懒加载
  - [ ] 清空搜索框恢复全量数据

- [ ] **推送历史日期默认值**
  - [ ] 页面打开时日期自动设置为今天
  - [ ] 自动加载今日推送数据
  - [ ] 重置按钮恢复到今天日期

- [ ] **边界情况**
  - [ ] UP主数据为空时显示提示
  - [ ] 搜索无结果时显示提示
  - [ ] 网络错误时显示错误提示


### 性能测试

- [ ] UP主页面初始加载时间 < 2 秒
- [ ] 滚动加载响应时间 < 1 秒
- [ ] 搜索响应时间 < 1 秒
- [ ] 测试 100+ UP主数据下的性能


### 兼容性测试

- [ ] Chrome 浏览器测试
- [ ] Firefox 浏览器测试
- [ ] 移动端浏览器测试（iOS Safari、Android Chrome）


## Completion Checklist

- [ ] 后端 API 支持分页和搜索参数
- [ ] 前端 UP主页面支持滚动加载
- [ ] 前端 UP主搜索改为后端搜索
- [ ] 前端推送历史页面日期默认今天
- [ ] 所有功能测试通过
- [ ] 性能测试通过
- [ ] 代码已提交到 git
- [ ] 文档已更新（如有必要）
