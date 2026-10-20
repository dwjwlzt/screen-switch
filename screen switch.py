from monitorcontrol import get_monitors, InputSource, PowerMode
import sys
import time
import os
import ctypes
import subprocess

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_input")
SCRIPT_PATH = os.path.abspath(__file__)

PORT_MAP = {
    "dp": InputSource.DP1,
    "dp1": InputSource.DP1,
    "hdmi": InputSource.HDMI1,
    "hdmi1": InputSource.HDMI1,
    "hdmi2": InputSource.HDMI2,
}

LABEL_MAP = {
    InputSource.DP1: "DP",
    InputSource.HDMI1: "HDMI1",
    InputSource.HDMI2: "HDMI2",
}

VCP_NAME_MAP = {
    15: "DP",
    17: "HDMI1",
    18: "HDMI2",
}

CYCLE = [InputSource.DP1, InputSource.HDMI1, InputSource.HDMI2]

POWER_MAP = {
    "on": PowerMode.on,
    "poweron": PowerMode.on,
    "standby": PowerMode.standby,
    "suspend": PowerMode.suspend,
    "off": PowerMode.off_soft,
    "off_soft": PowerMode.off_soft,
    "off_hard": PowerMode.off_hard,
}

_HWND_BROADCAST = 0xFFFF
_WM_SYSCOMMAND = 0x0112
_SC_MONITORPOWER = 0xF170
_MONITORPOWER_ON = -1
_MONITORPOWER_OFF = 2
_MONITORPOWER_STANDBY = 1


def _win32_monitor_power(action: int):
    try:
        ctypes.windll.user32.PostMessageW(
            _HWND_BROADCAST, _WM_SYSCOMMAND, _SC_MONITORPOWER, action
        )
        return True
    except Exception:
        return False


_AUTOSTART_NAME = "ScreenSwitch.vbs"


def _startup_dir():
    return os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )


def _startup_vbs_path():
    return os.path.join(_startup_dir(), _AUTOSTART_NAME)


