# Technical Design


## Overview

本次改动涉及两个独立功能点：
1. **UP主管理页面分页懒加载**：改造前后端数据加载方式，从一次性全量加载改为分页懒加载
2. **推送历史日期默认值**：前端页面加载时自动设置日期选择器默认值为当天


## Architecture

### 系统影响范围

```
前端层：
  templates/ups.html       # UP主页面：添加滚动加载逻辑、搜索改造
  templates/videos.html    # 推送历史页面：日期默认值设置

后端 API 层：
  src/api/ups.py          # UP主 API：添加分页和搜索参数

数据库层：
  src/database.py         # Database.get_ups() 方法：添加分页和搜索支持
```


## Data Model

### 数据库查询变化

**当前**：
```sql
SELECT * FROM ups WHERE user_id = ? ORDER BY created_at DESC
```

**改造后**：
```sql
SELECT COUNT(*) FROM ups WHERE user_id = ? AND (name LIKE ? OR mid LIKE ?)

SELECT * FROM ups
WHERE user_id = ? AND (name LIKE ? OR mid LIKE ?)
ORDER BY created_at DESC
LIMIT ? OFFSET ?
```


## API / Interface

### GET /api/ups 改造

**当前请求**：
```
GET /api/ups
```

**改造后请求**：
```
GET /api/ups?page=1&page_size=20&keyword=测试
```

**请求参数**：
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | int | 否 | 1 | 页码 |
| page_size | int | 否 | 20 | 每页数量 |
| keyword | string | 否 | "" | 搜索关键词（匹配名称或 mid） |

**响应格式**：
```json
{
  "items": [
    {
      "id": 1,
      "mid": 123456,
      "name": "UP主名称",
      "face": "头像URL",
      "is_monitoring": true,
      "created_at": "2024-01-01 12:00:00",
      "latest_videos": [...]
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```


## Frontend Changes

### UP主页面（templates/ups.html）

#### 1. 添加分页状态变量

```javascript
// 分页状态
let currentPage = 1;
let pageSize = 20;
let totalPages = 1;
let total = 0;
let isLoading = false;
let searchKeyword = '';
```

#### 2. 改造 loadUps() 函数

```javascript
async function loadUps(page = 1, append = false) {
    if (isLoading) return;
    isLoading = true;

    // 显示加载状态
    showLoadingState();

    try {
        const params = new URLSearchParams({
            page: page,
            page_size: pageSize
        });

        if (searchKeyword) {
            params.append('keyword', searchKeyword);
        }

        const response = await fetchAPI(`/api/ups?${params.toString()}`);

        const ups = response.items || [];
        total = response.total || 0;
        totalPages = Math.ceil(total / pageSize);
        currentPage = page;

        if (append) {
            allUps = [...allUps, ...ups];  // 追加数据
        } else {
            allUps = ups;  // 替换数据
        }

        renderUpsList(allUps, append);
        updateTotalCount(total);
        updateLoadStatus();

    } catch (error) {
        showError('加载失败: ' + error.message);
    } finally {
        isLoading = false;
        hideLoadingState();
    }
}
```

#### 3. 添加滚动监听

```javascript
function setupScrollListener() {
    const container = document.querySelector('.ups-list-container');

    container.addEventListener('scroll', function() {
        if (isLoading || currentPage >= totalPages) {
            return;
        }

        // 距离底部 100px 时触发加载
        if (container.scrollHeight - container.scrollTop - container.clientHeight < 100) {
            loadUps(currentPage + 1, true);
        }
    });
}
```

#### 4. 改造搜索功能

```javascript
let searchDebounceTimer = null;

document.getElementById('search-input').addEventListener('input', function(e) {
    const keyword = e.target.value.trim();

    // 防抖处理
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        searchKeyword = keyword;
        currentPage = 1;
        allUps = [];
        loadUps(1, false);
    }, 500);
});
```

#### 5. 添加加载状态 UI

```html
<!-- 列表底部加载提示 -->
<div id="load-status" class="py-4 text-center text-sm text-gray-500">
    <!-- 动态内容 -->
</div>
```

```javascript
function updateLoadStatus() {
    const statusEl = document.getElementById('load-status');

    if (currentPage >= totalPages) {
        if (total === 0) {
            statusEl.innerHTML = '<span class="text-gray-400">暂无 UP主</span>';
        } else {
            statusEl.innerHTML = `<span class="text-gray-400">已加载全部 ${total} 个 UP主</span>`;
        }
    } else {
        statusEl.innerHTML = '<span class="text-primary">下拉加载更多...</span>';
    }
}
```


### 推送历史页面（templates/videos.html）

#### 1. 页面加载时设置默认日期

```javascript
document.addEventListener('DOMContentLoaded', async function() {
    // 设置日期默认值为今天
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('filter-date-from').value = today;
    document.getElementById('filter-date-to').value = today;

    // 加载数据
    await loadUpsOptions();
    await loadVideos();

    bindEvents();
});
```

#### 2. 重置按钮改为恢复默认日期

```javascript
document.getElementById('btn-reset').addEventListener('click', function() {
    document.getElementById('filter-up').value = '';

    // 恢复到今天日期
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('filter-date-from').value = today;
    document.getElementById('filter-date-to').value = today;

    loadVideos(1);
});
```


## Backend Changes

### src/api/ups.py

#### 改造 get_ups() 函数

