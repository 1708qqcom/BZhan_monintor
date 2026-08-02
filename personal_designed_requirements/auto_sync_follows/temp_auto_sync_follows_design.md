# Technical Design - 登录后自动同步关注列表

## Overview

在现有扫码登录流程中增加"同步关注列表"步骤。登录成功后，后端自动调用B站API获取关注列表并写入数据库。同时提供独立API供手动同步使用。

## Architecture

### 影响模块

| 模块 | 文件 | 变化 |
|------|------|------|
| 登录API | `src/api/login.py` | 登录成功后增加同步逻辑 |
| UP主API | `src/api/ups.py` | 新增同步接口 |
| 数据库 | `src/database.py` | 新增批量插入方法（可选） |
| 前端 | `templates/bilibili_login.html` | 优化登录成功后的交互 |

### 数据流

```
前端扫码 → 后端保存Cookie → 调用B站API获取关注 → 批量写入数据库 → 返回结果
```

## API / Interface

### 新增 API

#### POST /api/ups/sync

**功能**：同步当前用户的B站关注列表

**请求**：无参数

**响应**：
```json
{
  "message": "同步成功",
  "data": {
    "total": 50,
    "added": 35,
    "skipped": 15
  }
}
```

**错误**：
- 400：未登录B站账号
- 500：同步失败（网络错误、API限流等）

### 修改 API

#### POST /api/login/poll

**现有响应**：
```json
{
  "message": "登录成功",
  "data": {
    "status": "success",
    "cookies": ["SESSDATA", "bili_jct", ...]
  }
}
```

**新增响应字段**：
```json
{
  "message": "登录成功",
  "data": {
    "status": "success",
    "cookies": ["SESSDATA", "bili_jct", ...],
    "sync_result": {
      "success": true,
      "total": 50,
      "added": 35,
      "skipped": 15,
      "error": null
    }
  }
}
```

## Backend Changes

### src/api/login.py

在 `poll_scan_result()` 函数中，保存Cookie后增加同步逻辑：

```python
# 现有逻辑
db.save_auth(cookies, expires_at=expires_at)

# 新增：自动同步关注列表
sync_result = {"success": False, "total": 0, "added": 0, "skipped": 0, "error": None}

try:
    client = BilibiliClient(cookies=cookies)
    ups = client.get_followed_ups(max_count=50)
    
    sync_result["total"] = len(ups)
    
    for up in ups:
        try:
            db.add_up(mid=up["mid"], name=up["uname"], face=up["face"])
            sync_result["added"] += 1
        except sqlite3.IntegrityError:
            sync_result["skipped"] += 1
    
    sync_result["success"] = True
    logger.info(f"同步关注列表成功: {sync_result}")
    
except Exception as e:
    sync_result["error"] = str(e)
    logger.error(f"同步关注列表失败: {e}")

# 返回响应
return SuccessResponse(
    message="登录成功",
    data={
        "status": "success",
        "cookies": list(cookies.keys()),
        "sync_result": sync_result
    }
)
```

### src/api/ups.py

新增同步接口：

```python
@router.post(
    "/sync",
    response_model=SuccessResponse,
    summary="同步关注列表",
    description="从B站账号同步关注列表到数据库"
)
async def sync_followed_ups(db: Database = Depends(get_db)):
    # 从数据库获取Cookie
    auth = db.get_auth()
    if not auth or not auth.get("cookies"):
        raise HTTPException(
            status_code=400,
            detail="未登录B站账号，请先登录"
        )
    
    try:
        client = BilibiliClient(cookies=auth["cookies"])
        ups = client.get_followed_ups(max_count=50)
        
        added = 0
        skipped = 0
        
        for up in ups:
            try:
                db.add_up(mid=up["mid"], name=up["uname"], face=up["face"])
                added += 1
            except sqlite3.IntegrityError:
                skipped += 1
        
        return SuccessResponse(
            message="同步成功",
            data={"total": len(ups), "added": added, "skipped": skipped}
        )
        
    except Exception as e:
        logger.error(f"同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")
```

### src/database.py

可选：新增批量插入方法提高效率（当前 `add_up()` 已够用）：

```python
def add_ups_batch(self, ups: list[dict]) -> dict:
    """
    批量添加UP主
    
    Args:
        ups: [{"mid": 123, "name": "名字", "face": "url"}, ...]
    
    Returns:
        {"added": 10, "skipped": 5}
    """
    added = 0
    skipped = 0
    
    with self._get_connection() as conn:
        cursor = conn.cursor()
        for up in ups:
            try:
                cursor.execute(...)
                added += 1
            except sqlite3.IntegrityError:
                skipped += 1
        conn.commit()
    
    return {"added": added, "skipped": skipped}
```

## Frontend Changes

### templates/bilibili_login.html

修改 `startPolling()` 函数中的成功处理：

```javascript
if (result.data && result.data.status === 'success') {
    clearInterval(pollTimer);
    pollTimer = null;

    // 显示同步状态
    const syncResult = result.data.sync_result;
    if (syncResult && syncResult.success) {
        document.getElementById('qrcode-status').textContent = 
            `✓ 登录成功，已同步 ${syncResult.added} 个UP主`;
        showSuccess(`登录成功，已同步 ${syncResult.added} 个UP主`);
    } else if (syncResult && !syncResult.success) {
        document.getElementById('qrcode-status').textContent = 
            '登录成功，但同步失败';
        showError(`同步失败: ${syncResult.error}`);
    }

    // 重新加载登录状态
    await loadLoginStatus();

    // 3秒后跳转到UP主管理页面
    setTimeout(() => {
        window.location.href = '/ups';
    }, 2000);
}
```

## File Changes

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/api/login.py` | 修改 | 登录成功后增加同步逻辑 |
| `src/api/ups.py` | 修改 | 新增 `/sync` 端点 |
| `src/database.py` | 可选修改 | 新增批量插入方法 |
| `templates/bilibili_login.html` | 修改 | 优化登录成功交互 |

## Implementation Flow

1. **修改 `src/api/ups.py`**：新增 `/sync` API
2. **修改 `src/api/login.py`**：登录成功后调用同步
3. **修改 `templates/bilibili_login.html`**：优化前端交互
4. **测试验证**：完整流程测试

## Error Handling

| 错误场景 | HTTP状态码 | 处理方式 |
|----------|------------|----------|
| 未登录B站 | 400 | 返回错误提示 |
| Cookie失效 | - | 同步失败但不影响登录 |
| B站API限流 | 500 | 记录日志，返回错误信息 |
| 网络超时 | 500 | 重试3次后返回错误 |
| UP主已存在 | - | 跳过，继续同步其他 |

## Testing Strategy

### 单元测试

- 测试 `/api/ups/sync` 接口
- 测试登录成功后的同步逻辑

### 集成测试

1. 新用户扫码登录 → 验证UP主已同步
2. 已有UP主的用户登录 → 验证跳过已存在
3. Cookie失效场景 → 验证登录成功但同步失败

### 手动测试

```bash
# 1. 清空数据库
rm data/monitor.db

# 2. 启动Web服务
python main.py --web

# 3. 访问登录页面，扫码登录

# 4. 验证UP主列表
curl http://localhost:3231/api/ups
```