def _find_pythonw():
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in [
        os.path.join(here, ".venv", "Scripts", "pythonw.exe"),
        os.path.join(sys.exec_prefix, "pythonw.exe"),
    ]:
        if os.path.isfile(candidate):
            return candidate
    try:
        result = subprocess.run(
            ["where", "pythonw"], capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return None


def _autostart_install(target_port: str = "dp"):
    pythonw = _find_pythonw()
    if not pythonw:
        print("找不到 pythonw.exe，无法设置开机自启")
        sys.exit(1)

    vbs_dir = _startup_dir()
    vbs_path = _startup_vbs_path()
    os.makedirs(vbs_dir, exist_ok=True)

    vbs_content = (
        'WScript.Sleep 8000\r\n'
        'Set ws = CreateObject("WScript.Shell")\r\n'
        f'ws.Run """{pythonw}"" ""{SCRIPT_PATH}"" {target_port}", 0, False\r\n'
    )

    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    print(f"已安装开机自启 (启动后自动切到 {target_port.upper()})")
    print(f"VBS 路径: {vbs_path}")


def _autostart_uninstall():
    vbs_path = _startup_vbs_path()
    if os.path.isfile(vbs_path):
        os.remove(vbs_path)
        print("已取消开机自启")
    else:
        print("当前未设置开机自启")


def _autostart_status():
    vbs_path = _startup_vbs_path()
    if os.path.isfile(vbs_path):
        with open(vbs_path, "r", encoding="utf-8") as f:
            content = f.read()
        print("开机自启: 已开启")
        print(f"VBS 路径: {vbs_path}")
        print(f"内容预览: {content.strip()}")
    else:
        print("开机自启: 未开启")


def _write_state(src: InputSource):
    try:
        with open(STATE_FILE, "w") as f:
            f.write(LABEL_MAP.get(src, str(src)))
    except Exception:
        pass


def _read_state():
    try:
        with open(STATE_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        return None


def _query_vcp(mon):
    try:
        return int(mon.get_input_source())
    except Exception:
        return None


CYCLE_LABELS = ["DP", "HDMI1", "HDMI2"]


def _next_in_cycle(vcp: int | None, cached: str | None) -> InputSource:
    use_cached = cached is not None
    use_vcp = (
        vcp is not None
        and vcp in VCP_NAME_MAP
        and (cached is None or VCP_NAME_MAP[vcp] == cached)
    )

    if use_vcp:
        try:
            current_src = InputSource(vcp)
            idx = CYCLE.index(current_src)
            return CYCLE[(idx + 1) % len(CYCLE)]
        except ValueError:
            pass

    if use_cached:
        for i, label in enumerate(CYCLE_LABELS):
            if cached == label:
                return CYCLE[(i + 1) % len(CYCLE)]

    return CYCLE[0]


def switch(target: str = None):
    target = (target or "toggle").lower().strip()

    if target.startswith("autostart"):
        parts = target.split()
        action = parts[1] if len(parts) > 1 else "status"
        port = parts[2] if len(parts) > 2 and parts[2] in PORT_MAP else "dp"
        if action == "enable":
            _autostart_install(port)
        elif action == "disable":
            _autostart_uninstall()
        elif action == "status":
            _autostart_status()
        else:
            print("用法:")
            print("  python switch_monitor.py autostart enable [dp|hdmi1|hdmi2]")
            print("  python switch_monitor.py autostart disable")
            print("  python switch_monitor.py autostart status")
        return

    if target in ("on", "poweron"):
        if _win32_monitor_power(_MONITORPOWER_ON):
            time.sleep(1.5)
        try:
            monitors = list(get_monitors())
            if monitors:
                with monitors[0] as mon:
                    mon.set_power_mode(PowerMode.on)
            print("已切换到 on ✓")
        except Exception:
            print("已切换到 on ✓ (通过 Windows API 唤醒)")
        return

    try:
        monitors = list(get_monitors())
    except Exception:
        monitors = []

    if not monitors:
        print("未检测到显示器")
        sys.exit(1)

    mon = monitors[0]

    if target == "status":
        with mon:
            vcp = _query_vcp(mon)
            if vcp is not None:
                name = VCP_NAME_MAP.get(vcp, f"VCP={vcp}")
                print(f"当前输入源: {name}")
            else:
                cached = _read_state()
                if cached:
                    print(f"当前输入源: ? (上次记录为 {cached})")
                else:
                    print("无法读取当前输入源 (HDMI 通道不支持读)")
            try:
                pm = mon.get_power_mode()
                print(f"当前电源状态: {pm.name}")
            except Exception:
                print("电源状态: ? (无法读取)")
        return

    if target in POWER_MAP:
        pm = POWER_MAP[target]
        with mon:
            print(f"切换电源状态 -> {pm.name}...")
            mon.set_power_mode(pm)

        if pm != PowerMode.on:
            win32_action = {
                PowerMode.standby: _MONITORPOWER_STANDBY,
                PowerMode.suspend: _MONITORPOWER_STANDBY,
                PowerMode.off_soft: _MONITORPOWER_OFF,
                PowerMode.off_hard: _MONITORPOWER_OFF,
            }.get(pm)
            if win32_action is not None:
                _win32_monitor_power(win32_action)

        time.sleep(1)
        print(f"已切换到 {pm.name} ✓")
        return

    if target == "toggle":
        with mon:
            vcp = _query_vcp(mon)
            cached = _read_state()
            next_src = _next_in_cycle(vcp, cached)
            print(f"切换到 {LABEL_MAP[next_src]}...")
            mon.set_input_source(next_src)
            _write_state(next_src)
            time.sleep(1)
            print(f"已切换到 {LABEL_MAP[next_src]} ✓")
        return

    if target not in PORT_MAP:
        print("用法:")
        print("  python switch_monitor.py dp      切到 DP")
        print("  python switch_monitor.py hdmi1   切到 HDMI1")
        print("  python switch_monitor.py hdmi2   切到 HDMI2")
        print("  python switch_monitor.py toggle  DP / HDMI1 / HDMI2 循环切换")
        print("  python switch_monitor.py status  查询状态")
        print("  python switch_monitor.py on      开机")
        print("  python switch_monitor.py off     软关机")
        print("  python switch_monitor.py off_hard 硬关机")
        print("  python switch_monitor.py standby 待机")
        print("  python switch_monitor.py suspend 挂起")
        sys.exit(1)

    src = PORT_MAP[target]
    with mon:
        print(f"正在切换到 {LABEL_MAP[src]}...")
        mon.set_input_source(src)
        _write_state(src)
        time.sleep(1)
        print(f"已切换到 {LABEL_MAP[src]} ✓")


if __name__ == "__main__":
    switch(" ".join(sys.argv[1:]) if len(sys.argv) > 1 else "toggle")