# Technical Design - 视频播放量追踪

## Overview

采用定时任务 + 数据库存储 + 前端可视化的架构：

- **数据采集**：使用 APScheduler 定时任务，每小时调用B站API采集数据
- **数据存储**：新增 `video_stats` 表存储历史统计数据
- **热门提醒**：阈值判断逻辑 + 飞书 Webhook 推送
- **可视化**：使用 ECharts 绘制播放量曲线图

技术选型：
- 定时任务：APScheduler（已在稍后再看功能中使用）
- 图表库：ECharts（功能丰富，社区成熟）
- 数据库：SQLite WAL模式（复用现有架构）

---

## Architecture

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                       定时任务层                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  video_stats_tracker (每小时执行)                     │   │
│  │  - 查询24小时内推送的视频                              │   │
│  │  - 调用B站API获取实时数据                              │   │
│  │  - 写入统计数据到数据库                                │   │
│  │  - 判断热门阈值并推送                                  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                       数据存储层                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  video_stats 表                                       │   │
│  │  - video_id (FK)                                      │   │
│  │  - play_count, like_count, comment_count...          │   │
│  │  - recorded_at                                        │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  config 表                                            │   │
│  │  - stats_tracking_duration (追踪时长)                 │   │
│  │  - hot_video_threshold (热门播放量阈值)               │   │
│  │  - hot_growth_rate_threshold (增长率阈值)             │   │
│  │  - enable_hot_notification (是否启用热门提醒)         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                       API 接口层                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  GET /api/videos/{bvid}/stats                         │   │
│  │  - 返回视频统计数据（用于图表渲染）                    │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  GET /api/videos/hot                                 │   │
│  │  - 返回热门视频列表                                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                       前端展示层                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  video_detail.html                                    │   │
│  │  - ECharts 折线图                                     │   │
│  │  - 指标切换、时间范围选择                              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 影响模块

| 模块 | 变化类型 | 说明 |
|------|---------|------|
| `src/database.py` | 修改 | 新增 `video_stats` 表和 CRUD 方法 |
| `src/scheduler.py` | 修改 | 新增定时任务和采集逻辑 |
| `src/api/videos.py` | 修改 | 新增统计查询 API |
| `src/models.py` | 修改 | 新增响应模型 |
| `src/feishu.py` | 修改 | 新增热门提醒推送方法 |
| `templates/video_detail.html` | 新建 | 视频详情页 |
| `templates/videos.html` | 修改 | 添加"查看详情"入口 |
| `static/js/main.js` | 修改 | 添加图表渲染逻辑 |

---

## Data Model

### 新增表：video_stats

```sql
CREATE TABLE video_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,                    -- 关联 videos.id
    play_count INTEGER DEFAULT 0,                 -- 播放量
    like_count INTEGER DEFAULT 0,                 -- 点赞数
    coin_count INTEGER DEFAULT 0,                 -- 投币数
    favorite_count INTEGER DEFAULT 0,             -- 收藏数
    share_count INTEGER DEFAULT 0,                -- 分享数
    danmaku_count INTEGER DEFAULT 0,              -- 弹幕数
    comment_count INTEGER DEFAULT 0,              -- 评论数
    recorded_at TEXT NOT NULL,                    -- 记录时间 (ISO8601)
    created_at TEXT NOT NULL,                     -- 创建时间
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX idx_video_stats_video_id ON video_stats(video_id);
CREATE INDEX idx_video_stats_recorded_at ON video_stats(recorded_at);
```

### 配置表新增字段

在 `config` 表中添加以下配置项：

| key | value | 说明 |
|-----|-------|------|
| `stats_tracking_duration` | `24` | 追踪时长（小时）|
| `hot_video_threshold` | `10000` | 热门播放量阈值 |
| `hot_growth_rate_threshold` | `50` | 增长率阈值（百分比）|
| `enable_hot_notification` | `1` | 是否启用热门提醒 |

---

## API / Interface

### 1. GET /api/videos/{bvid}/stats

**描述**：获取视频统计数据

**请求参数**：
- `bvid` (path): 视频BV号
- `hours` (query, optional): 查询最近N小时的数据，默认24

**响应模型**：

