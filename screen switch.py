from monitorcontrol import get_monitors, InputSource
import sys
import time
import os

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_input")

PORT_MAP = {
    "dp": InputSource.DP1,
    "dp1": InputSource.DP1,
    "hdmi": InputSource.HDMI1,
    "hdmi1": InputSource.HDMI1,
}

LABEL_MAP = {
    InputSource.DP1: "DP",
    InputSource.HDMI1: "HDMI",
}


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


def switch(target: str = None):
    monitors = list(get_monitors())
    if not monitors:
        print("未检测到显示器")
        sys.exit(1)

    target = (target or "toggle").lower().strip()
    mon = monitors[0]

    if target == "status":
        with mon:
            vcp = _query_vcp(mon)
            if vcp is not None:
                name = {15: "DP", 16: "HDMI"}.get(vcp, f"VCP={vcp}")
                print(f"当前输入源: {name}")
            else:
                cached = _read_state()
                if cached:
                    print(f"当前输入源: ? (上次记录为 {cached})")
                else:
                    print("无法读取当前输入源 (HDMI 通道不支持读)")
        return

    if target == "toggle":
        with mon:
            vcp = _query_vcp(mon)
            if vcp is not None:
                next_src = InputSource.HDMI1 if vcp == 15 else InputSource.DP1
            else:
                cached = _read_state()
                if cached == "HDMI":
                    next_src = InputSource.DP1
                else:
                    next_src = InputSource.HDMI1
            print(f"切换到 {LABEL_MAP[next_src]}...")
            mon.set_input_source(next_src)
            _write_state(next_src)
            time.sleep(1)
            print(f"已切换到 {LABEL_MAP[next_src]} ✓")
        return

    if target not in PORT_MAP:
        print("用法:")
        print("  python switch_monitor.py dp     切到 DP")
        print("  python switch_monitor.py hdmi   切到 HDMI")
        print("  python switch_monitor.py toggle DP/HDMI 循环切换")
        print("  python switch_monitor.py status 查询状态")
        sys.exit(1)

    src = PORT_MAP[target]
    with mon:
        print(f"正在切换到 {LABEL_MAP[src]}...")
        mon.set_input_source(src)
        _write_state(src)
        time.sleep(1)
        print(f"已切换到 {LABEL_MAP[src]} ✓")


if __name__ == "__main__":
    switch(sys.argv[1] if len(sys.argv) > 1 else "toggle")