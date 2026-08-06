# 经验复盘 - B站UP主视频监控服务

---

## 2026-08-06 — 稍后再看页面视频封面无法显示（B站防盗链）

**场景**
- 稍后再看页面（`/toview`）加载后，视频封面显示为SVG占位符图标
- 浏览器开发者工具检查：
  - `<img>` 标签的 `src` 属性正确指向 `https://i2.hdslb.com/bfs/archive/xxx.jpg`
  - 图片请求返回 `403 Forbidden` 或 `ERR_BLOCKED_BY_ORB`
  - 触发 `onerror` 事件，显示SVG占位符

**原因**
1. **B站图片服务器防盗链机制**：
   - 检查 HTTP 请求的 `Referer` 头
   - `Referer` 为 `*.bilibili.com` → 200 OK（允许）
   - `Referer` 为其他域名 → 403 Forbidden（拒绝）
2. **浏览器默认行为**：
   - 从 `http://123.57.88.156:3231/toview` 页面请求图片
   - 自动带上 `Referer: http://123.57.88.156:3231/toview` 头
   - B站服务器检测到非白名单域名，拒绝访问
3. **测试验证**：
   ```bash
   # 不带Referer: 200 OK (50692 bytes)
   curl https://i2.hdslb.com/bfs/archive/xxx.jpg
   
   # 带bilibili Referer: 200 OK (50692 bytes)
   curl -H "Referer: https://www.bilibili.com/" https://i2.hdslb.com/bfs/archive/xxx.jpg
   
   # 带外部Referer: 403 Forbidden (146 bytes)
   curl -H "Referer: http://123.57.88.156:3231/" https://i2.hdslb.com/bfs/archive/xxx.jpg
   ```

**解决**
- **方案（推荐）**：在 `<img>` 标签添加 `referrerpolicy="no-referrer"` 属性
  ```html
  <img src="https://i2.hdslb.com/bfs/archive/xxx.jpg"
       referrerpolicy="no-referrer"
       loading="lazy"
       alt="视频封面">
  ```
  - 浏览器发送图片请求时**不携带 Referer 头**
  - B站服务器接受无 Referer 的请求（返回 200 OK）
  - 简单有效，适用于开发环境和内部管理系统

**涉及文件**
- `templates/toview.html` — 用户稍后再看页面（第131行）
- `templates/admin_toview.html` — 管理员页面（保持一致）

**关键点**
- 图片URL协议需转换为HTTPS（避免Mixed Content）
- 添加 `loading="lazy"` 优化加载性能
- `onerror` 处理显示SVG占位符作为降级方案

**预防**
- 所有使用B站图片的地方统一添加 `referrerpolicy="no-referrer"`
- 包括：UP主头像、视频封面、用户头像等
- 在模板基类或组件中封装，避免遗漏

**标签**：`#防盗链` `#Referer` `#图片加载` `#403错误` `#稍后再看`

---

## 2026-08-02 — 推送历史页面播放量和推送时间无法显示

**场景**
- Web 管理后台推送历史页面（`/videos`）
- 播放量列显示为 `0`
- 推送时间列为空
- 数据库中 `view_count` 字段为 0，`pushed_at` 字段为 `NULL`

**原因**
1. **JSON 历史数据缺失字段**：原 `video_history.json` 只记录了 `bvid`、`title`、`up_id` 等基础信息，没有播放量数据
2. **推送时间未记录**：JSON 中 `pushed_at` 字段值为 `null`
3. **迁移脚本未补全**：`migrate_json_to_sqlite.py` 直接将缺失字段设为 0 和 NULL，未调用 B站 API 获取真实数据
4. **缺少后续更新机制**：迁移后没有脚本定期更新视频统计数据

**解决**
- **创建更新脚本** `scripts/update_video_stats.py`：
  1. 调用 B站视频信息 API (`/x/web-interface/view`) 获取播放量
  2. 对于没有推送时间的历史数据，设置为迁移当天时间
  3. 批量更新数据库