```python
class VideoStatItem(BaseModel):
    recorded_at: str           # 记录时间
    play_count: int            # 播放量
    like_count: int            # 点赞数
    coin_count: int            # 投币数
    favorite_count: int        # 收藏数
    share_count: int           # 分享数
    danmaku_count: int         # 弹幕数
    comment_count: int         # 评论数

class VideoStatsResponse(BaseModel):
    video_id: int
    bvid: str
    title: str
    stats: list[VideoStatItem]
```

**示例**：

```json
{
  "video_id": 123,
  "bvid": "BV1abc123",
  "title": "视频标题",
  "stats": [
    {
      "recorded_at": "2026-08-06T10:00:00",
      "play_count": 1000,
      "like_count": 50,
      "comment_count": 10,
      ...
    },
    {
      "recorded_at": "2026-08-06T11:00:00",
      "play_count": 1500,
      "like_count": 80,
      "comment_count": 15,
      ...
    }
  ]
}
```

---

### 2. GET /api/videos/hot

**描述**：获取热门视频列表

**请求参数**：
- `threshold` (query, optional): 播放量阈值，默认使用配置值
- `limit` (query, optional): 返回数量，默认10

**响应模型**：

```python
class HotVideoItem(BaseModel):
    video_id: int
    bvid: str
    title: str
    up_name: str
    current_play_count: int
    growth_rate: float          # 与上一小时对比的增长率
    pushed_at: str

class HotVideosResponse(BaseModel):
    items: list[HotVideoItem]
    total: int
```

---

## Frontend Changes

### 新建文件：templates/video_detail.html

**页面结构**：

```html
{% extends "base.html" %}

{% block title %}视频详情 - B站监控{% endblock %}

{% block content %}
<div class="space-y-6">
    <!-- 视频信息卡片 -->
    <div class="bg-white rounded-xl shadow-sm border p-6">
        <h1 class="text-2xl font-bold mb-2" id="video-title">加载中...</h1>
        <div class="flex items-center space-x-4 text-sm text-gray-500">
            <span id="video-up-name">UP主</span>
            <span id="video-pub-time">发布时间</span>
            <a id="video-url" href="#" target="_blank" class="text-primary hover:underline">观看视频</a>
        </div>
    </div>

    <!-- 指标选择器 -->
    <div class="bg-white rounded-xl shadow-sm border p-4">
        <div class="flex space-x-2">
            <button class="stat-btn active" data-metric="play_count">播放量</button>
            <button class="stat-btn" data-metric="like_count">点赞数</button>
            <button class="stat-btn" data-metric="comment_count">评论数</button>
            <button class="stat-btn" data-metric="coin_count">投币数</button>
        </div>
    </div>

    <!-- 时间范围选择器 -->
    <div class="bg-white rounded-xl shadow-sm border p-4">
        <div class="flex space-x-2">
            <button class="time-btn" data-hours="1">最近1小时</button>
            <button class="time-btn" data-hours="6">最近6小时</button>
            <button class="time-btn active" data-hours="24">最近24小时</button>
        </div>
    </div>

    <!-- 图表容器 -->
    <div class="bg-white rounded-xl shadow-sm border p-6">
        <div id="stats-chart" style="width: 100%; height: 400px;"></div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script src="/static/js/video_detail.js"></script>
{% endblock %}
```

---

### 修改文件：templates/videos.html

在表格行中添加"查看详情"按钮：

```html
<td class="px-6 py-4">
    <div class="text-sm font-medium text-gray-900">
        <a href="${video.url || '#'}" target="_blank" class="hover:text-primary">
            ${escapeHtml(video.title)}
        </a>
    </div>
    <div class="text-xs text-gray-500 mt-1">
        <a href="/videos/${video.bvid}" class="hover:text-primary">查看详情</a>
    </div>
</td>
```

---

### 新建文件：static/js/video_detail.js

**核心逻辑**：

