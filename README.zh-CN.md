<div align="center">

# Private Key Input

**让本地 Agent 获取任务所需凭据，而不必把凭据贴进聊天。**

短时 HTML 页面把输入交给任务专用的本机回调；Agent 只接收处理结果，并继续原任务。

[English](README.md) · [快速开始](#快速开始) · [让-agent-使用](#让-agent-使用) · [安全模型](#安全模型)

![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-1f6f5c) ![仅标准库](https://img.shields.io/badge/dependencies-standard_library_only-cb6d32) [![MIT 许可](https://img.shields.io/badge/license-MIT-244f73)](LICENSE)

</div>

## 为什么需要它

把凭据贴进聊天，可能让它进入会话历史和模型上下文。Private Key Input 为 Agent 工作流提供一条更小的路径：

```text
你 -> 临时页面 -> 本机回调 -> 已授权的目标服务
                    |
               仅处理状态 -> Agent 继续任务
```

- **一个任务，一个页面。** 随机路径默认十分钟过期，接受一次提交后关闭。
- **不是凭据平台。** 实现只用 Python 标准库，不需要守护进程、数据库、插件或新保险库。
- **只回传结果。** 回调在本机消费输入，宿主只收到 `submitted`、`expired` 或 `handler_failed`。
- **网络边界明确。** 默认仅回环地址；LAN 明文访问必须显式开启，调用方也可提供 TLS。

> [!IMPORTANT]
> 它不是密码保险库，也不是操作系统沙箱。本机回调与目标服务必然接触明文。要让凭据不出现在 Agent 可见输出中，任务包装程序也不能打印、返回或记录该值。

<a id="快速开始"></a>
## 快速开始

### 1. 安装为 Skill

需要 Python 3.9+，以及支持 `SKILL.md` 的客户端。不依赖第三方 Python 包。

Hermes 默认 profile 示例：

```bash
git clone https://github.com/Loveacup/private-key-input.git ~/.hermes/skills/private-key-input
python3 -B -m unittest discover -s ~/.hermes/skills/private-key-input/scripts -p 'test_*.py'
```

检查成功时，结尾应为：

```text
Ran 6 tests

OK
```

目标目录必须尚不存在。其他客户端应使用其真实支持的 Skill 目录，不要照搬 Hermes 路径。安装文件不会启动监听、保存凭据或修改客户端配置。

### 2. 运行丢弃型 Demo

接着进入刚才安装的目录（已有检出则使用其实际路径）：

```bash
cd ~/.hermes/skills/private-key-input
python3 -B examples/discard_demo.py
```

Windows 没有 `python3` 时可运行 `py -B examples/discard_demo.py`。

命令会打印本机回环 URL，并等待最多十分钟。在同一台机器的浏览器中打开页面，**只输入测试文字**并提交。回调会丢弃输入，终端最终显示：

```text
Outcome: submitted
```

不要在该 Demo 中输入真实凭据。

<a id="让-agent-使用"></a>
## 让 Agent 使用

安装为 Skill 后，可直接这样请求：

> 当前任务需要凭据时使用 private-key-input。先确定已授权的目标，再提供临时页面；不要把输入放进聊天或工具输出，提交后复用宿主现有机制自动继续任务。不要新增回调服务，也不要未经授权另建存储。

完整操作契约见 [`SKILL.md`（英文）](SKILL.md)，其中说明了何时使用、如何递交页面、怎样在用户不补发“好了”的情况下继续，以及何时应改用宿主的受保护凭据保险库。

## 接入任务

从 [`scripts/private_input.py`](scripts/private_input.py) 导入 `InputServer` 或 `serve`。在仓库根目录运行以下丢弃型示例；真实任务由包装程序提供面向已授权目标的回调：

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts").resolve()))
from private_input import serve


def accept(secret):
    return None  # Discard-only example; use test text.


serve(accept, purpose="Demo: input is discarded; use test text only.")
```

真实任务中，使用目标已有的凭据 API，扩展回调而不是改写通用页面。回调应返回 `None`，不得打印或返回输入、请求头、响应正文和原始异常。携带凭据的网络请求应设置超时并拒绝重定向。

### 宿主如何自动继续

`serve(...)` 打印 URL、等待页面提交，再打印结果。宿主需要单独递交链接时，可使用提供 `url` 与 `run()` 的 `InputServer(...)`。

- 终端通常能在进程结束前显示已 flush 的输出；部分 Agent 工具会缓存到命令退出，因此必须先核验链接是否能及时交给用户。
- 工具会缓存输出时，应启动任务自有临时进程、递交 URL，再复用宿主已有的完成机制等待；不要增加常驻回调服务。
- 只把非密钥状态返回原会话。宿主原生支持续接时，不再要求用户另发一句“好了”。

<a id="安全模型"></a>
## 安全模型

### 辅助程序负责什么

- 默认监听 `127.0.0.1`，由系统分配空闲端口。
- 使用随机页面路径与提交令牌。
- 校验路由、`Host`、`Origin`、内容类型、正文大小和提交令牌。
- 发送 no-store、no-referrer、CSP、防嵌入和内容类型保护响应头。
- 禁用 HTTP 访问日志和请求处理 traceback 输出。
- 接受一次提交、回调失败或等待过期后关闭；宿主负责取消时终止自有进程。

### 调用方仍要负责什么

- 在等待阻塞前把 URL 交给真人。
- 只把输入用于已授权的目标。
- 防止明文进入日志、Shell 参数、源码、状态文件或 Agent 输出。
- `handler_failed` 后先检查目标状态再重试，因为回调可能已部分完成。
- 浏览器密码、登录表单和 2FA 若有宿主凭据保险库，应优先使用原生受保护流程。

### LAN 与 TLS

回环 URL 只能由运行服务的机器访问。其他设备访问时，必须提供可达的 `public_origin`。

- 优先复用已有的可信 HTTPS 路径。
- 使用 TLS 时，传入 `ssl.SSLContext` 作为 `tls_context`，并提供匹配的纯 HTTPS `public_origin`。
- 没有 TLS 时必须显式设置 `allow_plain_lan=True`。即使在私有网络中，HTTP 仍是明文，只应在知情同意后使用。

页面默认简体中文。密码框带有标准自动填充提示，但尚未证实与 1Password 的联动；页面不会自动提交密码管理器填入的值。

这不是安全审计，也不保证受入侵主机上的安全、内存清零或回调的硬超时。默认 `ttl=600` 是等待期限，不是回调执行期限。

<details>
<summary>参数与结果</summary>

`InputServer(callback, purpose, host="127.0.0.1", port=0, ttl=600, allow_plain_lan=False, tls_context=None, public_origin=None)`

- `port=0`：选择空闲端口。
- `submitted`：回调已返回，不等于下游认证通过。
- `expired`：等待期限已到。
- `handler_failed`：回调抛出异常，先检查是否部分完成再决定重试。

</details>

## 验证情况

仓库中的 6 项测试覆盖：

- HTML 页面获取与一次性提交；
- 过期与监听关闭；
- 拒绝错误路由、Origin 和令牌；
- LAN 明文访问必须显式同意；
- 回调失败时不反射提交内容。

Python 辅助程序及短时同步续接还在 macOS 与 Windows 上，通过独立 loopback HTTP 客户端做过实测：模拟输入提交后，同一会话可以继续写报告。这项宿主实验不包含在仓库单元测试中。

尚未验证：浏览器渲染／JavaScript 端到端、每个 CLI 面向真人的链接递交、密码管理器填充、真实下游认证、LAN/TLS 集成、长时间等待、分离进程唤醒，以及会话替换后的恢复。

## 项目结构

```text
.
├── SKILL.md                     # Agent 工作流与边界
├── examples/discard_demo.py     # 仅用于测试文字的浏览器 Demo
└── scripts/
    ├── private_input.py         # Python 标准库 HTTP 辅助程序
    └── test_private_input.py    # 6 项单元测试
```

## 许可

[MIT](LICENSE)
