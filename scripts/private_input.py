"""Temporary private input; the callback owns authorized use/storage."""
import html
import json
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit


class InputServer(HTTPServer):
    def __init__(self, callback, purpose, host="127.0.0.1", port=0, ttl=600,
                 allow_plain_lan=False, tls_context=None, public_origin=None):
        if host not in ("127.0.0.1", "::1", "localhost"):
            if tls_context is None and not allow_plain_lan:
                raise ValueError("LAN requires TLS or explicit plaintext consent")
            if not public_origin:
                raise ValueError("LAN requires a reachable public_origin")
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        super().__init__((host, port), Handler)
        try:
            if tls_context is not None:
                self.socket = tls_context.wrap_socket(self.socket, server_side=True)
            scheme = "https" if tls_context else "http"
            self.origin = public_origin or f"{scheme}://127.0.0.1:{self.server_port}"
            parsed = urlsplit(self.origin)
            if (parsed.scheme != scheme or not parsed.hostname or parsed.path
                    or parsed.query or parsed.fragment or parsed.username or parsed.password):
                raise ValueError("public_origin must be a bare matching HTTP(S) origin")
            self.host_header = parsed.netloc
            self.route = "/input/" + secrets.token_urlsafe(32)
            self.token = secrets.token_urlsafe(32)
            self.callback = callback
            self.purpose = purpose
            self.deadline = time.monotonic() + ttl
            self.outcome = "waiting"
            self.timeout = 0.25
        except Exception:
            self.server_close()
            raise

    def handle_error(self, request, client_address):
        # Do not send request-processing tracebacks into agent output.
        pass

    @property
    def url(self):
        return self.origin + self.route

    def run(self):
        try:
            while self.outcome == "waiting" and time.monotonic() < self.deadline:
                self.handle_request()
            if self.outcome == "waiting":
                self.outcome = "expired"
            return self.outcome
        finally:
            self.server_close()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)
        # A socket timeout alone resets on each read; enforce an absolute deadline.
        self.deadline_timer = threading.Timer(
            max(0, self.server.deadline - time.monotonic()), self.expire_request)
        self.deadline_timer.daemon = True
        self.deadline_timer.start()

    def expire_request(self):
        try:
            self.connection.shutdown(socket.SHUT_RD)
        except OSError:
            pass

    def finish(self):
        self.deadline_timer.cancel()
        super().finish()

    def log_message(self, *args):
        pass

    def reply(self, status, text, kind="text/plain; charset=utf-8"):
        raw = text.encode("utf-8")
        self.send_response(status)
        for k, v in {"Content-Type": kind, "Content-Length": str(len(raw)),
                     "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                     "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
                     "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'"}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def valid(self):
        s = self.server
        return (self.path == s.route and self.headers.get("Host") == s.host_header
                and s.outcome == "waiting" and time.monotonic() < s.deadline)

    def do_GET(self):
        if not self.valid():
            return self.reply(404, "Not found")
        purpose = html.escape(self.server.purpose)
        token = json.dumps(self.server.token)
        page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>密钥输入</title><style>
body{margin:0;padding:8vh 24px;background:linear-gradient(135deg,#e6f1ec,#faf4e7);color:#163e36;font:18px Georgia,serif}
main{max-width:480px;margin:auto;padding:32px;background:#fffdf7;border:1px solid #b2c9bf;border-radius:18px}
input,button{box-sizing:border-box;width:100%;padding:14px;margin-top:16px;font:inherit;border-radius:8px;border:1px solid #819f92}
button{background:#164f43;color:white}p{line-height:1.6}</style>
<main><small>一次性输入 · 本机处理</small><h1>密钥输入</h1><p>__PURPOSE__</p>
<form id="f"><label for="k">密钥或测试文字</label><input id="k" name="password" type="password" required maxlength="8192" autocomplete="current-password" spellcheck="false">
<button id="b">提交</button></form><p id="s" role="status">内容仅交给本机处理程序，不发送到聊天。若使用 HTTP，传输为明文。</p></main>
<script>const f=document.getElementById('f'),k=document.getElementById('k'),b=document.getElementById('b'),s=document.getElementById('s');
f.onsubmit=async e=>{e.preventDefault();b.disabled=true;let value=k.value;k.value='';try{const r=await fetch(location.pathname,{method:'POST',headers:{'Content-Type':'application/json','X-Input-Token':__TOKEN__},body:JSON.stringify({secret:value})});value='';s.textContent=await r.text();f.hidden=true;}catch{value='';s.textContent='连接已结束，请回到聊天确认任务状态后再试。';f.hidden=true;}};</script></html>'''
        page = page.replace("__TOKEN__", token).replace("__PURPOSE__", purpose)
        self.reply(200, page, "text/html; charset=utf-8")

    def do_POST(self):
        s = self.server
        if (not self.valid() or self.headers.get("Origin") != s.origin
                or not secrets.compare_digest(self.headers.get("X-Input-Token", ""), s.token)):
            return self.reply(403, "请求被拒绝")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                raise ValueError()
            if self.headers.get("Content-Type") != "application/json":
                raise ValueError()
            data = json.loads(self.rfile.read(length))
            value = data["secret"]
            if not isinstance(value, str) or not value or len(value) > 8192:
                raise ValueError()
        except Exception:
            return self.reply(400, "输入格式无效")
        if time.monotonic() >= s.deadline:
            s.outcome = "expired"
            return self.reply(410, "输入页面已过期")
        self.deadline_timer.cancel()
        s.outcome = "processing"
        try:
            s.callback(value)
        except Exception:
            s.outcome = "handler_failed"
            return self.reply(500, "处理失败，请先确认目标状态，不要重复提交。")
        finally:
            value = None
            data = None
        s.outcome = "submitted"
        self.reply(200, "已提交给本机处理程序，请回到聊天继续确认结果。")


def serve(on_submit, purpose, **options):
    server = InputServer(on_submit, purpose, **options)
    print("Private input: " + server.url, flush=True)
    print("Outcome: " + server.run(), flush=True)