```javascript
let currentMetric = 'play_count';
let currentHours = 24;
let bvid = null;
let chart = null;

// 初始化图表
function initChart() {
    chart = echarts.init(document.getElementById('stats-chart'));
    window.addEventListener('resize', () => chart.resize());
}

// 加载统计数据
async function loadStats() {
    const response = await fetchAPI(`/api/videos/${bvid}/stats?hours=${currentHours}`);
    const stats = response.stats;

    // 渲染图表
    renderChart(stats);
}

// 渲染图表
function renderChart(stats) {
    const times = stats.map(s => s.recorded_at);
    const values = stats.map(s => s[currentMetric]);

    const option = {
        title: { text: getMetricLabel(currentMetric) },
        tooltip: { trigger: 'axis' },
        xAxis: {
            type: 'category',
            data: times,
            axisLabel: { formatter: formatTime }
        },
        yAxis: { type: 'value' },
        series: [{
            type: 'line',
            data: values,
            smooth: true,
            areaStyle: { opacity: 0.3 }
        }]
    };

    chart.setOption(option);
}

// 切换指标
document.querySelectorAll('.stat-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        currentMetric = e.target.dataset.metric;
        updateButtonState('.stat-btn', e.target);
        loadStats();
    });
});

// 切换时间范围
document.querySelectorAll('.time-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        currentHours = parseInt(e.target.dataset.hours);
        updateButtonState('.time-btn', e.target);
        loadStats();
    });
});
```

---

## Backend Changes

### 修改文件：src/database.py

**新增方法**：

```python
# ==================== 视频统计数据 CRUD ====================

def create_video_stats_table(self) -> None:
    """创建 video_stats 表"""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                play_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                coin_count INTEGER DEFAULT 0,
                favorite_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0,
                danmaku_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                recorded_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
            )
        """)
        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_video_stats_video_id
            ON video_stats(video_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_video_stats_recorded_at
            ON video_stats(recorded_at)
        """)
        conn.commit()

def add_video_stats(self, video_id: int, stats: dict) -> int:
    """
    添加视频统计记录

    Args:
        video_id: 视频ID
        stats: 统计数据字典 {
            play_count, like_count, coin_count,
            favorite_count, share_count, danmaku_count, comment_count
        }

    Returns:
        新记录的 id
    """
    now = datetime.now().isoformat()

    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO video_stats
            (video_id, play_count, like_count, coin_count,
             favorite_count, share_count, danmaku_count, comment_count,
             recorded_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            video_id,
            stats.get('play_count', 0),
            stats.get('like_count', 0),
            stats.get('coin_count', 0),
            stats.get('favorite_count', 0),
            stats.get('share_count', 0),
            stats.get('danmaku_count', 0),
            stats.get('comment_count', 0),
            now,
            now
        ))
        conn.commit()
        return cursor.lastrowid

def get_video_stats(self, bvid: str, hours: int = 24) -> list[dict]:
    """
    获取视频统计数据

    Args:
        bvid: 视频BV号
        hours: 查询最近N小时的数据

    Returns:
        统计记录列表，按时间升序排列
    """
    cutoff_time = datetime.now() - timedelta(hours=hours)

    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                vs.recorded_at, vs.play_count, vs.like_count,
                vs.coin_count, vs.favorite_count, vs.share_count,
                vs.danmaku_count, vs.comment_count
            FROM video_stats vs
            INNER JOIN videos v ON vs.video_id = v.id
            WHERE v.bvid = ? AND vs.recorded_at >= ?
            ORDER BY vs.recorded_at ASC
        """, (bvid, cutoff_time.isoformat()))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_videos_pushed_after(self, cutoff_time: datetime) -> list[dict]:
    """
    获取推送后指定时间内的视频列表

    Args:
        cutoff_time: 截止时间

    Returns:
        视频列表
    """
    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, bvid, title, pushed_at
            FROM videos
            WHERE pushed = 1 AND pushed_at >= ?
            ORDER BY pushed_at DESC
        """, (cutoff_time.isoformat(),))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_latest_video_stats(self, video_id: int) -> Optional[dict]:
    """
    获取视频的最新统计记录

    Args:
        video_id: 视频ID

    Returns:
        最新统计记录，不存在返回 None
    """
    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT play_count, like_count, coin_count, recorded_at
            FROM video_stats
            WHERE video_id = ?
            ORDER BY recorded_at DESC
            LIMIT 1
        """, (video_id,))

        row = cursor.fetchone()
        return dict(row) if row else None

def cleanup_old_video_stats(self, days: int = 7) -> int:
    """
    清理过期的视频统计数据

    Args:
        days: 保留天数

    Returns:
        删除的记录数
    """
    cutoff_date = datetime.now() - timedelta(days=days)

    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM video_stats
            WHERE recorded_at < ?
        """, (cutoff_date.isoformat(),))
        conn.commit()

        deleted = cursor.rowcount
        logger.info(f"清理了 {deleted} 条过期统计数据")
        return deleted
```

