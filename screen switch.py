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


def _autostart_status_text():
    vbs_path = _startup_vbs_path()
    if os.path.isfile(vbs_path):
        return f"开机自启: 已开启 ({vbs_path})"
    return "开机自启: 未开启"


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


def _execute(action: str) -> dict:
    action = (action or "toggle").lower().strip()

    if action.startswith("autostart"):
        parts = action.split()
        sub = parts[1] if len(parts) > 1 else "status"
        port = parts[2] if len(parts) > 2 and parts[2] in PORT_MAP else "dp"
        if sub == "enable":
            try:
                _autostart_install(port)
                return {"ok": True, "message": f"已安装开机自启 ({port.upper()})"}
            except SystemExit:
                return {"ok": False, "message": "找不到 pythonw.exe"}
        elif sub == "disable":
            _autostart_uninstall()
            return {"ok": True, "message": "已取消开机自启"}
        elif sub == "status":
            return {"ok": True, "message": _autostart_status_text()}
        return {"ok": False, "message": "未知 autostart 操作"}

    if action in ("on", "poweron"):
        if _win32_monitor_power(_MONITORPOWER_ON):
            time.sleep(1.5)
        try:
            monitors = list(get_monitors())
            if monitors:
                with monitors[0] as mon:
                    mon.set_power_mode(PowerMode.on)
            return {"ok": True, "message": "已开机"}
        except Exception:
            return {"ok": True, "message": "已开机 (通过 Windows API)"}

    try:
        monitors = list(get_monitors())
    except Exception:
        monitors = []

    if not monitors:
        return {"ok": False, "message": "未检测到显示器"}

    mon = monitors[0]

    if action == "status":
        with mon:
            vcp = _query_vcp(mon)
            cached = _read_state()
            current = "未知"
            if vcp is not None:
                current = VCP_NAME_MAP.get(vcp, f"VCP={vcp}")
            elif cached:
                current = f"? (上次记录 {cached})"
            try:
                pm = mon.get_power_mode()
                power = pm.name
            except Exception:
                power = "未知"
            return {
                "ok": True,
                "message": f"输入源: {current}, 电源: {power}",
                "input_source": current,
                "power": power,
            }

    if action in POWER_MAP:
        pm = POWER_MAP[action]
        with mon:
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
        return {"ok": True, "message": f"电源 -> {pm.name}"}

    if action == "toggle":
        with mon:
            vcp = _query_vcp(mon)
            cached = _read_state()
            next_src = _next_in_cycle(vcp, cached)
            mon.set_input_source(next_src)
            _write_state(next_src)
            time.sleep(1)
            return {"ok": True, "message": f"已切换到 {LABEL_MAP[next_src]}"}

    if action in PORT_MAP:
        src = PORT_MAP[action]
        with mon:
            mon.set_input_source(src)
            _write_state(src)
            time.sleep(1)
            return {"ok": True, "message": f"已切换到 {LABEL_MAP[src]}"}

    return {"ok": False, "message": f"未知操作: {action}"}


def switch(target: str = None):
    target = (target or "toggle").lower().strip()

    if target in ("server", "web", "serve") or target.startswith("server") or target.startswith("web"):
        print("Web 服务已分离到 webserver.py")
        print("用法: python webserver.py [--host HOST] [--port PORT] [--token TOKEN]")
        sys.exit(1)

    result = _execute(target)
    if result["ok"]:
        print(result["message"])
    else:
        print(f"错误: {result['message']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    switch(" ".join(sys.argv[1:]) if len(sys.argv) > 1 else "toggle")