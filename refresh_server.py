#!/usr/bin/env python3
"""
Simple local server for the VA Dashboard.
- Serves the dashboard
- /refresh endpoint re-pulls data and regenerates the HTML
"""

import json
import os
import subprocess
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

PORT = 8080
BASE_DIR = "/workspace/artifacts"

class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/refresh":
            self.handle_refresh()
        else:
            super().do_GET()

    def handle_refresh(self):
        print("Refresh requested...")
        try:
            # Run the data refresh script
            result = subprocess.run(
                ["python3", "/workspace/artifacts/full_refresh.py"],
                capture_output=True,
                text=True,
                timeout=300
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
    print(f"Dashboard server running at http://localhost:{PORT}/va_dashboard.html")
    print("Press Ctrl+C to stop")
    server.serve_forever()
