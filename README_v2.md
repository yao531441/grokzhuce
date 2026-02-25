# Grok 注册机 - Playwright 版本

基于 Playwright 浏览器自动化的 Grok 账号注册工具，支持 Turnstile 验证码自动处理、人工介入、TOS/NSFW 自动设置等功能。

> **注意**: 这是 v2.0 重构版本，使用浏览器自动化替代了原有的 HTTP 请求方式，更加稳定且不易被检测。

## 功能特性

- **浏览器自动化**: 使用 Playwright 控制 Chrome，模拟真实用户行为
- **Turnstile 处理**: 自动尝试完成验证，失败时支持人工介入
- **完整注册流程**: 自动完成邮箱验证、信息填写、注册提交
- **TOS/NSFW 设置**: 自动接受服务条款并启用 NSFW 内容
- **实时保存**: 注册成功立即写入 JSONL 文件，防止数据丢失
- **防风控设计**: 单账号串行执行，失败立即停止，降低封号风险

## 环境要求

- Python 3.8+
- Windows 10/11（推荐，带图形界面）
- Google Chrome 浏览器（可选，支持自动检测）

## 安装步骤

### 1. 克隆仓库

```bash
git clone <your-repo-url>
cd grokzhuce
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. 配置邮箱服务

确保 `.env` 文件存在并包含邮箱服务配置：

```env
# 邮箱服务配置（根据实际使用的服务调整）
WORKER_DOMAIN=your_freemail_domain
FREEMAIL_TOKEN=your_jwt_token
```

## 使用方法

### 基本使用

```bash
python grok_register.py
```

程序会：
1. 自动检测系统 Chrome 浏览器
2. 启动浏览器并打开 Grok 注册页面
3. 等待 Turnstile 验证（自动或人工）
4. 完成注册流程
5. 保存账号信息到 `accounts.jsonl`

### 命令行参数

```bash
python grok_register.py --help
```

参数说明：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--chrome` | Chrome 可执行文件路径 | 自动检测 |
| `--headless` | 无头模式（不显示浏览器界面） | False |
| `--count` | 注册账号数量 | 1 |
| `--output` | 输出文件路径 | accounts.jsonl |

### 使用示例

**注册 1 个账号（默认，显示浏览器）**
```bash
python grok_register.py
```

**注册 3 个账号**
```bash
python grok_register.py --count 3
```

**无头模式（后台运行）**
```bash
python grok_register.py --headless --count 2
```

**指定 Chrome 路径**
```bash
python grok_register.py --chrome "C:\Program Files\Google\Chrome\Application\chrome.exe"
```

**指定输出文件**
```bash
python grok_register.py --output my_accounts.jsonl --count 5
```

## 输出格式

注册成功的账号信息以 JSONL 格式保存，每行一个 JSON 对象：

```json
{"timestamp": "2025-02-25T10:30:00", "email": "abc123@920814.xyz", "password": "x7k9m2p5q8r4t1", "first_name": "John", "last_name": "Smith", "sso": "eyJhbGciOiJIUzI1NiIs...", "status": "success"}
```

字段说明：
- `timestamp`: 注册时间
- `email`: 注册邮箱
- `password`: 登录密码
- `first_name`: 名字
- `last_name`: 姓氏
- `sso`: SSO Cookie（用于登录状态）
- `status`: 状态（success）

## 工作流程

1. **启动浏览器**: 初始化 Chrome，应用 stealth 插件隐藏自动化特征
2. **打开注册页**: 访问 `https://accounts.x.ai/sign-up`
3. **Turnstile 验证**: 
   - 自动检测并尝试点击验证
   - 30 秒超时后提示人工介入
   - 按回车继续
4. **创建邮箱**: 使用 EmailService 创建临时邮箱
5. **发送验证码**: 填写邮箱并点击发送
6. **获取验证码**: 轮询获取邮箱验证码（最多 60 秒）
7. **填写信息**: 输入验证码、密码、姓名
8. **提交注册**: 点击注册按钮
9. **获取 SSO**: 提取登录 Cookie
10. **TOS/NSFW**: 自动接受服务条款并启用 NSFW
11. **保存数据**: 写入 JSONL 文件
12. **清理**: 删除临时邮箱

