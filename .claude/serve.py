"""로컬 검증용 정적 서버. 포트는 PORT 환경변수로 받는다."""
import os
import functools
import http.server
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("PORT", "8731"))

handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                            directory=str(ROOT))
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
    print(f"serving {ROOT} at http://127.0.0.1:{PORT}", flush=True)
    httpd.serve_forever()