- **关键代码**：
  ```python
  # 获取视频信息
  video_info = client.get_video_info(bvid=bvid)
  new_view_count = video_info["stat"]["view"]
  
  # 推送时间：如果原数据为空，使用迁移日期
  new_pushed_at = old_pushed_at if old_pushed_at else migration_date
  
  # 更新数据库
  cursor.execute("""
      UPDATE videos
      SET view_count = ?, pushed_at = ?
      WHERE bvid = ?
  """, (new_view_count, new_pushed_at, bvid))
  ```

**预防**
- 新视频入库时应同时获取播放量等统计数据
- 定期运行更新脚本保持数据新鲜度
- 考虑在监控流程中增加播放量更新逻辑

**标签**：`#数据迁移` `#播放量` `#B站API` `#数据补全`

---

## 2026-08-02 — B站图片防盗链导致前端无法渲染头像

**场景**
- Web 管理后台 UP 主列表页面，头像 URL 正确：`https://i2.hdslb.com/bfs/face/xxx.jpg`
- 浏览器控制台显示图片请求返回 403 Forbidden
- 图片无法显示，只显示空白或占位图

**原因**
1. **B站防盗链机制**：B站图片服务器检查 HTTP 请求的 `Referer` 头
   - `Referer` 为 `*.bilibili.com` 域名 → 正常返回图片
   - `Referer` 为其他域名（如 `localhost:8000`）→ 返回 403
2. **浏览器默认行为**：从 `http://localhost:8000/ups` 页面请求 B站图片时，会自动带上 `Referer: http://localhost:8000/ups` 头
3. **开发环境无 B站域名**：本地开发无法使用 B站域名，必然触发防盗链

**解决**
- **方案一（推荐）**：在 `<img>` 标签添加 `referrerpolicy="no-referrer"` 属性
  ```html
  <img src="https://i2.hdslb.com/bfs/face/xxx.jpg" referrerpolicy="no-referrer">
  ```
  - 浏览器发送图片请求时不带 `Referer` 头
  - B站服务器接受无 `Referer` 的请求
  - 简单有效，适用于开发环境和内部管理系统

- **方案二**：后端代理图片
  - 增加服务器流量开销
  - 适合对外公开的生产环境

- **方案三**：使用第三方图片代理服务（如 `images.weserv.nl`）
  - 将 `i0.hdslb.com` 替换为代理域名
  - 依赖第三方服务稳定性

**涉及文件**
- `templates/ups.html` — UP 主列表页面

**标签**：`#防盗链` `#Referer` `#图片加载` `#403错误`

---

## 2026-08-02 — 飞书测试推送报错 'FeishuNotifier' object has no attribute 'send_message'

**场景**
- Web 管理后台配置飞书群机器人 Webhook 地址后点击"发送测试消息"
- 前端报错：`✗ 发送失败: 'FeishuNotifier' object has no attribute 'send_message'`
- 后端日志：`AttributeError: 'FeishuNotifier' object has no attribute 'send_message'` 在 `src/api/config.py:158`

**原因**
- **API 调用与类方法不匹配**：`config.py` 的 `test_push()` 函数调用了 `notifier.send_message(request.message)`
- **FeishuNotifier 类缺少通用方法**：`src/feishu.py` 只定义了两个专门方法：
  - `send_new_video_notification()` - 发送新视频通知卡片
  - `send_error_notification()` - 发送错误告警卡片
- **测试功能未考虑**：开发时专注于业务通知场景，未提供简单的测试消息发送能力

**解决**
- 在 `FeishuNotifier` 类中新增 `send_message(message: str)` 方法
- 使用飞书简单的 `text` 消息类型（而非交互式卡片）
- 复用现有的 `_send_webhook()` 方法发送请求
- 代码修改：
  ```python
  def send_message(self, message: str) -> bool:
      """发送简单文本消息（用于测试）"""
      payload = {
          "msg_type": "text",
          "content": {"text": message}
      }
      return self._send_webhook(payload)
  ```

