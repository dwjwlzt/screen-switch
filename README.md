# ScreenSwitch

通过软件指令切换显示器输入源（DP / HDMI1 / HDMI2），支持电源控制和开机自启。

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
python "screen switch.py" status

# 切换输入源
python "screen switch.py" dp
python "screen switch.py" hdmi1
python "screen switch.py" hdmi2

# 循环切换 DP → HDMI1 → HDMI2 → DP
python "screen switch.py" toggle

# 电源控制
python "screen switch.py" off       # 软关机
python "screen switch.py" on        # 开机
python "screen switch.py" standby   # 待机
python "screen switch.py" suspend   # 挂起
python "screen switch.py" off_hard  # 硬关机

# 开机自动切到 DP
python "screen switch.py" autostart enable dp
```

## 全部命令

### 输入源切换

| 命令 | 说明 |
|------|------|
| `python screen switch.py dp` | 切到 DisplayPort |
| `python screen switch.py hdmi1` | 切到 HDMI 1 |
| `python screen switch.py hdmi2` | 切到 HDMI 2 |
| `python screen switch.py toggle` | 三端口循环切换（默认行为，无参数运行即执行此命令） |
| `python screen switch.py status` | 查询当前输入源和电源状态 |

### 电源控制

| 命令 | 说明 |
|------|------|
| `python screen switch.py on` | 开机（Win32 API + DDC/CI 双保险） |
| `python screen switch.py off` | 软关机（off_soft，显示器进入低功耗） |
| `python screen switch.py off_hard` | 硬关机（off_hard） |
| `python screen switch.py standby` | 待机 |
| `python screen switch.py suspend` | 挂起 |

电源控制采用 DDC/CI + Windows Win32 API `PostMessage(WM_SYSCOMMAND, SC_MONITORPOWER)` 双保险机制，确保在不同显示器上都生效。

### 开机自启

| 命令 | 说明 |
|------|------|
| `python screen switch.py autostart enable [目标]` | 安装开机自启，目标为 `dp` / `hdmi1` / `hdmi2`，默认 dp |
| `python screen switch.py autostart disable` | 取消开机自启 |
| `python screen switch.py autostart status` | 查看当前自启状态 |

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
    → pythonw.exe "screen switch.py" dp（无窗口执行，不弹黑框）
    → 切换到 DP，写入 .last_input = "DP"
```

### 架构图

```
┌─────────────────────────────────────────────────┐
│                命令行入口 switch()                │
└──────────────────┬──────────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
 PORT_MAP      POWER_MAP       toggle逻辑
 (dp/hdmi)    (on/off/standby) (next_in_cycle)
    │              │              │
    └──────────────┼──────────────┘
                   ▼
           monitorcontrol 库
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
    Windows VCP API      Win32 PostMessage
    (ctypes DDC/CI)      (电源控制双保险)
         │                   │
         └─────────┬─────────┘
                   ▼
         DDC/CI I²C 协议
                   │
                   ▼
          显示器 MCU（内部控制器）
                   │
          ┌────────┴────────┐
          ▼                 ▼
     切换物理输入通道    切换物理电源状态
```

## 注意事项

- **DDC/CI 必须开启** — 在显示器物理菜单里找到 DDC/CI 或 Display Data Channel 选项并开启，否则指令无法发送
- **本项目只操作第一台显示器** — 如果有多台显示器，需要扩展 `monitors[0]` 加选择逻辑
- **硬编码 DP1/HDMI1/HDMI2** — 大多数显示器够用；如果有 DP2/HDMI2 的第二个实例，需扩展 `PORT_MAP` / `VCP_NAME_MAP`
- **缓存文件位置** — `.last_input` 放在脚本同目录；如果脚本被打包成 exe 放到只读目录（如 `C:\Program Files`），写入会静默失败，此时 toggle 只能依赖 VCP 读取
- **关机后 DDC/CI 断开** — 显示器关机后 `get_monitors()` 会失败，但 `on` 命令已通过 Win32 API 绕过此问题，不影响开机