from flask import Flask, request
import requests
import json
import os
import re
from datetime import datetime
from base64 import b64encode

app = Flask(__name__)

# === ENVIRONMENT VARIABLES ===
EVOCON_TENANT = os.getenv("EVOCON_TENANT")
EVOCON_SECRET = os.getenv("EVOCON_SECRET")

if not EVOCON_TENANT or not EVOCON_SECRET:
    raise RuntimeError("❌ Missing required environment variables: EVOCON_TENANT or EVOCON_SECRET")

TARGET_STATIONS = [3, 4, 5, 6]

def evocon_auth_header():
    token = b64encode(f"{EVOCON_TENANT}:{EVOCON_SECRET}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json"
    }

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        print("\n\n----- Incoming Webhook -----")
        raw_body = request.data
        print(f"Raw body: {raw_body}")

        try:
            data = json.loads(raw_body)
        except Exception as e:
            print(f"⚠️ Failed to parse JSON: {e}")
            return "Bad JSON", 400

        print(f"Parsed JSON: {json.dumps(data, indent=2)}")

        text = data.get("text", "")
        print(f"Webhook text: {text}")

        # Extract station, timestamp, and order using regex
        match = re.search(r'(?P<station>.+)-\s*(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*-\s*(?P<order>.+)', text)
        if not match:
            print("⚠️ Failed to parse input string.")
            return "Bad input format", 400

        station_name = match.group("station").strip()
        event_time_str = match.group("dt").strip()
        production_order = match.group("order").strip()

        print(f"Parsed station: {station_name}")
        print(f"Parsed time: {event_time_str}")
        print(f"Parsed productionOrderId: {production_order}")

        # Convert event time to ISO 8601 format with +03:00
        event_time = datetime.strptime(event_time_str, "%Y-%m-%d %H:%M:%S")
        event_time_iso = event_time.strftime("%Y-%m-%dT%H:%M:%S.000+03:00")

        headers = evocon_auth_header()

        for station_id in TARGET_STATIONS:
            print(f"\n🌀 Checking jobs for stationId {station_id}")
            job_url = f"https://api.evocon.com/api/jobs?stationId={station_id}"
            response = requests.get(job_url, headers=headers)

            if response.status_code != 200:
                print(f"❌ Failed to fetch jobs for station {station_id}: {response.status_code} {response.text}")
                continue

            jobs = response.json()
            print(f"✅ Jobs fetched for station {station_id}")

            # Match job by productionOrder
            job = next((j for j in jobs if str(j.get("orderNumber")) == production_order), None)
            if not job:
                print(f"❌ No job found for productionOrder {production_order} on station {station_id}")
                continue

            payload = {
                "jobId": job["id"],
                "plannedQty": job["plannedQty"],
                "unitQty": 1,
                "notes": f"Auto CO for {production_order}",
                "unitId": job["unitId"],
                "eventTimeISO": event_time_iso,
                "lotCode": f"CO-{production_order}"
            }

            print(f"🌀 Posting changeover to station {station_id}")
            print(json.dumps(payload, indent=2))

            changeover_url = f"https://api.evocon.com/api/batches/{station_id}"
            post_response = requests.post(changeover_url, headers=headers, json=payload)

            if post_response.status_code == 200:
                print(f"✅ Changeover posted successfully to station {station_id}")
            else:
                print(f"❌ Failed to post changeover to station {station_id}: {post_response.status_code} {post_response.text}")

        return "Processed", 200

    except Exception as e:
        print(f"⚠️ Exception: {e}")
        return "Error", 500

if __name__ == '__main__':
    print("✅ Starting Flask app on 0.0.0.0:8080 ...")
    app.run(host='0.0.0.0', port=8080)