**标签**：`#飞书推送` `#AttributeError` `#API设计` `#测试功能`

---

## 2026-08-02 — Web 扫码登录前端无法获取登录状态

**场景**
- Web 管理后台点击"获取二维码"正常显示
- 用户使用 B站 App 扫码确认成功
- 前端轮询 `/api/login/status` 始终返回 `is_logged_in: false`
- 终端日志显示二维码生成成功，但没有后续扫码成功的记录

**原因**
1. **缺失关键 API 端点**：后端只有 `/api/login/qrcode`（生成二维码）和 `/api/login/status`（查询状态），缺少轮询扫码结果的端点
2. **流程断裂**：
   - ✅ 前端获取二维码
   - ✅ 用户扫码确认
   - ❌ **后端没有轮询 B站接口确认扫码状态**
   - ❌ **扫码成功后没有保存 Cookie 到数据库**
   - ✅ 前端轮询登录状态（但数据库永远没有数据）
3. **auth_code 未传递**：`BilibiliLogin.generate_qrcode()` 返回的 `auth_code` 用于轮询扫码结果，但 API 层没有保存和传递它
4. **前端轮询对象错误**：前端轮询 `/api/login/status` 只是查询数据库状态，不会触发后端去 B站验证扫码结果

**解决**
- **新增 `/api/login/poll` 端点**：
  ```python
  @router.post("/poll")
  async def poll_scan_result():
      # 1. 获取保存的 auth_code
      # 2. 调用 BilibiliLogin.poll_scan_result(auth_code)
      # 3. 扫码成功则保存 Cookie 到数据库
  ```
- **临时存储 auth_code**：在 `/api/login/qrcode` 生成二维码时保存 `auth_code` 到模块级变量（生产环境应用 Redis）
- **前端修改轮询逻辑**：从轮询 `/api/login/status` 改为调用 `/api/login/poll`
  ```javascript
  // 旧：const status = await fetchAPI('/api/login/status')
  // 新：const result = await fetchAPI('/api/login/poll', { method: 'POST' })
  ```
- **完整流程**：
  1. 前端调用 `/api/login/qrcode` → 后端生成二维码，保存 `auth_code`
  2. 用户扫码确认
  3. 前端每 2 秒调用 `/api/login/poll` → 后端用 `auth_code` 轮询 B站接口
  4. 扫码成功 → 后端保存 Cookie 到数据库 → 前端收到 `status: success`

**涉及文件**
- `src/api/login.py` — 新增 `/poll` 端点
- `templates/bilibili_login.html` — 前端轮询逻辑

**标签**：`#扫码登录` `#流程缺失` `#API设计` `#前后端协作`

---

## 2026-08-02 — FastAPI 中间件执行顺序导致 SessionMiddleware 未生效

**场景**
- 实现 Web 管理后台的认证中间件，需要访问 `request.session`
- 启动服务后访问任何页面都报错：`SessionMiddleware must be installed to access request.session`
- 已在代码中使用 `app.add_middleware(SessionMiddleware, ...)` 注册了 Session 中间件
- 认证中间件使用 `@app.middleware("http")` 装饰器注册

**原因**
1. **中间件注册方式混合**：同时使用 `@app.middleware("http")` 装饰器和 `app.add_middleware()` 方法
2. **执行顺序错误**：
   - `@app.middleware("http")` 装饰器注册的中间件总是在 `add_middleware()` 之前执行
   - 无论代码定义顺序如何，装饰器注册的中间件优先级更高
3. **对 BaseHTTPMiddleware 执行顺序的误解**：
   - `BaseHTTPMiddleware` 的执行顺序与注册顺序**相同**（FIFO）
   - 普通 `add_middleware()` 的执行顺序与注册顺序**相反**（LIFO）