```python
@router.get("", response_model=PaginatedUpResponse)
async def get_ups(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    is_monitoring: Optional[bool] = None,
    user_id: Optional[int] = None,
    db: Database = Depends(get_db),
):
    """
    获取UP主列表（分页）
    """
    current_user_id = request.session.get("user_id")
    is_admin = request.session.get("is_admin", False)

    # 确定查询用户 ID
    query_user_id = None if is_admin else current_user_id

    # 查询总数
    total = db.get_ups_count(
        user_id=query_user_id,
        keyword=keyword,
        is_monitoring=is_monitoring
    )

    # 查询列表
    ups = db.get_ups(
        user_id=query_user_id,
        keyword=keyword,
        is_monitoring=is_monitoring,
        page=page,
        page_size=page_size
    )

    # 为每个 UP主查询最新视频
    items = []
    for up in ups:
        up_data = UpResponse(**up).model_dump()

        videos_result = db.get_videos(
            page=1,
            page_size=5,
            up_id=up["id"]
        )
        up_data["latest_videos"] = videos_result.get("items", [])
        items.append(up_data)

    return PaginatedUpResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )
```

#### 添加响应模型

在 `src/models.py` 中添加：

```python
class PaginatedUpResponse(BaseModel):
    """分页 UP主响应"""
    items: list[UpResponse]
    total: int
    page: int
    page_size: int
```


### src/database.py

#### 改造 get_ups() 方法

```python
def get_ups(
    self,
    user_id: int = None,
    keyword: str = None,
    is_monitoring: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20
) -> list[dict]:
    """
    查询 UP主列表（支持分页和搜索）
    """
    with self._get_connection() as conn:
        cursor = conn.cursor()

        # 构造 WHERE 条件
        conditions = []
        params = []

        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)

        if is_monitoring is not None:
            conditions.append("is_monitoring = ?")
            params.append(1 if is_monitoring else 0)

        if keyword:
            conditions.append("(name LIKE ? OR mid LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 分页查询
        offset = (page - 1) * page_size
        sql = f"""
            SELECT id, mid, name, face, user_id, is_monitoring, created_at, updated_at
            FROM ups
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """

        cursor.execute(sql, params + [page_size, offset])
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
```

#### 添加 get_ups_count() 方法

```python
def get_ups_count(
    self,
    user_id: int = None,
    keyword: str = None,
    is_monitoring: Optional[bool] = None
) -> int:
    """
    查询 UP主总数
    """
    with self._get_connection() as conn:
        cursor = conn.cursor()

        # 构造 WHERE 条件
        conditions = []
        params = []

        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)

        if is_monitoring is not None:
            conditions.append("is_monitoring = ?")
            params.append(1 if is_monitoring else 0)

        if keyword:
            conditions.append("(name LIKE ? OR mid LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        sql = f"SELECT COUNT(*) FROM ups WHERE {where_clause}"
        cursor.execute(sql, params)

        return cursor.fetchone()[0]
```


## File Changes

### 修改文件列表

| 文件 | 修改内容 |
|------|---------|
| `templates/ups.html` | 添加分页状态、滚动监听、搜索防抖、加载状态 UI |
| `templates/videos.html` | 添加日期默认值设置、重置按钮逻辑调整 |
| `src/api/ups.py` | 添加分页和搜索参数、返回格式改为分页响应 |
| `src/database.py` | `get_ups()` 添加分页和搜索参数、新增 `get_ups_count()` |
| `src/models.py` | 新增 `PaginatedUpResponse` 模型 |


## Implementation Flow

```
1. 后端改造
   ├─ 修改 src/database.py
   │  ├─ get_ups() 添加分页和搜索参数
   │  └─ 新增 get_ups_count()
   ├─ 修改 src/models.py
   │  └─ 新增 PaginatedUpResponse
   └─ 修改 src/api/ups.py
      └─ get_ups() 添加分页和搜索逻辑

2. 前端改造 - 推送历史
   └─ 修改 templates/videos.html
      ├─ 页面加载设置日期默认值
      └─ 重置按钮逻辑调整

3. 前端改造 - UP主列表
   └─ 修改 templates/ups.html
      ├─ 添加分页状态变量
      ├─ 改造 loadUps() 函数
      ├─ 添加滚动监听
      ├─ 改造搜索功能（防抖 + 后端搜索）
      └─ 添加加载状态 UI

4. 测试验证
   ├─ 测试分页加载
   ├─ 测试搜索功能
   ├─ 测试日期默认值
   └─ 测试边界情况
```


## Error Handling

### UP主列表

| 错误场景 | 处理方式 |
|---------|---------|
| 网络请求失败 | 显示错误提示，提供重试按钮 |
| 加载中重复滚动 | 忽略滚动事件（isLoading 标志） |
| 搜索无结果 | 显示"未找到匹配的 UP主" |
| 最后一页已加载 | 显示"已加载全部"提示 |


### 推送历史

| 错误场景 | 处理方式 |
|---------|---------|
| 今日无推送数据 | 正常显示空状态提示 |
| 日期格式错误 | 不应发生（自动设置） |


## Testing Strategy

### 单元测试

- [ ] `Database.get_ups()` 分页参数测试
- [ ] `Database.get_ups()` 搜索参数测试
- [ ] `Database.get_ups_count()` 测试
- [ ] API 响应格式测试


### 集成测试

- [ ] 完整分页加载流程测试
- [ ] 搜索 + 分页组合测试
- [ ] 日期默认值设置测试


### 手动测试

- [ ] 滚动加载流畅性测试
- [ ] 搜索防抖效果测试
- [ ] 边界情况测试（空数据、最后一页等）
- [ ] 响应式布局测试（移动端滚动）
