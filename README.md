# ScreenSwitch

通过软件指令切换显示器输入源（DP / HDMI1 / HDMI2），支持电源控制、开机自启和**手机远程控制**。

## 文件结构

```
屏幕切换/
├── tray.py                系统托盘入口（打包 exe 用）
├── screen_switch.py       核心逻辑 + CLI 入口
├── webserver.py           局域网 HTTP 服务（手机远程控制）
├── templates/
│   ├── index.html         手机端控制页面
│   └── favicon.png        网页图标
├── .gitignore             忽略构建产物、图标等
├── requirements.txt       依赖
└── .last_input            上次切换的输入源（自动生成）
```

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11 |
| Python | >= 3.10 |
| 显示器 | 支持 DDC/CI（显示器菜单里需开启） |
| GPU | 独显或核显，通过视频输出口连接显示器 |

### 依赖

```
monitorcontrol >= 4.2.0
```

### 安装

```bash
pip install -r requirements.txt
```

## 快速开始

```bash
# 查询当前状态
python "screen_switch.py" status

# 切换输入源
python "screen_switch.py" dp
python "screen_switch.py" hdmi1
python "screen_switch.py" hdmi2

# 循环切换 DP → HDMI1 → HDMI2 → DP
python "screen_switch.py" toggle

# 电源控制
python "screen_switch.py" off       # 软关机
python "screen_switch.py" on        # 开机
python "screen_switch.py" standby   # 待机
python "screen_switch.py" suspend   # 挂起
python "screen_switch.py" off_hard  # 硬关机

# 开机自动切到 DP
python "screen_switch.py" autostart enable dp
```

## 手机远程控制

最实用的功能——当你切到其他输入源（比如游戏机、机顶盒）后显示器不再显示电脑画面，手机就是你的救星。

### 启动服务

```bash
# 默认 0.0.0.0:8765，无鉴权
python webserver.py

# 加 token 鉴权（推荐，防止局域网其他人误操作）
python webserver.py --token mysecret123

# 自定义端口
python webserver.py --port 9000

# 只允许本机访问
python webserver.py --host 127.0.0.1
```

启动后会打印：

```
==================================================
  显示器控制 Web 服务已启动
==================================================
  本机访问:  http://127.0.0.1:8765
  手机访问:  http://192.168.3.2:8765
==================================================
```

### 手机使用

1. 手机和电脑连**同一个 WiFi**
2. 手机浏览器打开 `http://` + 电脑显示的那个局域网地址（比如 `http://192.168.3.2:8765`）
3. 如果设置了 token，有两种方式：在页面顶部「访问令牌」里填写后点保存，或直接打开 `http://电脑地址:8765/?token=你的token`（会自动保存并清理地址栏）
4. 页面上大按钮直接操作：切输入源、开关显示器、待机

### API 接口

所有接口返回 JSON，`ok` 字段表示成功与否。启动时带了 `--token` 的话，GET 请求加 `?token=xxx`，POST 在 body 里带 `"token": "xxx"`；不带或错误会返回 401。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 返回手机控制页面 |
| GET | `/api/status?token=xxx` | 查询当前输入源和电源状态 |
| POST | `/api/exec` | 执行操作，body 为 `{"action": "dp", "token": "..."}` |

`action` 可取值：`dp` / `hdmi1` / `hdmi2` / `toggle` / `on` / `off` / `off_soft` / `off_hard` / `standby` / `suspend` / `status`

示例：

```bash
# 查询状态
curl http://127.0.0.1:8765/api/status

# 切换到 DP
curl -X POST http://127.0.0.1:8765/api/exec \
  -H "Content-Type: application/json" \
  -d '{"action": "dp"}'
```

### 常见问题

- **手机打不开？** — 检查手机和电脑是否同一 WiFi；Windows 防火墙是否拦了端口（首次启动如果弹框点允许）；iPhone 开了「私有中继」可临时关掉
- **token 不记得了？** — 重启服务用新 token；或不带 `--token` 启动临时解除鉴权
- **想后台常驻？** — 用 `pythonw.exe webserver.py --token xxx` 启动，不会弹黑框

