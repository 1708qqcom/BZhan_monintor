# Feature Requirements - B站API集成

## Background

B站UP主视频监控服务需要调用B站API获取用户关注列表和UP主视频列表。当前项目已完成扫码登录功能，Cookie已保存到本地，但尚未实现API调用逻辑。

B站部分API需要WBI签名机制（反爬虫措施），这是技术实现的难点。通过分析yutto开源项目，已明确WBI签名的完整实现方案。


## Goal

实现B站API调用的三个核心功能：
1. **获取关注列表** - 同步用户关注的UP主列表
2. **获取UP主视频列表** - 查询指定UP主发布的视频
3. **Cookie有效性检查** - 验证登录状态是否有效

这些功能是整个监控服务的数据基础，支撑后续的定时检查和飞书推送功能。


## User Story

**As a** B站重度用户

**I want** 自动获取我关注的UP主列表和他们的最新视频

**So that** 我可以第一时间收到新视频通知，不再错过喜欢的UP主更新


## Functional Requirements

### FR-001: Cookie有效性检查

**优先级**: P0

**描述**:
- 系统应能验证已保存的Cookie是否有效
- 验证接口：`https://api.bilibili.com/x/space/acc/info`
- 有效返回用户信息，无效返回错误提示

**验收标准**:
- [ ] 调用接口返回code=0表示有效
- [ ] Cookie无效时抛出明确异常
- [ ] 已在 `src/login.py` 中实现


### FR-002: 获取关注列表

**优先级**: P0

**描述**:
- 获取当前登录用户关注的UP主列表
- API接口：`https://api.bilibili.com/x/relation/followings`
- 支持分页，每页最多50条
- 最多获取前50个关注（配置项 `max_follows_to_check`）

**请求参数**:
```
vmid: {用户ID}  # 从Cookie中的DedeUserID获取
pn: {页码}      # 从1开始
ps: {每页数量}  # 建议50
```

**返回数据**:
```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "mid": 123456,        // UP主ID
        "uname": "UP主名称",
        "face": "https://...", // 头像URL
        "sign": "个性签名"
      }
    ],
    "total": 120
  }
}
```

**验收标准**:
- [ ] 成功返回UP主列表（包含mid、uname、face）
- [ ] 支持分页，自动获取多页数据
- [ ] 达到配置的最大数量时停止获取
- [ ] 网络错误时自动重试（最多3次）


### FR-003: 获取UP主视频列表

**优先级**: P0

**描述**:
- 获取指定UP主发布的视频列表
- API接口：`https://api.bilibili.com/x/space/wbi/arc/search`
- **需要WBI签名**
- 支持分页，每页30条
- 按发布时间倒序排列

**请求参数**:
```
mid: {UP主ID}
pn: {页码}
ps: {每页数量}  # 固定30
order: "pubdate"  # 按发布时间排序
```

**WBI签名参数**（自动添加）:
```
wts: {时间戳}
w_rid: {MD5签名}
dm_img_list: "[]"
dm_img_str: {随机base64}
dm_cover_img_str: {随机base64}
```

**返回数据**:
```json
{
  "code": 0,
  "data": {
    "list": {
      "vlist": [
        {
          "aid": 114514,           // AV号
          "bvid": "BV1xx...",      // BV号
          "title": "视频标题",
          "description": "简介",
          "pic": "https://...",    // 封面URL
          "pubdate": 1722585600,   // 发布时间戳
          "play": 12000,           // 播放量
          "video_review": 500      // 弹幕数
        }
      ]
    },
    "page": {
      "count": 100  // 总数
    }
  }
}
```

**验收标准**:
- [ ] 正确实现WBI签名算法
- [ ] 成功返回视频列表（包含aid、bvid、title、pubdate、play）
- [ ] 签名错误时能重试（重新获取WBI密钥）
- [ ] 支持分页获取多页数据


### FR-004: WBI签名机制

**优先级**: P0（技术基础）

**描述**:
B站部分API需要WBI签名，算法流程：

1. **获取WBI密钥**
   - 调用 `https://api.bilibili.com/x/web-interface/nav`
   - 提取 `img_key` 和 `sub_key`

2. **生成混淆密钥**
   - 拼接 `img_key + sub_key`
   - 按固定索引表提取32位字符

3. **参数签名**
   - 添加时间戳 `wts`
   - 添加反爬参数 `dm_img_str`、`dm_cover_img_str`
   - 按字母顺序排序参数
   - 移除非法字符 `! ' ( ) *`
   - 拼接参数字符串 + 混淆密钥
   - 计算MD5得到 `w_rid`

**验收标准**:
- [ ] WBI密钥可缓存（有效期约10分钟）
- [ ] 签名验证通过（API返回code=0）
- [ ] 签名失败时自动重试


## User Flow

```
用户扫码登录
    ↓
Cookie保存到本地
    ↓
系统加载Cookie
    ↓
验证Cookie有效性 ─── 无效 ──→ 提示重新登录
    ↓ 有效
获取关注列表（分页）
    ↓
筛选监控UP主（最多50个）
    ↓
定时任务启动
    ↓
遍历UP主获取视频列表（WBI签名）
    ↓
对比历史记录
    ↓
发现新视频 ──→ 推送通知
```


## Edge Cases

### EC-001: Cookie过期
**场景**: 用户Cookie超过30天有效期
**处理**:
- 验证接口返回错误码
- 飞书推送告警通知
- 提示用户重新登录

### EC-002: API限流
**场景**: 请求频率过高触发412错误
**处理**:
- 添加请求间隔（1-2秒）
- 自动重试（最多3次）
- 记录日志便于排查

### EC-003: WBI签名失效
**场景**: B站更新签名算法
**处理**:
- 签名验证失败时重新获取密钥
- 重试一次，仍失败则记录错误日志
- 飞书推送告警

### EC-004: 网络异常
**场景**: 网络超时或连接失败
**处理**:
- 自动重试（最多3次，间隔递增）
- 记录错误日志
- 不中断整个监控流程

### EC-005: 用户关注列表为空
**场景**: 用户没有关注任何UP主
**处理**:
- 返回空列表
- 记录日志提示用户


## Acceptance Criteria

### 功能验收
- [ ] Cookie有效性检查正常工作
- [ ] 成功获取关注列表（包含mid、uname、face）
- [ ] 成功获取UP主视频列表（包含aid、title、pubdate）
- [ ] WBI签名算法正确实现
- [ ] 分页逻辑正确
- [ ] 错误处理完善（重试、日志、告警）

### 性能验收
- [ ] WBI密钥缓存生效（避免重复获取）
- [ ] 请求间隔可控（避免限流）
- [ ] 50个UP主的视频列表获取时间 < 5分钟

### 代码质量
- [ ] 代码符合项目规范（中文注释、英文代码）
- [ ] 异常处理完善
- [ ] 日志记录清晰
- [ ] 无硬编码（配置项可调整）


## Dependencies

### 已完成
- ✅ 扫码登录功能（`src/login.py`）
- ✅ Cookie保存机制（`config/bilibili_cookies.json`）
- ✅ 配置文件模板（`config/settings.yaml`）

### 待完成
- 🔴 WBI签名实现
- 🔴 API调用封装
- 🔴 错误处理与重试机制
- 🔴 日志记录集成


## Reference

- yutto项目源码：https://github.com/yutto-dev/yutto
- WBI签名实现：`src/yutto/api/user_info.py`
- HTTP封装参考：`src/yutto/utils/fetcher.py`
- 用户空间API：`src/yutto/api/space.py`
