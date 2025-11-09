import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class RootToAgentsHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # 이 스크립트가 위치한(reg) 폴더를 정적 루트로 사용
        super().__init__(*args, directory=os.path.dirname(__file__), **kwargs)

    def do_GET(self):
        # /agents 요청을 agents.html로 매핑
        if self.path in ("/agents"):
            self.path = "/agents.html"
        return super().do_GET()


def main():
    # 기본 포트 3000 (환경변수 PORT로 변경 가능)
    port = int(os.environ.get("PORT", "3000"))
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, RootToAgentsHandler)
    print(f"Serving at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
