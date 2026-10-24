# Private Key Input

给 Agent 工作流用的临时 HTML 密钥输入页：值交给本机处理函数，Agent 只接收处理状态。

[English](README.md) · [Agent 使用说明](SKILL.md) · [实现源码](scripts/private_input.py)

## 解决什么问题

任务需要凭据时，把密钥贴进聊天会让它进入会话历史，甚至模型上下文。这个 Skill 用一个短时页面和任务专用 Python 回调替代聊天输入，不需要守护进程、数据库、插件或凭据管理平台。

```text
用户 -> 临时页面 -> 本机回调 -> 已授权的目标服务
                      |
                 仅处理状态 -> Agent 继续任务
```

它不是操作系统沙箱或密码保险库。本机处理函数与目标服务必然接触明文；只有任务包装程序也正确处理数据，才能让密钥不进入 Agent 可见输出。

## 安装 Skill

需要 Python 3.9+，以及支持 `SKILL.md` 的客户端。不依赖第三方 Python 包。Python 执行已在 macOS、Windows 上实测；各客户端的技能发现能力应单独核验。

将仓库克隆到客户端实际支持的技能目录，或从共享副本建立链接。例如 Hermes 默认 profile：

```bash
git clone https://github.com/Loveacup/private-key-input.git ~/.hermes/skills/private-key-input
python3 -B -m unittest discover -s ~/.hermes/skills/private-key-input/scripts -p 'test_*.py'
```

目标目录必须尚不存在。其他客户端请使用其真实支持的技能位置，不要照搬 Hermes 路径。安装文件不会开启监听、保存凭据或修改客户端配置。

给 Agent 的示例请求：

> 当前任务需要凭据时使用 private-key-input。先明确凭据要交给哪里，再提供临时页面；不把输入放进聊天或工具输出，提交后复用宿主现有机制自动继续任务。不要新增回调服务，也不要未经授权另建存储。

## 第一次运行：只用测试文字

在仓库根目录运行：

```bash
python3 -B -m unittest discover -s scripts -p 'test_*.py'
python3 -B examples/discard_demo.py
```

Windows 没有 `python3` 时使用 `py -B`。Demo 打印本机回环 URL，最多等待十分钟。在同一台机器的浏览器打开页面，**只输入测试文字**。回调丢弃输入，最终输出 `Outcome: submitted`。该 Demo 不需要、也不应使用真实密钥。

页面目前为简体中文，包含标准密码管理器提示字段，但不代表已验证 1Password 联动。

## 接入真实授权任务

从 `scripts/private_input.py` 导入 `InputServer` 或 `serve`。任务包装程序提供回调，直接把密钥用于已授权目标，返回 `None`。不得返回或打印输入、请求正文、请求头、响应正文和原始异常；发送凭据时应设置超时并拒绝重定向。

`serve(callback, purpose, **options)` 打印 URL、等待并输出结果。`InputServer(callback, purpose, **options)` 提供 `url` 与 `run()`，适合需要单独递交链接的宿主。

### 链接递交与自动继续

- 必须在等待调用阻塞前，让用户拿到 URL。终端通常能显示及时 flush 的输出，但 Agent 工具可能一直缓存输出到命令退出；先核验实际宿主行为。
- 工具缓存输出时，先启动任务自有临时进程、取得并发送 URL，再用宿主已有机制等待。不要只为续接新增常驻服务。
- Hermes 可复用已有后台进程完成通知。OMP 已用延迟模拟客户端验证短时同步等待，但这**不证明**真人能及时拿到链接，也不证明长等待成立。
- 仅把非密钥状态返回原会话。宿主支持时不再要求用户补一句“好了”；原会话关闭后，不得擅自把结果改投其他会话。

### 参数与结果

- 默认 `host="127.0.0.1"`、`port=0`（系统分配空闲端口）、`ttl=600` 秒。
- TLS：传入已配置的 `ssl.SSLContext` 作为 `tls_context`，并设置匹配的纯 HTTPS `public_origin`。
- LAN：必须指定可达的 `public_origin`。没有 TLS 时，只有明确告知并获得同意，才使用 `allow_plain_lan=True`；私有网络里的 HTTP 仍是明文。手机不能访问另一台机器的 loopback URL。
- 一次接受提交后关闭监听。结果为 `submitted`、`expired` 或 `handler_failed`。处理失败可能已产生部分效果，应先检查目标状态，不直接重试。

实现校验路由、Host、Origin 和提交令牌，不记录请求访问日志，并发送 no-store 头。这不是安全审计，也不保证受入侵主机上的安全；不保证内存清零、不强制终止超时回调，也不替代浏览器的受保护凭据保险库登录流程。

## 验证范围

仓库包含 6 项单元测试，覆盖正常提交、一次性关闭、过期、错误 Origin/token/路由、LAN 明文显式同意与处理器失败。另以独立 loopback HTTP 客户端，在 macOS 与 Windows OMP 中验证了短时同步等待及同会话继续写报告。这些宿主实验不包含在仓库单测中，不应由单测通过推导其重复通过。

尚未验证：浏览器 JavaScript／渲染端到端、每个 CLI 面向真人的链接递交、密码管理器填充、真实下游认证、LAN/TLS 集成、长等待、OMP 后台唤醒，以及会话替换后的恢复。Windows 关闭端口探测须区分超时/10035 与明确拒绝/10061；实测环境中一秒探测不足。

## 文件

- `SKILL.md`：可移植的 Agent 工作方式和边界。
- `scripts/private_input.py`：Python 标准库 HTTP 辅助程序。
- `scripts/test_private_input.py`：6 项单元测试。
- `examples/discard_demo.py`：可运行的浏览器演示，仅用于测试文字。

## 许可

[MIT](LICENSE)。
