import os
import sys
import threading


def _resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    candidates = [
        os.path.join(base, rel),
        os.path.join(exe_dir, rel),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def _load_icon_image():
    ico_path = _resource_path("切换.ico")
    from PIL import Image, ImageDraw
    if os.path.isfile(ico_path):
        return Image.open(ico_path)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=(66, 135, 245, 255), outline=(255, 255, 255, 255), width=2)
    draw.text((22, 24), "切", fill=(255, 255, 255, 255))
    return img


def _start_webserver():
    import webserver
    webserver.run_server()


def main():
    import pystray
    from pystray import MenuItem as Item

    threading.Thread(target=_start_webserver, daemon=True).start()

    image = _load_icon_image()

    def on_quit(icon, item):
        icon.stop()
        os._exit(0)

    menu = pystray.Menu(Item("退出", on_quit))
    icon = pystray.Icon("ScreenSwitch", image, "屏幕切换", menu)
    icon.run()


if __name__ == "__main__":
    main()