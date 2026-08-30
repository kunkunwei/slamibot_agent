#!/usr/bin/env python3
import json
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BACKEND = "http://127.0.0.1:5000"
AUDIT_PATH = "/tmp/sherpa-wake-ack-safe-audit-20260828.jsonl"


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _forward(self, method):
        body = None
        if method == "POST":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
        request = urllib.request.Request(
            BACKEND + self.path,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                self._send(response.status, response.read())
        except urllib.error.HTTPError as exc:
            self._send(exc.code, exc.read())
        except Exception as exc:
            payload = json.dumps(
                {"success": False, "msg": "SAFE_PROXY_UPSTREAM_ERROR", "data": {"error": type(exc).__name__}}
            ).encode("utf-8")
            self._send(502, payload)

    def do_GET(self):
        if self.path == "/api/assistant/status" or self.path.startswith("/api/assistant/jobs/"):
            self._forward("GET")
            return
        self._send(404, b'{"success":false,"msg":"NOT_FOUND"}')

    def do_POST(self):
        if self.path == "/api/assistant/speak":
            self._forward("POST")
            return
        if self.path == "/api/assistant/turn":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                payload = {"invalidJson": True}
            with open(AUDIT_PATH, "a", encoding="utf-8") as audit:
                audit.write(json.dumps(payload, ensure_ascii=False) + "\n")
            response = {
                "success": False,
                "msg": "MOCK_ONLY",
                "data": {"route": "mock", "state": "logged", "error": "MOCK_ONLY"},
            }
            self._send(200, json.dumps(response, ensure_ascii=False).encode("utf-8"))
            return
        self._send(404, b'{"success":false,"msg":"NOT_FOUND"}')

    def log_message(self, fmt, *args):
        print("[safe-proxy] " + fmt % args, flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 15000), Handler).serve_forever()