## 全部命令

### 输入源切换

| 命令 | 说明 |
|------|------|
| `python screen_switch.py dp` | 切到 DisplayPort |
| `python screen_switch.py hdmi1` | 切到 HDMI 1 |
| `python screen_switch.py hdmi2` | 切到 HDMI 2 |
| `python screen_switch.py toggle` | 三端口循环切换（默认行为，无参数运行即执行此命令） |
| `python screen_switch.py status` | 查询当前输入源和电源状态 |

### 电源控制

| 命令 | 说明 |
|------|------|
| `python screen_switch.py on` | 开机（Win32 API + DDC/CI 双保险） |
| `python screen_switch.py off` | 软关机（off_soft，显示器进入低功耗） |
| `python screen_switch.py off_hard` | 硬关机（off_hard） |
| `python screen_switch.py standby` | 待机 |
| `python screen_switch.py suspend` | 挂起 |

电源控制采用 DDC/CI + Windows Win32 API `PostMessage(WM_SYSCOMMAND, SC_MONITORPOWER)` 双保险机制，确保在不同显示器上都生效。

### 开机自启

| 命令 | 说明 |
|------|------|
| `python screen_switch.py autostart enable [目标]` | 安装开机自启，目标为 `dp` / `hdmi1` / `hdmi2`，默认 dp |
| `python screen_switch.py autostart disable` | 取消开机自启 |
| `python screen_switch.py autostart status` | 查看当前自启状态 |

自启实现：在 Windows 启动文件夹写入 `ScreenSwitch.vbs`，开机等 8 秒（让 DDC/CI 就绪）后无窗口执行切换。

## 原理

### DDC/CI 协议

整个项目基于 **VESA DDC/CI**（Display Data Channel / Command Interface）—— 这是显示器的带内通信协议，藏在 DP/HDMI 视频信号里，不需要额外信号线。

```
电脑 GPU ─── DP / HDMI 线 ─── 显示器
                │
           DDC/CI 通道
           电脑可以发指令给显示器：
             "切到 HDMI1"
             "把亮度调到 80"
             "你现在是哪个输入源？"
             "关机" / "开机"
           显示器回复：
             "好的"
             "VCP=15 (DP)"
```

效果等同于按显示器上的物理菜单按钮，只是换成了软件发指令。

### monitorcontrol 库

`monitorcontrol` 封装了 Windows 的 VCP（Virtual Control Panel）API，提供 Python 接口：

```python
from monitorcontrol import get_monitors, InputSource, PowerMode

monitors = list(get_monitors())   # 通过 DDC/CI 握手发现显示器
mon = monitors[0]

with mon:                         # 建立 DDC/CI 会话
    mon.set_input_source(InputSource.HDMI1)   # 写 VCP 代码 → 切源
    mon.set_power_mode(PowerMode.off_soft)    # 写 VCP 代码 → 关机
    vcp = mon.get_input_source()              # 读 VCP 代码 → 查当前通道
    pm = mon.get_power_mode()                 # 读 VCP 代码 → 查电源状态
```

### VCP 编号

每个显示器通道对应一个标准 VCP 编号：

| 枚举 | VCP 十进制 | 含义 |
|------|-----------|------|
| `InputSource.DP1` | 15 | DisplayPort |
| `InputSource.HDMI1` | 17 | HDMI 1 |
| `InputSource.HDMI2` | 18 | HDMI 2 |

### 缓存文件 `.last_input`

toggle（循环切换）需要知道"当前在哪个通道"才能算出下一个。但部分显示器的 DDC/CI 读取存在问题：

- 某些 HDMI 通道不支持 `get_input_source()`，直接抛异常
- 某些显示器 HDMI1 通道 get 时**错误返回 HDMI2 的编号**

解决方案：**每次 set 成功后，代码自己把目标通道写入 `.last_input` 文件**。这个值来自代码的主动设定，不会被显示器的错误回复干扰。