4. **Session 未初始化**：认证中间件在 SessionMiddleware 之前执行，导致 `request.session` 不存在

**解决**
- **统一注册方式**：将所有中间件都改为继承 `BaseHTTPMiddleware` 类，使用 `app.add_middleware()` 注册
- **调整注册顺序**：
  - 注册顺序：Auth → Log → Session → CORS
  - 实际执行顺序（FIFO）：Auth → Log → Session → CORS
- **关键代码**：
  ```python
  # 1. 认证中间件（最先执行）
  class AuthMiddleware(BaseHTTPMiddleware):
      async def dispatch(self, request, call_next):
          authenticated = request.session.get("authenticated", False)
          # ...
  app.add_middleware(AuthMiddleware)

  # 2. 日志中间件
  class LogMiddleware(BaseHTTPMiddleware):
      # ...
  app.add_middleware(LogMiddleware)

  # 3. Session 中间件
  app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400)

  # 4. CORS 中间件（最后执行）
  app.add_middleware(CORSMiddleware, allow_origins=["*"])
  ```

**验证**
- 访问 `/` 自动跳转到 `/auth/login`
- 登录成功后 Session 正常写入
- 后续请求可正常读取 `request.session`

**标签**：`#FastAPI` `#中间件` `#SessionMiddleware` `#执行顺序` `#BaseHTTPMiddleware`

---

## 2026-08-02 — Web API 返回空数据但日志显示查询成功

**场景**
- 启动 Web 服务后访问 `/api/ups` 端点，返回空列表 `{"items": [], "total": 0}`
- 终端日志显示：`查询到 0 个 UP主`、`返回 0 个UP主`
- 数据库文件 `data/monitor.db` 存在且大小为 56KB
- 同目录下有 `video_history.json` 文件（76KB）包含历史数据

**原因**
1. **数据库刚初始化**：虽然数据库文件存在，但表是空的，没有执行数据迁移
2. **新旧存储并存**：项目同时支持 JSON 文件和 SQLite 数据库，历史数据在 JSON 中，数据库是新建的空库
3. **缺少自动迁移**：Web 服务启动时只初始化空数据库，未检测并迁移已有 JSON 数据

**解决**
- 执行数据迁移脚本：
  ```bash
  python scripts/migrate_json_to_sqlite.py
  ```
- 迁移结果：50 个 UP主、246 条视频记录、0 条失败
- JSON 文件自动备份为 `video_history.json.backup_{timestamp}`
- 迁移后 API 正常返回数据

**预防**
- Web 服务启动时可检测 `video_history.json` 是否存在且数据库为空，提示用户迁移
- 或提供 `--migrate` 参数自动迁移旧数据

**标签**：`#数据迁移` `#SQLite` `#空数据库` `#Web API`

## 2026-08-02 — 视频发布时间字段为 None 导致时间转换报错

**场景**
- 实现 `main.py` 飞书推送功能时，测试推送报错：`'NoneType' object cannot be interpreted as an integer`
- 错误发生在 `datetime.fromtimestamp(test_video['pubdate'])` 这一行
- 终端显示获取视频列表成功，但推送时失败

**原因**
1. **B站API返回数据不一致**：视频列表接口返回的字段中，发布时间字段可能缺失或为 `None`
2. **字段名称不确定**：B站不同接口可能使用不同字段名（`pubdate` 或 `created`）
3. **缺少空值检查**：直接将 `None` 传递给 `datetime.fromtimestamp()` 导致类型错误

**解决**
- **兼容多字段名**：在 `src/bilibili.py` 中同时检查 `pubdate` 和 `created` 字段
  ```python
  pubdate = item.get("pubdate") or item.get("created")
  ```
