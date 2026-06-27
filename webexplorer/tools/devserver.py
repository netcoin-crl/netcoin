# Dev-only: serve public/ and proxy /api/* -> a NetCoin node (raw IP bypasses the
# ISP domain filter). NOT for production — production uses nginx same-origin relay.
import http.server, socketserver, urllib.request, os
NODE = os.environ.get("NETCOIN_NODE", "http://18.226.74.252:28444")
ROOT = os.path.join(os.path.dirname(__file__), "..", "public")

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def do_GET(self):
        if self.path.startswith("/api/"):
            url = NODE + self.path[4:]
            try:
                with urllib.request.urlopen(url, timeout=8) as r:
                    body = r.read()
                self.send_response(200); self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
            except Exception as e:
                self.send_response(502); self.end_headers(); self.wfile.write(str(e).encode())
            return
        super().do_GET()
    def log_message(self,*a): pass

PORT=8077
socketserver.TCPServer.allow_reuse_address=True
with socketserver.TCPServer(("127.0.0.1",PORT), H) as s:
    print("dev explorer on", PORT, "-> node", NODE); s.serve_forever()
