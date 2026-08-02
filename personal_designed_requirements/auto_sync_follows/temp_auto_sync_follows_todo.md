# Implementation Todo - 登录后自动同步关注列表

## Preparation

- [x] 分析现有登录流程
- [x] 确认B站API可用性（`get_followed_ups` 已实现）
- [x] 确认数据库表结构（`ups` 表已存在）

## Development Tasks

### Task 1: 新增同步API

**文件**: `src/api/ups.py`

**任务**:
- [ ] 新增 `POST /api/ups/sync` 端点
- [ ] 从数据库获取Cookie
- [ ] 调用 `BilibiliClient.get_followed_ups()`
- [ ] 遍历写入数据库（处理重复）
- [ ] 返回同步结果

**验证**: 使用 `curl -X POST http://localhost:3231/api/ups/sync` 测试

---

### Task 2: 登录成功后自动同步

**文件**: `src/api/login.py`

**任务**:
- [ ] 在 `poll_scan_result()` 中，保存Cookie后增加同步逻辑
- [ ] 导入 `BilibiliClient` 和 `sqlite3.IntegrityError`
- [ ] 调用 `get_followed_ups(max_count=50)`
- [ ] 遍历调用 `db.add_up()`
- [ ] 捕获 `IntegrityError` 跳过已存在
- [ ] 构造 `sync_result` 加入响应
- [ ] 异常处理：同步失败不影响登录成功

**验证**: 扫码登录后检查响应中是否包含 `sync_result`

---

### Task 3: 优化前端交互

**文件**: `templates/bilibili_login.html`

**任务**:
- [ ] 修改 `startPolling()` 中的成功处理逻辑
- [ ] 解析 `result.data.sync_result`
- [ ] 显示同步成功/失败信息
- [ ] 登录成功后2秒自动跳转到 `/ups`

**验证**: 前端测试完整登录流程

---

### Task 4: 更新API文档（可选）

**文件**: 无（FastAPI自动生成）

**说明**: FastAPI会自动更新 `/docs` 文档

---

## Testing Tasks

### 单元测试

- [ ] 测试 `/api/ups/sync` 成功场景
- [ ] 测试 `/api/ups/sync` 未登录场景
- [ ] 测试登录成功后同步逻辑

### 集成测试

- [ ] 清空数据库 → 扫码登录 → 验证UP主已同步
- [ ] 数据库已有UP主 → 再次登录 → 验证跳过已存在
- [ ] 模拟Cookie失效 → 验证同步失败不影响登录

### 手动测试

```bash
# 1. 清空数据库
rm data/monitor.db

# 2. 启动服务
python main.py --web

# 3. 浏览器访问
http://localhost:3231/bilibili-login

# 4. 扫码登录

# 5. 验证结果
curl http://localhost:3231/api/ups
```

---

## Completion Checklist

- [ ] `POST /api/ups/sync` API 已实现
- [ ] 登录成功后自动同步已实现
- [ ] 前端交互已优化
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 手动测试通过
- [ ] 代码已提交

---

## Risk Notes

1. **B站API限流**: 短时间内频繁调用可能被限流，同步失败需友好提示
2. **数据量**: 用户关注数可能超过50，需告知用户只会同步前50个
3. **Cookie有效期**: 同步时Cookie可能刚过期，需处理此异常情况