---

### 修改文件：src/scheduler.py

**新增方法**：

```python
def setup_video_stats_tracker(self) -> None:
    """
    设置视频播放量追踪任务（每小时执行）

    在 start() 之前调用，初始化统计数据采集定时任务
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        logger.info("设置视频播放量追踪任务...")

        # 创建后台调度器
        if not hasattr(self, 'stats_scheduler'):
            self.stats_scheduler = BackgroundScheduler()

        # 添加定时任务（每小时执行）
        self.stats_scheduler.add_job(
            func=self._track_video_stats,
            trigger=IntervalTrigger(hours=1),
            id='video_stats_tracker',
            name='视频播放量追踪',
            replace_existing=True
        )

        # 启动调度器
        self.stats_scheduler.start()
        logger.info("视频播放量追踪任务已启动（每小时执行）")

    except Exception as e:
        logger.error(f"设置视频播放量追踪失败: {e}", exc_info=True)

def _track_video_stats(self) -> None:
    """
    追踪推送后24小时内的视频播放量

    流程：
    1. 查询推送后24小时内的视频
    2. 遍历获取实时统计数据
    3. 写入数据库
    4. 判断热门阈值并推送
    """
    logger.info("========== 开始视频统计数据采集 ==========")

    if not self.use_database:
        logger.warning("未启用数据库，跳过统计采集")
        return

    try:
        # 1. 获取追踪时长配置
        tracking_hours = int(self.db.get_config_value(
            "stats_tracking_duration", default="24"
        ))

        # 2. 查询推送后指定时间内的视频
        cutoff_time = datetime.now() - timedelta(hours=tracking_hours)
        videos = self.db.get_videos_pushed_after(cutoff_time)

        if not videos:
            logger.info("无需要追踪的视频")
            return

        logger.info(f"需要追踪 {len(videos)} 个视频")

        # 3. 遍历采集数据
        success_count = 0
        fail_count = 0

        for i, video in enumerate(videos, 1):
            video_id = video['id']
            bvid = video['bvid']
            title = video['title'][:30]

            try:
                logger.debug(f"[{i}/{len(videos)}] 采集: {bvid} - {title}")

                # 调用B站API获取统计数据
                stats = self._fetch_video_stats(bvid)

                if not stats:
                    logger.warning(f"视频可能已删除: {bvid}")
                    continue

                # 写入数据库
                self.db.add_video_stats(video_id, stats)
                success_count += 1

                # 判断热门阈值并推送
                if self._check_hot_threshold(video_id, stats):
                    self._push_hot_notification(video, stats)

                logger.debug(f"采集成功: {bvid}")

            except Exception as e:
                logger.error(f"采集失败: {bvid}, error={e}")
                fail_count += 1
                continue

        logger.info(f"采集完成: 成功 {success_count}, 失败 {fail_count}")

    except Exception as e:
        logger.error(f"视频统计数据采集异常: {e}", exc_info=True)

def _fetch_video_stats(self, bvid: str) -> Optional[dict]:
    """
    获取视频统计数据（从B站API）

    Args:
        bvid: 视频BV号

    Returns:
        统计数据字典，失败返回 None
    """
    try:
        # 使用B站客户端获取视频信息
        video_info = self.bilibili.get_video_info(bvid=bvid)

        if not video_info:
            return None

        stat = video_info.get('stat', {})

        return {
            'play_count': stat.get('view', 0) or 0,
            'like_count': stat.get('like', 0) or 0,
            'coin_count': stat.get('coin', 0) or 0,
            'favorite_count': stat.get('favorite', 0) or 0,
            'share_count': stat.get('share', 0) or 0,
            'danmaku_count': stat.get('danmaku', 0) or 0,
            'comment_count': stat.get('reply', 0) or 0,
        }

    except Exception as e:
        logger.error(f"获取视频统计数据失败: bvid={bvid}, error={e}")
        return None

def _check_hot_threshold(self, video_id: int, current_stats: dict) -> bool:
    """
    判断是否达到热门阈值

    Args:
        video_id: 视频ID
        current_stats: 当前统计数据

    Returns:
        达到阈值返回 True
    """
    try:
        # 获取配置
        threshold = int(self.db.get_config_value(
            "hot_video_threshold", default="10000"
        ))
        growth_threshold = float(self.db.get_config_value(
            "hot_growth_rate_threshold", default="50"
        ))
        enable_notification = self.db.get_config_value(
            "enable_hot_notification", default="1"
        ) == "1"

        if not enable_notification:
            return False

        # 条件1：播放量绝对值阈值
        play_count = current_stats.get('play_count', 0)
        if play_count >= threshold:
            logger.info(f"达到播放量阈值: video_id={video_id}, play_count={play_count}")
            return True

        # 条件2：增长率阈值
        latest_stats = self.db.get_latest_video_stats(video_id)
        if latest_stats:
            old_play = latest_stats.get('play_count', 0)
            if old_play > 0:
                growth_rate = (play_count - old_play) / old_play * 100
                if growth_rate >= growth_threshold:
                    logger.info(f"达到增长率阈值: video_id={video_id}, growth_rate={growth_rate:.1f}%")
                    return True

        return False

    except Exception as e:
        logger.error(f"判断热门阈值失败: {e}")
        return False

def _push_hot_notification(self, video: dict, stats: dict) -> None:
    """
    推送热门视频提醒

    Args:
        video: 视频信息
        stats: 统计数据
    """
    try:
        # 检查是否已推送过（避免重复）
        # 可以在 push_history 表中记录

        # 获取飞书 Webhook
        webhook_url = self.db.get_config_value("feishu_webhook_url")
        if not webhook_url:
            logger.warning("未配置飞书 Webhook，跳过热门提醒")
            return

        # 计算增长率
        latest_stats = self.db.get_latest_video_stats(video['id'])
        growth_rate = 0.0
        if latest_stats:
            old_play = latest_stats.get('play_count', 0)
            if old_play > 0:
                growth_rate = (stats['play_count'] - old_play) / old_play * 100

        # 发送飞书通知
        from src.feishu import FeishuNotifier
        notifier = FeishuNotifier(webhook_url)

        video_url = f"https://www.bilibili.com/video/{video['bvid']}"

        success = notifier.send_hot_video_notification(
            video_title=video['title'],
            video_url=video_url,
            play_count=stats['play_count'],
            growth_rate=growth_rate
        )

        if success:
            logger.info(f"热门提醒推送成功: {video['bvid']}")
        else:
            logger.warning(f"热门提醒推送失败: {video['bvid']}")

    except Exception as e:
        logger.error(f"推送热门提醒异常: {e}", exc_info=True)
```

