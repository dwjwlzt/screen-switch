import importlib
import http.server
import json
import os
import socket
import sys
import urllib.parse

_core = importlib.import_module("screen switch")

# Windows 控制台默认 GBK，启动横幅里的特殊字符会导致编码报错，统一替换为可打印字符
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# 站点图标等静态资源白名单：请求路径 -> (templates 下文件名, Content-Type)
STATIC_FILES = {
    "/favicon.png": ("favicon.png", "image/png"),
    "/favicon.ico": ("favicon.png", "image/png"),
    "/apple-touch-icon.png": ("favicon.png", "image/png"),
}


def _get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class _Handler(http.server.BaseHTTPRequestHandler):
    server_version = "ScreenSwitch/1.0"

    def log_message(self, fmt, *args):
        print(f"[HTTP] {self.address_string()} - {fmt % args}")

    def _send_json(self, data: dict, code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _check_token(self, params: dict) -> bool:
        expected = self.server.auth_token
        if not expected:
            return True
        got = params.get("token", "")
        return got == expected

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        params = {k: v[0] for k, v in params.items()}

        if parsed.path in STATIC_FILES:
            filename, content_type = STATIC_FILES[parsed.path]
            file_path = os.path.join(TEMPLATE_DIR, filename)
            try:
                with open(file_path, "rb") as f:
                    body = f.read()
            except FileNotFoundError:
                self._send_json({"ok": False, "message": "Not Found"}, 404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/":
            html_path = os.path.join(TEMPLATE_DIR, "index.html")
            try:
                with open(html_path, "r", encoding="utf-8") as f:
                    body = f.read().encode("utf-8")
            except FileNotFoundError:
                body = b"<h1>404 - index.html not found</h1>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/status":
            if not self._check_token(params):
                self._send_json({"ok": False, "message": "鉴权失败"}, 401)
                return
            result = _core._execute("status")
            self._send_json(result)
            return

        self._send_json({"ok": False, "message": "Not Found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json({"ok": False, "message": "请求体不是合法 JSON"}, 400)
            return
        if not isinstance(data, dict):
            self._send_json({"ok": False, "message": "请求体必须是 JSON 对象"}, 400)
            return

        if parsed.path == "/api/exec":
            if not self._check_token(data):
                self._send_json({"ok": False, "message": "鉴权失败"}, 401)
                return
            action = data.get("action", "toggle")
            result = _core._execute(action)
            self._send_json(result, 200 if result["ok"] else 400)
            return

        self._send_json({"ok": False, "message": "Not Found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


class _Server(http.server.HTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_cls, auth_token=None):
        super().__init__(server_address, handler_cls)
        self.auth_token = auth_token


def run_server(host="0.0.0.0", port=8765, token=None):
    server = _Server((host, port), _Handler, token)
    lan_ip = _get_lan_ip()
    print("=" * 50)
    print("  显示器控制 Web 服务已启动")
    print("=" * 50)
    print(f"  本机访问:  http://127.0.0.1:{port}")
    print(f"  手机访问:  http://{lan_ip}:{port}")
    if token:
        print(f"  Token:     {token}")
    else:
        print("  ⚠ 未设置 token，局域网内任何人可操作")
    print("  按 Ctrl+C 停止")
    print("=" * 50)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.server_close()


if __name__ == "__main__":
    parts = sys.argv[1:]
    host = "0.0.0.0"
    port = 8765
    token = None
    i = 0
    while i < len(parts):
        p = parts[i]
        if p == "--host" and i + 1 < len(parts):
            host = parts[i + 1]
            i += 2
        elif p == "--port" and i + 1 < len(parts):
            port = int(parts[i + 1])
            i += 2
        elif p == "--token" and i + 1 < len(parts):
            token = parts[i + 1]
            i += 2
        else:
            i += 1
    run_server(host, port, token)