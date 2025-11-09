#!/usr/bin/env python3
"""
Simple HTTP receiver for registry logs.

- Accepts POST to any path and prints the body as UTF-8 text.
- GET /healthz returns 200 for health checks.

Run:
  python recive.py --port 9000 --bind 0.0.0.0

Test:
  curl -X POST http://localhost:9000/v3-logs -H 'Content-Type: application/json' -d '{"hello":"world"}'
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime
import sys


def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_decode(b: bytes) -> str:
    try:
        return b.decode("utf-8", errors="replace")
    except Exception:
        return str(b)


class Receiver(BaseHTTPRequestHandler):
    server_version = "ReciveHTTP/1.0"

    def _send(self, code: int, body: bytes, ctype: str = "text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/healthz"):
            msg = f"receiver ok {ts()}\n"
            self._send(200, msg.encode("utf-8"))
            return
        self._send(404, b"Not Found\n")

    def do_POST(self):  # noqa: N802
        length = 0
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except Exception:
            pass
        body = self.rfile.read(length) if length > 0 else b""
        txt = safe_decode(body).strip()
        peer = self.client_address[0]
        if txt:
            print(f"[{ts()}] HTTP {peer} -> {self.path}")
            print(txt)
            sys.stdout.flush()
        self._send(200, b"OK\n")

    def log_message(self, format: str, *args):  # silence default
        return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9000)
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.bind, args.port), Receiver)
    print(f"[{ts()}] Receiver listening on http://{args.bind}:{args.port}")
    try:
        srv.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        srv.shutdown()
        srv.server_close()


if __name__ == "__main__":
    main()