在 `start()` 方法中调用：

```python
def start(self, skip_signals: bool = False) -> None:
    """启动定时监控"""
    logger.info("=" * 50)
    logger.info("监控调度器启动")
    logger.info("=" * 50)

    # 加载历史记录
    self.load_history()

    # 设置稍后再看定时推送
    self.setup_toview_push_scheduler()

    # 【新增】设置视频播放量追踪
    self.setup_video_stats_tracker()

    # ... 其他逻辑
```

---

### 修改文件：src/api/videos.py

**新增端点**：

```python
@router.get(
    "/{bvid}/stats",
    response_model=VideoStatsResponse,
    summary="获取视频统计数据",
    description="获取视频的播放量、点赞数等统计数据，用于绘制曲线图"
)
async def get_video_stats(
    bvid: str,
    hours: int = Query(24, ge=1, le=72, description="查询最近N小时的数据"),
    db: Database = Depends(get_db)
):
    """
    获取视频统计数据

    Args:
        bvid: 视频BV号
        hours: 查询最近N小时的数据（默认24小时）

    Returns:
        视频统计数据
    """
    logger.info(f"API调用: GET /api/videos/{bvid}/stats, hours={hours}")

    try:
        # 查询视频基本信息
        video = db.get_video_by_bvid(bvid)
        if not video:
            raise HTTPException(status_code=404, detail=f"视频不存在: {bvid}")

        # 查询统计数据
        stats = db.get_video_stats(bvid, hours=hours)

        return VideoStatsResponse(
            video_id=video['id'],
            bvid=bvid,
            title=video['title'],
            stats=stats
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取视频统计数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取统计数据失败")


@router.get(
    "/hot",
    response_model=HotVideosResponse,
    summary="获取热门视频列表",
    description="获取播放量达到阈值的视频列表"
)
async def get_hot_videos(
    threshold: Optional[int] = Query(None, ge=0, description="播放量阈值"),
    limit: int = Query(10, ge=1, le=50, description="返回数量"),
    db: Database = Depends(get_db)
):
    """
    获取热门视频列表

    Args:
        threshold: 播放量阈值（默认使用配置值）
        limit: 返回数量

    Returns:
        热门视频列表
    """
    logger.info(f"API调用: GET /api/videos/hot, threshold={threshold}, limit={limit}")

    try:
        # 获取阈值
        if threshold is None:
            threshold = int(db.get_config_value("hot_video_threshold", default="10000"))

        # 查询热门视频（需要实现）
        hot_videos = db.get_hot_videos(threshold=threshold, limit=limit)

        return HotVideosResponse(
            items=hot_videos,
            total=len(hot_videos)
        )

    except Exception as e:
        logger.error(f"获取热门视频失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取热门视频失败")
```

