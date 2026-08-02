# Feature Requirements

## Background

B站UP主视频监控服务需要访问用户的关注列表和视频数据，这需要用户身份认证。B站提供TV端扫码登录接口，用户可用B站App扫描二维码完成授权，无需手动输入账号密码。

## Goal

实现终端扫码登录功能，用户运行命令后在终端看到二维码，用B站App扫描后自动完成登录并保存Cookie。

## User Story

**As a** B站UP主视频监控服务的使用者

**I want** 通过终端扫码登录我的B站账号

**So that** 服务可以自动获取我的关注列表和视频更新信息

## Functional Requirements

### FR-001 获取登录二维码

调用B站TV端登录接口获取 `auth_code` 和二维码内容。

**输入**: 无

**输出**:
- `auth_code`: 授权码，用于后续轮询
- `qrcode_url`: 二维码内容URL

### FR-002 终端显示二维码

在终端以ASCII字符形式显示二维码，方便用户扫描。

**要求**:
- 二维码清晰可识别
- 提示用户用B站App扫描
- 显示二维码有效期（180秒）

### FR-003 轮询扫码状态

定时查询扫码结果，直到成功、失败或超时。

**状态**:
- `未扫描`: 继续等待
- `已扫描未确认`: 提示用户在手机上确认
- `已确认`: 登录成功，获取Cookie
- `已取消`: 登录失败
- `二维码过期`: 提示重新运行

**轮询策略**:
- 间隔: 2秒
- 超时: 180秒

### FR-004 保存Cookie

登录成功后，将Cookie保存到 `config/bilibili_cookies.json`。

**格式**:
```json
{
  "cookies": {
    "SESSDATA": "...",
    "bili_jct": "...",
    "DedeUserID": "...",
    ...
  },
  "created_at": "2026-08-02T14:30:00",
  "updated_at": "2026-08-02T14:30:00"
}
```

### FR-005 错误提示

对以下情况进行友好提示:
- 网络请求失败
- 二维码获取失败
- 扫码超时
- 登录取消

## User Flow

```
用户运行 python main.py --login
        ↓
调用B站API获取auth_code
        ↓
终端显示二维码
        ↓
用户用B站App扫描 ←───┐
        ↓              │
轮询扫码状态 ────────┘
        ↓
扫码成功，获取Cookie
        ↓
保存到config/bilibili_cookies.json
        ↓
提示"登录成功"
```

## Edge Cases

| 场景 | 处理方式 |
|------|----------|
| 二维码过期 | 提示用户重新运行命令 |
| 用户取消扫码 | 提示"登录已取消"，退出程序 |
| 网络请求失败 | 重试3次，仍失败则提示错误 |
| Cookie文件写入失败 | 提示权限错误，建议检查目录权限 |
| 已有有效Cookie | 提示是否重新登录 |

## Acceptance Criteria

- [ ] 运行 `python main.py --login` 可启动扫码登录
- [ ] 终端正确显示二维码
- [ ] 扫码成功后Cookie保存到 `config/bilibili_cookies.json`
- [ ] Cookie文件包含 `SESSDATA`、`bili_jct`、`DedeUserID` 等必要字段
- [ ] 超时、取消等异常情况有明确提示
- [ ] 网络错误有重试机制