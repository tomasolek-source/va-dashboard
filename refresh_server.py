#!/usr/bin/env python3
"""VA Dashboard server with automatic data refresh."""
import os
import json
import requests
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from collections import Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

GHL_BASE = "https://services.leadconnectorhq.com"

LOCATIONS = {
    "Apex Window Tinting": {"token": "pit-us-fd3cecb4-21ec-4a28-972c-bdcb83a828d8", "location_id": "2PztXdrwYLWKGk8IsUms"},
    "Alpine Armor": {"token": "pit-us-078c4a8e-acb2-493e-a6d8-6dbe88060eeb", "location_id": "lN5CoI3L3At3FhSeugMo"},
    "AZ Coat Masters": {"token": "pit-us-ddac29d7-abf0-41bb-a2a0-ed0bb11b2c57", "location_id": "ccTYzKaz6SnSBt5ZiV3x"},
    "Auto Addict": {"token": "pit-us-0d43ad3d-38a3-42b5-82b7-def32e6d016c", "location_id": "kxz7PZDsnNvd6VacPSju"},
    "Owners Pride": {"token": "pit-us-770d24b8-f66c-4d48-b4cc-9fe867b9698e", "location_id": "jICFLxBE3K4nOhpVVKEV"}
}

VA_MAP = {
    "3zfG0Mx670BNXEWZE4Mt": "Marvin Jusef",
    "warxON0UwXBJAlHRR7Dk": "Patricia Mayoo",
    "pA1A0miyhTy7FMwMu02g": "Sheena Sanchez",
    "EMusCjMIYognUko8G7yb": "Brent Jaylord",
    "68z9Gq0YrNah9odeBeZo": "Maybelle Bonane",
    "twAMSrWCLvjTLvwj8v3z": "Rico Martinez",
    "ImtwGtUvCUmumKhKqEZE": "Rachelle Bonane"
}

def pull_calls():
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    calls = []
    for loc_name, info in LOCATIONS.items():
        headers = {"Authorization": f"Bearer {info['token']}", "Version": "2021-07-28", "Accept": "application/json"}
        try:
            url = f"{GHL_BASE}/conversations/search?locationId={info['location_id']}&limit=100"
            resp = requests.get(url, headers=headers, timeout=45)
            if resp.status_code != 200: continue
            for conv in resp.json().get("conversations", []):
                conv_id = conv.get("id")
                msg_url = f"{GHL_BASE}/conversations/{conv_id}/messages?limit=40&type=TYPE_CALL"
                msg_resp = requests.get(msg_url, headers=headers, timeout=30)
                if msg_resp.status_code != 200: continue
                for m in msg_resp.json().get("messages", {}).get("messages", []):
                    if not isinstance(m, dict) or m.get("messageType") != "TYPE_CALL" or m.get("direction") != "outbound": continue
                    date_str = m.get("dateAdded")
                    if not date_str: continue
                    try: call_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    except: continue
                    if call_date < cutoff: continue
                    user_id = m.get("userId") or conv.get("assignedTo")
                    va = VA_MAP.get(user_id, "Unknown")
                    calls.append({"location": loc_name, "va": va, "date": call_date.strftime("%Y-%m-%d %H:%M"), "date_only": call_date.strftime("%Y-%m-%d"), "duration_sec": int(m.get("duration") or m.get("callDuration") or 0), "status": m.get("status") or "completed", "contact_id": conv.get("contactId"), "lead_name": conv.get("contactName") or conv.get("fullName") or "Unknown", "hour": call_date.hour})
        except Exception as e:
            print(f"Error pulling {loc_name}: {e}")
    return calls

def refresh_data():
    print("Refreshing data...")
    calls = pull_calls()
    lead_counts = Counter((c["contact_id"], c["location"]) for c in calls)
    single_dials = [c for c in calls if lead_counts[(c["contact_id"], c["location"])] == 1][:150]
    data = {"calls": calls, "transfers": [], "single_dials": single_dials, "updated": datetime.now().isoformat()}
    with open("dashboard_data.json", "w") as f:
        json.dump(data, f)
    print(f"Refresh complete: {len(calls)} calls")
    return data

def background_refresh():
    while True:
        time.sleep(3600)
        try: refresh_data()
        except Exception as e: print("Background refresh error:", e)

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/refresh":
            try:
                refresh_data()
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
            return
        if self.path in ("/", "/index.html"):
            self.path = "/va_dashboard.html"
        return super().do_GET()

if __name__ == "__main__":
    try: refresh_data()
    except Exception as e: print("Initial refresh failed:", e)
    t = threading.Thread(target=background_refresh, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting server on port {port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
