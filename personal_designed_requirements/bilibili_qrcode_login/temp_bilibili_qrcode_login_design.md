# Technical Design

## Overview

使用B站TV端扫码登录接口实现账号授权。流程: 获取auth_code → 显示二维码 → 轮询状态 → 保存Cookie。

## Architecture

**影响模块**:
- `src/login.py`: 登录核心逻辑
- `main.py`: 登录入口调用
- `config/bilibili_cookies.json`: Cookie存储

**依赖**:
- `requests`: HTTP请求
- `qrcode`: 二维码生成
- `pillow`: 图像处理（qrcode依赖）

## Data Model

### Cookie存储格式

**文件**: `config/bilibili_cookies.json`

```json
{
  "cookies": {
    "SESSDATA": "xxx",
    "bili_jct": "xxx",
    "DedeUserID": "xxx",
    "DedeUserID__ckMd5": "xxx",
    "sid": "xxx"
  },
  "created_at": "2026-08-02T14:30:00Z",
  "updated_at": "2026-08-02T14:30:00Z"
}
```

**关键字段**:
- `SESSDATA`: 会话凭证，最重要
- `bili_jct`: CSRF Token
- `DedeUserID`: 用户ID

### API响应格式

**获取二维码响应**:
```json
{
  "code": 0,
  "data": {
    "auth_code": "xxx",
    "url": "https://passport.bilibili.com/h5-app/qrcode/login?auth_code=xxx"
  }
}
```

**轮询响应（成功）**:
```json
{
  "code": 0,
  "data": {
    "code": 0,
    "message": "success",
    "url": "https://...",
    "cookie_info": {
      "cookies": [
        {"name": "SESSDATA", "value": "xxx"},
        ...
      ]
    }
  }
}
```

## API / Interface

### B站API

| 接口 | 方法 | 用途 |
|------|------|------|
| `https://passport.bilibili.com/x/passport-tv/c/qrcode/auth_code` | POST | 获取登录二维码 |
| `https://passport.bilibili.com/x/passport-tv/c/qrcode/auth_code/result` | POST | 查询扫码结果 |

**请求头**:
```
Content-Type: application/x-www-form-urlencoded
User-Agent: Mozilla/5.0 (Linux; Android 10) ...
```

### 内部接口

```python
class BilibiliLogin:
    def generate_qrcode() -> tuple[str, str]
        # 返回 (auth_code, qrcode_url)

    def show_qrcode_terminal(qrcode_url: str) -> None
        # 终端显示二维码

    def poll_scan_result(auth_code: str, timeout: int = 180) -> dict | None
        # 轮询扫码结果，返回Cookie字典

    def save_cookies(cookies: dict) -> None
        # 保存Cookie到文件

    def login() -> bool
        # 完整登录流程
```

## Frontend Changes

无Web前端，仅终端输出。

**终端交互**:
1. 显示二维码ASCII图
2. 显示提示文本
3. 显示轮询状态

## Backend Changes

### src/login.py

实现 `BilibiliLogin` 类的所有方法。

**关键实现点**:

1. **generate_qrcode**
   - POST请求到B站接口
   - 解析响应获取auth_code和url
   - 错误处理

2. **show_qrcode_terminal**
   - 使用 `qrcode.QRCode` 生成二维码矩阵
   - 调用 `.print_ascii(out=sys.stdout)` 输出
   - 显示提示文本

3. **poll_scan_result**
   - 循环请求结果接口
   - 解析状态码:
     - 0: 成功
     - 86038: 二维码已失效
     - 86090: 已扫描未确认
     - 86101: 未扫描
   - 提取Cookie字段

4. **save_cookies**
   - 转换Cookie列表为字典
   - 添加时间戳
   - 写入JSON文件

### main.py

完善 `run_login_flow` 函数:
```python
def run_login_flow(config: dict) -> bool:
    login = BilibiliLogin()
    return login.login()
```

## File Changes

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/login.py` | 修改 | 实现所有TODO方法 |
| `main.py` | 修改 | 实现run_login_flow |
| `config/bilibili_cookies.json` | 自动生成 | 登录成功后创建 |
| `requirements.txt` | 确认 | 确保包含qrcode、pillow |

## Implementation Flow

```
1. 实现generate_qrcode
   ↓ 测试能否获取auth_code
2. 实现show_qrcode_terminal
   ↓ 测试终端显示
3. 实现poll_scan_result
   ↓ 测试完整扫码流程
4. 实现save_cookies
   ↓ 测试Cookie保存
5. 实现login整合方法
   ↓ 端到端测试
6. 完善main.py调用
```

## Error Handling

| 错误 | 检测方式 | 处理 |
|------|----------|------|
| 网络请求失败 | requests.RequestException | 重试3次，间隔1秒 |
| 二维码获取失败 | API code != 0 | 提示错误，退出 |
| 二维码过期 | API code == 86038 | 提示重新运行 |
| 扫码超时 | 180秒未成功 | 提示超时，退出 |
| 用户取消 | API code == 86090 | 提示已取消，退出 |
| 文件写入失败 | IOError | 提示权限错误 |

## Testing Strategy

### 单元测试

- Mock B站API响应
- 测试各方法逻辑

### 集成测试

1. 运行 `python main.py --login`
2. 检查终端显示二维码
3. 用测试账号扫码
4. 验证Cookie文件生成

### 手动测试

- 正常登录流程
- 二维码过期场景
- 网络断开场景
- 重复登录场景