---

### 修改文件：src/models.py

**新增模型**：

```python
# ==================== 视频统计相关模型 ====================

class VideoStatItem(BaseModel):
    """视频统计项模型"""
    recorded_at: str
    play_count: int = 0
    like_count: int = 0
    coin_count: int = 0
    favorite_count: int = 0
    share_count: int = 0
    danmaku_count: int = 0
    comment_count: int = 0


class VideoStatsResponse(BaseModel):
    """视频统计响应模型"""
    video_id: int
    bvid: str
    title: str
    stats: list[VideoStatItem]


class HotVideoItem(BaseModel):
    """热门视频项模型"""
    video_id: int
    bvid: str
    title: str
    up_name: Optional[str] = None
    current_play_count: int = 0
    growth_rate: float = 0.0
    pushed_at: str


class HotVideosResponse(BaseModel):
    """热门视频响应模型"""
    items: list[HotVideoItem]
    total: int
```

---

### 修改文件：src/feishu.py

**新增方法**：

```python
def send_hot_video_notification(
    self,
    video_title: str,
    video_url: str,
    play_count: int,
    growth_rate: float
) -> bool:
    """
    发送热门视频提醒

    Args:
        video_title: 视频标题
        video_url: 视频链接
        play_count: 当前播放量
        growth_rate: 增长率（百分比）

    Returns:
        发送成功返回 True
    """
    self.logger.info(f"准备发送热门视频提醒: {video_title}")

    # 构造飞书交互式卡片
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "🔥 热门视频提醒"
                },
                "template": "orange"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**视频标题**\n{video_title}"
                    }
                },
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**当前播放量**\n{self._format_view_count(play_count)}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**增长率**\n{growth_rate:.1f}%"
                            }
                        }
                    ]
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "观看视频"
                            },
                            "type": "primary",
                            "url": video_url
                        }
                    ]
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"提醒时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    ]
                }
            ]
        }
    }

    result = self._send_webhook(payload)
    if result:
        self.logger.info(f"热门视频提醒发送成功: {video_title}")
    else:
        self.logger.warning(f"热门视频提醒发送失败: {video_title}")
    return result
```

---

## File Changes

### 新建文件

| 文件路径 | 说明 |
|---------|------|
| `templates/video_detail.html` | 视频详情页模板 |
| `static/js/video_detail.js` | 视频详情页前端逻辑 |
| `scripts/migrate_add_video_stats_table.py` | 数据库迁移脚本 |

### 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `src/database.py` | 新增 `video_stats` 表和 CRUD 方法 |
| `src/scheduler.py` | 新增定时任务和采集逻辑 |
| `src/api/videos.py` | 新增统计查询 API |
| `src/models.py` | 新增响应模型 |
| `src/feishu.py` | 新增热门提醒推送方法 |
| `templates/videos.html` | 添加"查看详情"入口 |