## 注意事项

### 1. Turnstile 验证

- 程序会首先尝试自动完成验证
- 如果自动验证失败，会暂停并提示人工介入
- **请勿关闭浏览器窗口**，在页面中手动点击验证框
- 完成验证后，在命令行按回车继续

### 2. 防风控建议

- 每次只注册少量账号（建议 1-3 个）
- 注册间隔时间至少 5 秒
- 使用不同的 IP 地址（如果需要注册多个）
- 如果注册失败，请等待一段时间再试

### 3. 错误处理

- 任何步骤失败都会立即停止
- 检查控制台输出的错误信息
- 常见错误：
  - `Turnstile 验证失败`: 需要人工介入或更换 IP
  - `创建邮箱失败`: 检查邮箱服务配置
  - `获取验证码超时`: 检查邮箱服务状态

## 文件说明

```
grokzhuce/
├── grok_register.py          # 主程序（Playwright 版本）⭐
├── grok.py                   # 旧版本（HTTP 请求版，已废弃）
├── api_solver.py             # Turnstile Solver 服务（旧版依赖）
├── requirements.txt          # 依赖列表
├── accounts.jsonl           # 默认输出文件
├── .env                     # 环境变量配置
├── README.md                # 本文档
└── g/                       # 服务模块
    ├── __init__.py
    ├── email_service.py     # 邮箱服务
    ├── turnstile_service.py # Turnstile 服务（旧版依赖）
    ├── user_agreement_service.py  # TOS 服务
    └── nsfw_service.py      # NSFW 服务
```

## 新旧版本对比

| 特性 | 新版本 (grok_register.py) | 旧版本 (grok.py) |
|------|---------------------------|------------------|
| 架构 | Playwright 浏览器自动化 | HTTP 请求 |
| Turnstile | 浏览器内自动处理 | 依赖外部 Solver 服务 |
| 并发 | 单账号串行 | 多线程并发 |
| 稳定性 | 高（模拟真实用户） | 低（易被检测） |
| 速度 | 较慢（但稳定） | 较快（但易失败） |
| 输出格式 | JSONL | 纯文本 |
| 推荐使用 | ✅ 是 | ❌ 否 |

## 故障排除

### 问题：无法启动浏览器

**解决**：
```bash
# 重新安装 Playwright 浏览器
playwright install chromium

# 或指定 Chrome 路径
python grok_register.py --chrome "C:\Path\To\chrome.exe"
```

### 问题：Turnstile 一直验证失败

**解决**：
1. 检查网络连接
2. 尝试更换 IP 地址
3. 使用有界面模式观察验证过程
4. 手动完成验证

### 问题：邮箱验证码获取失败

**解决**：
1. 检查邮箱服务是否正常运行
2. 检查 `.env` 配置是否正确
3. 查看邮箱服务日志

### 问题：缺少依赖

**解决**：
```bash
pip install -r requirements.txt
playwright install chromium
```

## 更新日志

### v2.0 (2025-02-25)
- ✨ 重构为 Playwright 浏览器自动化版本
- ✨ 支持 Turnstile 自动验证和人工介入
- ✨ 添加 TOS/NSFW 自动设置
- ✨ 实时 JSONL 格式保存
- ♻️ 移除并发，改为单账号串行执行
- ♻️ 移除外部 Turnstile Solver 依赖
- 🐛 修复 Cloudflare 拦截问题

### v1.0 (旧版本)
- 基于 HTTP 请求的注册方式
- 支持多线程并发
- 依赖 curl_cffi 模拟浏览器指纹
- 需要外部 Turnstile Solver 服务

## 免责声明

本工具仅供学习和研究使用，请勿用于：
- 批量注册账号进行商业活动
- 违反 Grok/X.AI 服务条款的行为
- 任何违法或不当用途

使用本工具产生的任何后果由使用者自行承担。

## 许可证

MIT License

## 联系方式

如有问题或建议，欢迎提交 Issue。