- **空值处理**：在 `main.py` 中添加空值检查和降级逻辑
  ```python
  pubdate = test_video.get('pubdate')
  if pubdate:
      pub_time = datetime.fromtimestamp(pubdate).strftime('%Y-%m-%d %H:%M:%S')
  else:
      pub_time = "未知时间"
      logger.warning(f"视频缺少发布时间字段: {test_video.get('bvid')}")
  ```
- **播放量空值处理**：同时处理 `play` 字段可能为 `None` 的情况
  ```python
  view_count = test_video.get('play') or 0
  ```

**标签**：`#空值处理` `#B站API` `#TypeError` `#数据兼容性`

---

## 2026-08-02 — B站API WBI签名循环依赖导致-403错误

**场景**
- 登录成功后验证Cookie有效，但获取UP主视频列表时报错：`[错误码:-403] 访问权限不足`
- 使用 `USER_INFO_API` (`/x/space/wbi/acc/info`) 获取WBI密钥时也返回 `-403`
- 形成循环依赖：获取WBI密钥需要调用API → 该API需要WBI签名 → 签名又需要密钥

**原因**
1. **WBI密钥获取接口选择错误**：`USER_INFO_API` 接口本身需要WBI签名才能访问
2. **对B站API签名机制理解不足**：并非所有接口都需要WBI签名，`/x/web-interface/nav` 接口无需签名且返回WBI密钥
3. **Cookie验证接口选择不当**：使用需要WBI签名的接口验证Cookie，导致不必要的签名开销

**解决**
- **获取WBI密钥**：改用 `NAV_API` (`/x/web-interface/nav`) 接口
  - 该接口无需WBI签名
  - 返回数据包含 `wbi_img.img_url` 和 `wbi_img.sub_url` 字段
  - 从URL中提取密钥：`img_url.split("/")[-1].split(".")[0]`
- **验证Cookie**：同样使用 `NAV_API` 接口
  - 无需签名，响应快速
  - 返回 `uname` 字段可验证用户身份
- **WBI签名流程**：
  1. 从 `nav` 接口获取 `img_key` 和 `sub_key`
  2. 缓存密钥（10分钟有效期）
  3. 使用密钥对需要签名的接口参数进行签名

**标签**：`#WBI签名` `#B站API` `#循环依赖` `#-403错误`

---

## 2026-08-02 — B站扫码登录 Cookie 获取失败

**场景**
- 用户使用 B站 App 扫码确认登录后，终端显示"登录成功"但无法获取到 Cookie
- 本项目使用 `qrcode` 库生成终端二维码
- 轮询接口使用 `/x/passport-login/web/qrcode/check`

**原因**
1. **轮询 API 端点错误**：应该使用 `/x/passport-login/web/qrcode/poll` 而非 `/check`
2. **缺少必要参数**：需要添加 `source=main-fe-header` 参数
3. **Cookie 提取方式错误**：B站登录成功后返回 `redirect_url`，需要请求该 URL 让 Cookie 写入 session，再从 cookie jar 提取；而非直接从响应体解析
4. **二维码库选择**：`qrcode` 库的终端输出不够紧凑，yutto 使用的 `segno` 库更简洁，一行代码 `qr.terminal(compact=True)` 即可

**解决**
- 替换依赖：`qrcode` + `pillow` → `segno`
- 修正 API 端点：`/check` → `/poll`
- 添加参数：`source=main-fe-header`
- 重构 Cookie 提取流程：
  1. 登录成功后获取 `redirect_url`
  2. 请求 `redirect_url` 让 Cookie 写入 `session.cookies`
  3. 从 cookie jar 提取 `SESSDATA`、`bili_jct` 等
  4. 备选：从 URL 参数解析
- 优化轮询逻辑：使用 `time.monotonic()` 计时，只在状态变化时输出日志

**参考**
- yutto 源码：`E:\python3\Lib\site-packages\yutto\login.py`
- 关键状态码：`86101`(未扫描) / `86090`(已扫描) / `0`(成功) / `86038`(过期)

**标签**：`#扫码登录` `#Cookie` `#B站API`