---

## Implementation Flow

### 阶段1：数据采集（后端）

**优先级**：P0

**任务列表**：
1. 数据库迁移：创建 `video_stats` 表
2. 实现 `src/database.py` 中的 CRUD 方法
3. 实现 `src/scheduler.py` 中的定时任务
4. 实现 B站API调用和数据写入逻辑
5. 测试定时任务执行

**验收标准**：
- 定时任务每小时执行一次
- 数据正确写入 `video_stats` 表
- 日志输出正常

---

### 阶段2：热门提醒（推送）

**优先级**：P1

**任务列表**：
1. 实现阈值判断逻辑
2. 实现 `src/feishu.py` 中的热门提醒方法
3. 实现去重逻辑（避免重复推送）
4. 测试飞书推送

**验收标准**：
- 播放量达到阈值时触发提醒
- 飞书消息格式正确
- 同一视频每小时最多推送1次

---

### 阶段3：数据可视化（前端）

**优先级**：P2

**任务列表**：
1. 创建 `templates/video_detail.html`
2. 实现 ECharts 图表渲染
3. 实现指标切换、时间范围选择
4. 在 `templates/videos.html` 添加"查看详情"入口
5. 实现响应式设计

**验收标准**：
- 图表正确渲染播放量曲线
- 支持切换指标和时间范围
- 移动端显示正常

---

### 阶段4：配置管理

**优先级**：P3

**任务列表**：
1. 在 `config` 表添加配置项
2. 在配置页面显示追踪参数设置
3. 实现配置保存逻辑

**验收标准**：
- 配置页面显示新参数
- 配置保存后立即生效

---

## Error Handling

### 错误场景处理

| 错误场景 | 处理方式 |
|---------|---------|
| B站API限流 | 记录日志，跳过本次采集，等待下一次定时任务 |
| 视频已删除 | 标记视频状态，停止后续采集 |
| 数据库写入失败 | 记录错误日志，不影响其他视频采集 |
| 飞书推送失败 | 记录日志，不重试（避免频繁推送） |
| 未配置Webhook | 跳过推送，记录警告日志 |

### 日志规范

- **INFO**：定时任务启动/完成、采集成功、推送成功
- **WARNING**：API限流、未配置Webhook、视频可能删除
- **ERROR**：数据库写入失败、API调用异常、推送异常

---

## Testing Strategy

### 单元测试

**测试范围**：
- `Database.add_video_stats()` 正常写入
- `Database.get_video_stats()` 查询逻辑
- `MonitorScheduler._check_hot_threshold()` 阈值判断

**测试文件**：`tests/test_video_stats.py`

---

### 集成测试

**测试场景**：
1. 推送视频后，T0时刻记录初始播放量
2. 定时任务触发，采集数据并写入数据库
3. 播放量达到阈值，触发飞书推送
4. 查询API返回正确的统计数据

**测试方法**：使用 Mock 对象模拟B站API和飞书推送

---

### 手动测试

**测试步骤**：
1. 启动服务：`python main.py --web`
2. 触发视频推送（手动推送或等待新视频）
3. 查看数据库 `video_stats` 表是否有记录
4. 等待热门提醒推送（可临时降低阈值测试）
5. 访问视频详情页查看图表

---

## Performance Considerations

### 数据库优化

- 使用索引加速查询：`idx_video_stats_video_id`, `idx_video_stats_recorded_at`
- 定期清理过期数据（7天）
- 使用 WAL 模式支持并发读写

### API 调用优化

- 添加随机延迟（避免并发调用）
- 控制并发数量（最多同时采集10个视频）
- 失败重试机制（最多重试2次）

### 前端优化

- ECharts 图表懒加载
- 数据缓存（切换指标时不重新请求）
- 图表响应式设计

---

## Security Considerations

- 飞书 Webhook URL 存储在数据库中，不暴露给前端
- API 端点需要登录验证（复用现有 Session 验证）
- 数据库操作使用参数化查询，防止SQL注入
- B站API调用使用 HTTPS 协议