toggle 时的信任策略：

1. 尝试读 VCP（显示器报告）
2. 读缓存文件（代码自存）
3. 如果 VCP 和缓存一致 → 两者都可信，用 VCP 算下一个
4. 如果不一致或 VCP 读不到 → 用缓存算下一个（缓存永远可信）
5. 都没有 → 默认回 DP

### 电源控制双保险

`off` / `on` 等电源命令采用两层机制：

```
关机:
  1. DDC/CI mon.set_power_mode(PowerMode.off_soft)
  2. Win32 PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)

开机:
  1. Win32 PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, -1)
  2. 等待 1.5 秒
  3. DDC/CI mon.set_power_mode(PowerMode.on)（作为兜底）
```

当 DDC/CI 关机后显示器断电时，`get_monitors()` 会失败——但开机命令通过 Win32 API 绕过了这个限制，不需要 DDC/CI 通路。

### 开机自启流程

```
Windows 启动
    → 启动文件夹 ScreenSwitch.vbs 触发
    → WScript.Sleep 8000（等 8 秒让 DDC/CI 就绪）
    → pythonw.exe "screen_switch.py" dp（无窗口执行，不弹黑框）
    → 切换到 DP，写入 .last_input = "DP"
```

### 架构图

```
┌──────────────────────────────────────────┐
│               tray.py                    │
│  系统托盘 (pystray) + 启动 webserver      │
└─────────────────────────┬────────────────┘
                          │ 线程启动
                 ┌────────┴─────────┐
                 ▼                  │
    ┌──────────────────┐            │
    │   templates/     │            │
    │   index.html     │            │
    └────────┬─────────┘            │
             │ HTTP                 │
┌────────────┴──────────────────────┴────────────────┐
│                  webserver.py                       │
│   http.server  (GET /  POST /api/exec  GET /api/status)
│   importlib 导入  screen_switch 模块               │
└─────────────────────────┬─────────────────────────┘
                          │ _execute(action) → dict
┌─────────────────────────┴─────────────────────────┐
│              screen_switch.py                      │
│                                                     │
│  ┌──────────────────────────────────────────┐      │
│  │           命令行入口 switch()             │      │
│  └────────────────────┬─────────────────────┘      │
│                       │                             │
│      ┌────────────────┼────────────────┐            │
│      ▼                ▼                ▼            │
│  PORT_MAP          POWER_MAP       toggle 逻辑     │
│  (dp/hdmi)        (on/off/standby) (next_in_cycle)  │
│      │                │                │            │
│      └────────────────┼────────────────┘            │
│                       ▼                             │
│              monitorcontrol 库                       │
│                       │                             │
└───────────────────────┬─────────────────────────────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
    Windows VCP API              Win32 PostMessage
    (ctypes DDC/CI)              (电源控制双保险)
         │                             │
         └──────────────┬──────────────┘
                        ▼
               DDC/CI I²C 协议
                        │
                        ▼
               显示器 MCU（内部控制器）
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
         切换物理输入通道      切换物理电源状态
```

## 注意事项

- **DDC/CI 必须开启** — 在显示器物理菜单里找到 DDC/CI 或 Display Data Channel 选项并开启，否则指令无法发送
- **本项目只操作第一台显示器** — 如果有多台显示器，需要扩展 `monitors[0]` 加选择逻辑
- **硬编码 DP1/HDMI1/HDMI2** — 大多数显示器够用；如果有 DP2/HDMI2 的第二个实例，需扩展 `PORT_MAP` / `VCP_NAME_MAP`
- **缓存文件位置** — `.last_input` 放在脚本同目录；如果脚本被打包成 exe 放到只读目录（如 `C:\Program Files`），写入会静默失败，此时 toggle 只能依赖 VCP 读取
- **关机后 DDC/CI 断开** — 显示器关机后 `get_monitors()` 会失败，但 `on` 命令已通过 Win32 API 绕过此问题，不影响开机