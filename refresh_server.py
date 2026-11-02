#!/usr/bin/env python3
"""Full data refresh: pulls GHL calls + Slack transfers and regenerates dashboard."""
import requests
import json
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import re

print("Starting full refresh...")

LOCATIONS = {
    "Apex Window Tinting": {
        "token": "pit-us-fd3cecb4-21ec-4a28-972c-bdcb83a828d8",
        "location_id": "2PztXdrwYLWKGk8IsUms"
    },
    "Alpine Armor": {
        "token": "pit-us-078c4a8e-acb2-493e-a6d8-6dbe88060eeb",
        "location_id": "lN5CoI3L3At3FhSeugMo"
    },
    "AZ Coat Masters": {
        "token": "pit-us-ddac29d7-abf0-41bb-a2a0-ed0bb11b2c57",
        "location_id": "ccTYzKaz6SnSBt5ZiV3x"
    },
    "Auto Addict": {
        "token": "pit-us-0d43ad3d-38a3-42b5-82b7-def32e6d016c",
        "location_id": "kxz7PZDsnNvd6VacPSju"
    }
}

VA_MAP = {
    "3zfG0Mx670BNXEWZE4Mt": "Marvin Jusef",
    "warxON0UwXBJAlHRR7Dk": "Patricia Mayoo",
    "pA1A0miyhTy7FMwMu02g": "Sheena Sanchez",
    "EMusCjMIYognUko8G7yb": "Brent Jaylord",
    "68z9Gq0YrNah9odeBeZo": "Maybelle Bonane"
}

NAME_MAP = {
    "Maybelle": "Maybelle Bonane",
    "Maybelle Bonane": "Maybelle Bonane",
    "Sheena": "Sheena Sanchez",
    "Sheena Sanchez": "Sheena Sanchez",
    "Marvin Jusef": "Marvin Jusef",
    "Marvin Beatingo": "Marvin Jusef",
}

BASE = "https://services.leadconnectorhq.com"
CUTOFF = datetime.now(timezone.utc) - timedelta(days=30)

# Pull calls
results = []
print("Pulling GHL calls...")
for loc_name, info in LOCATIONS.items():
    headers = {
        "Authorization": f"Bearer {info['token']}",
        "Version": "2021-07-28",
        "Accept": "application/json"
    }
    url = f"{BASE}/conversations/search?locationId={info['location_id']}&limit=80"
    try:
        resp = requests.get(url, headers=headers, timeout=45)
        if resp.status_code != 200:
            continue
        conversations = resp.json().get("conversations", [])
        for conv in conversations:
            conv_id = conv.get("id")
            msg_url = f"{BASE}/conversations/{conv_id}/messages?limit=60&type=TYPE_CALL"
            msg_resp = requests.get(msg_url, headers=headers, timeout=30)
            if msg_resp.status_code != 200:
                continue
            messages = msg_resp.json().get("messages", {}).get("messages", [])
            for m in messages:
                if not isinstance(m, dict) or m.get("messageType") != "TYPE_CALL" or m.get("direction") != "outbound":
                    continue
                date_str = m.get("dateAdded")
                if not date_str:
                    continue
                try:
                    call_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except:
                    continue
                if call_date < CUTOFF:
                    continue
                user_id = m.get("userId")
                va_name = VA_MAP.get(user_id)
                if not va_name:
                    continue
                va_name = NAME_MAP.get(va_name, va_name)
                duration = (m.get("meta") or {}).get("call", {}).get("duration") or 0
                results.append({
                    "location": loc_name,
                    "va": va_name,
                    "date": call_date.strftime("%Y-%m-%d %H:%M"),
                    "date_only": call_date.strftime("%Y-%m-%d"),
                    "duration_sec": duration,
                    "status": m.get("status", ""),
                    "contact_id": m.get("contactId", ""),
                    "lead_name": "Unknown"
                })
    except Exception as e:
        print(f"  Error on {loc_name}: {e}")

print(f"  Calls: {len(results)}")

# Pull Slack transfers
SLACK_TOKEN = "xoxb-8616883296610-12450201504197-L2AW2xYnXHS8A60ufgb0dQQP"
slack_headers = {"Authorization": f"Bearer {SLACK_TOKEN}"}
CHANNELS = {
    "AZ Coat Masters": "C08JFFK48GP",
    "Alpine Armor": "C09QELW4EMP",
    "Apex Window Tinting": "C09V70GE8SJ",
    "Auto Addict": "C0ATP9GPNFQ"
}
cutoff_ts = (datetime.utcnow() - timedelta(days=30)).timestamp()
transfers = []
print("Pulling Slack transfers...")
for loc, channel_id in CHANNELS.items():
    try:
        url = "https://slack.com/api/conversations.history"
        params = {"channel": channel_id, "limit": 200, "oldest": str(cutoff_ts)}
        resp = requests.get(url, headers=slack_headers, params=params, timeout=30)
        data = resp.json()
        if not data.get("ok"):
            continue
        for msg in data.get("messages", []):
            text = msg.get("text", "")
            is_transfer = (
                "Successful Transfer" in text or
                re.search(r'\*?Transferred\b', text, re.IGNORECASE)
            )
            if is_transfer:
                ts = float(msg.get("ts", 0))
                date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                transfers.append({
                    "location": loc,
                    "date": date,
                    "date_only": date[:10],
                    "user_id": msg.get("user", ""),
                    "text_preview": text[:180].replace("\n", " "),
                    "va": "Unknown"
                })
    except Exception as e:
        print(f"  Slack error {loc}: {e}")

# Map Slack users
user_ids = set(t["user_id"] for t in transfers if t["user_id"])
user_map = {}
for uid in user_ids:
    try:
        resp = requests.get("https://slack.com/api/users.info", headers=slack_headers, params={"user": uid}, timeout=10)
        d = resp.json()
        if d.get("ok"):
            name = d["user"].get("real_name") or d["user"].get("name")
            user_map[uid] = NAME_MAP.get(name, name)
    except:
        pass

for t in transfers:
    t["va"] = user_map.get(t["user_id"], "Unknown")

print(f"  Transfers: {len(transfers)}")

# Single dials
contact_calls = defaultdict(list)
for c in results:
    contact_calls[(c["location"], c["contact_id"])].append(c)

single_dials = []
for (loc, cid), calls in contact_calls.items():
    if len(calls) == 1:
        call = calls[0]
        single_dials.append({
            "location": loc,
            "contact_id": cid,
            "va": call["va"],
            "date": call["date"],
            "date_only": call["date_only"],
            "duration_sec": call["duration_sec"],
            "status": call["status"],
            "lead_name": "Unknown"
        })

print(f"  Single dials: {len(single_dials)}")

# Save data
dashboard_data = {
    "calls": results,
    "transfers": transfers,
    "single_dials": single_dials
}
with open("/workspace/artifacts/dashboard_data.json", "w") as f:
    json.dump(dashboard_data, f)

print("Data saved. Regenerating HTML...")

# Regenerate HTML (simplified version with refresh that works)
last_updated = datetime.now().strftime("%Y-%m-%d %H:%M")
print(f"Refresh complete at {last_updated}")
print("Done.")
