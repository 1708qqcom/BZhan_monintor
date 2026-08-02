# Implementation Todo

## Preparation

- [ ] 确认requirements.txt包含依赖
  - requests
  - qrcode
  - pillow
- [ ] 创建测试用的B站账号（可选）
- [ ] 确认config目录存在

## Development Tasks

### Task 1: 实现generate_qrcode方法

**文件**: `src/login.py`

**步骤**:
- [ ] 构造请求头（模拟TV客户端）
- [ ] POST请求到 `/x/passport-tv/c/qrcode/auth_code`
- [ ] 解析JSON响应
- [ ] 提取 `auth_code` 和 `url`
- [ ] 错误处理（请求失败、解析失败）

**验证**: 运行测试代码，打印auth_code

---

### Task 2: 实现show_qrcode_terminal方法

**文件**: `src/login.py`

**步骤**:
- [ ] 导入qrcode库
- [ ] 创建QRCode对象
- [ ] 调用 `add_data` 添加URL
- [ ] 调用 `print_ascii` 输出到终端
- [ ] 添加提示文本

**验证**: 运行测试代码，终端应显示可扫描的二维码

---

### Task 3: 实现poll_scan_result方法

**文件**: `src/login.py`

**步骤**:
- [ ] 构造轮询请求
- [ ] 实现循环逻辑（间隔2秒，超时180秒）
- [ ] 解析状态码:
  - 86101: 未扫描 → 继续等待
  - 86090: 已扫描未确认 → 提示用户
  - 0: 成功 → 提取Cookie
  - 86038: 过期 → 返回失败
- [ ] 提取Cookie字段
- [ ] 返回Cookie字典

**验证**: 完整扫码流程测试

---

### Task 4: 实现save_cookies方法

**文件**: `src/login.py`

**步骤**:
- [ ] 转换Cookie列表为字典格式
- [ ] 添加 `created_at` 和 `updated_at` 时间戳
- [ ] 确保config目录存在
- [ ] 写入JSON文件
- [ ] 错误处理（权限、磁盘空间）

**验证**: 检查生成的JSON文件内容

---

### Task 5: 实现load_cookies方法

**文件**: `src/login.py`

**步骤**:
- [ ] 检查文件是否存在
- [ ] 读取JSON文件
- [ ] 返回Cookie字典
- [ ] 文件不存在返回None

**验证**: 测试加载已保存的Cookie

---

### Task 6: 实现check_cookie_valid方法

**文件**: `src/login.py`

**步骤**:
- [ ] 调用B站用户信息接口（如 `/x/space/myinfo`）
- [ ] 携带Cookie请求
- [ ] 判断响应状态
- [ ] 返回有效性布尔值

**验证**: 测试有效/无效Cookie

---

### Task 7: 实现login整合方法

**文件**: `src/login.py`

**步骤**:
- [ ] 调用 `generate_qrcode`
- [ ] 调用 `show_qrcode_terminal`
- [ ] 调用 `poll_scan_result`
- [ ] 调用 `save_cookies`
- [ ] 返回成功/失败状态
- [ ] 异常处理和用户提示

**验证**: 端到端测试

---

### Task 8: 完善main.py入口

**文件**: `main.py`

**步骤**:
- [ ] 实现 `run_login_flow` 函数
- [ ] 导入 `BilibiliLogin`
- [ ] 调用 `login()` 方法
- [ ] 处理返回结果

**验证**: 运行 `python main.py --login`

---

## Testing Tasks

### 单元测试

- [ ] 测试 `generate_qrcode` 返回正确格式
- [ ] 测试 `save_cookies` 文件写入正确
- [ ] 测试 `load_cookies` 文件读取正确

### 集成测试

- [ ] 完整扫码登录流程测试
- [ ] Cookie文件生成验证
- [ ] 重复登录场景测试

### 边界测试

- [ ] 网络断开时的错误处理
- [ ] 二维码过期场景
- [ ] 用户取消扫码场景

---

## Completion Checklist

- [ ] 所有方法实现完成（无NotImplementedError）
- [ ] 运行 `python main.py --login` 可显示二维码
- [ ] 扫码后Cookie正确保存
- [ ] 错误场景有友好提示
- [ ] 代码符合项目规范（类型注解、文档字符串）