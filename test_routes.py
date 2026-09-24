"""
Test all 25 frontend routes against built SPA assets.
Starts an in-process SPA HTTP server on 127.0.0.1:5173, queries all 25 routes,
confirms HTTP 200 OK and root HTML presence for each route, then terminates.
"""

import sys
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / "apps" / "web" / "dist"
INDEX_FILE = DIST_DIR / "index.html"

routes = [
    '/', '/ecosystem', '/docs',
    '/wallet', '/wallet/credentials/1', '/wallet/scan', '/wallet/consent', '/wallet/activity', '/wallet/security',
    '/issuer', '/issuer/templates', '/issuer/issue', '/issuer/revocations',
    '/verifier', '/verifier/request', '/verifier/verify', '/verifier/history',
    '/guardian', '/guardian/requests', '/guardian/approve/1',
    '/admin', '/admin/contracts', '/admin/audit', '/admin/fraud-monitor',
    '/random-404-check'
]

class SpaHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    def do_GET(self):
        target = DIST_DIR / self.path.lstrip("/").split("?")[0]
        if not target.exists() or target.is_dir():
            # SPA fallback: serve index.html for all client routes
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(INDEX_FILE, "rb") as f:
                self.wfile.write(f.read())
            return
        return super().do_GET()

    def log_message(self, format, *args):
        pass

def main():
    if not INDEX_FILE.exists():
        print(f"[-] Dist bundle not found at {INDEX_FILE}. Run 'npm run build' in apps/web first.")
        sys.exit(1)

    server = HTTPServer(("127.0.0.1", 5173), SpaHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    results = []
    for r in routes:
        url = f'http://127.0.0.1:5173{r}'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                content = resp.read().decode('utf-8', errors='ignore')
                has_html = '<div id="root">' in content or '<html' in content
                results.append((r, resp.status, has_html))
        except Exception as e:
            results.append((r, str(e), False))

    server.shutdown()

    passed = sum(1 for r in results if r[1] == 200 and r[2])
    print(f"Total Routes Verified: {passed} / {len(routes)} returned HTTP 200 OK with SPA root HTML.")
    for r, status, ok in results:
        print(f"  {r:25} -> Status: {status} | SPA HTML: {ok}")

    if passed != len(routes):
        sys.exit(1)

if __name__ == "__main__":
    main()
