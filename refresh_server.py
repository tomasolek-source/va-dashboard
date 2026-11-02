#!/usr/bin/env python3
"""
Simple server for the VA Dashboard.
Works locally and on Render.
"""

import json
import os
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/refresh" or self.path.startswith("/refresh?"):
            self.handle_refresh()
        else:
            super().do_GET()

    def handle_refresh(self):
        print("Refresh requested...")
        try:
            result = subprocess.run(
                ["python3", os.path.join(BASE_DIR, "full_refresh.py")],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=BASE_DIR
            )
            if result.returncode == 0:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "message": "Data refreshed"}).encode())
            else:
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": result.stderr[:500]}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())

if __name__ == "__main__":
    os.chdir(BASE_DIR)
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print(f"Dashboard server running on port {PORT}")
    server.serve_forever()
