from flask import Flask, request
import requests
import json
from datetime import datetime
import re

app = Flask(__name__)

# === CONFIG ===
STATION_ID = 3
USERNAME = "your_evocon_username"
PASSWORD = "your_evocon_password"

# === UTILS ===
def evocon_auth_header():
    from base64 import b64encode
    token = b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

# === ROUTE ===
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
        match = re.search(r'(?P<station>.+)-\s*(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*-\s*(?P<order>\d+)', text)
        if not match:
            print("⚠️ Failed to parse input string.")
            return "Bad input", 400

        station_name = match.group("station").strip()
        event_time_str = match.group("dt").strip()
        production_order = match.group("order").strip()

        print(f"Parsed station: {station_name}")
        print(f"Parsed time: {event_time_str}")
        print(f"Parsed productionOrderId: {production_order}")

        # Convert event time to ISO 8601 format with +03:00
        event_time = datetime.strptime(event_time_str, "%Y-%m-%d %H:%M:%S")
        event_time_iso = event_time.strftime("%Y-%m-%dT%H:%M:%S.000+03:00")

        # Step 1: Fetch all jobs for the station
        job_url = f"https://api.evocon.com/api/jobs?stationId={STATION_ID}"
        headers = evocon_auth_header()
        response = requests.get(job_url, headers=headers)

        if response.status_code != 200:
            print(f"❌ Failed to fetch jobs: {response.status_code} {response.text}")
            return "Job fetch failed", 500

        jobs = response.json()
        print("Jobs fetched:")
        print(json.dumps(jobs, indent=2))

        # Step 2: Find the job that matches the production order
        matching_job = next((job for job in jobs if job["orderNumber"] == production_order), None)

        if not matching_job:
            print(f"❌ No job found for order number {production_order}")
            return "Job not found", 404

        job_id = matching_job["id"]
        planned_qty = matching_job["plannedQty"]
        unit_qty = 1
        unit_id = matching_job["unitId"]
        notes = f"Auto CO for {production_order}"
        lot_code = f"CO-{production_order}"

        payload = {
            "jobId": job_id,
            "plannedQty": planned_qty,
            "unitQty": unit_qty,
            "notes": notes,
            "unitId": unit_id,
            "eventTimeISO": event_time_iso,
            "lotCode": lot_code
        }

        print("Posting changeover payload:")
        print(json.dumps(payload, indent=2))

        post_url = f"https://api.evocon.com/api/batches/{STATION_ID}"
        post_response = requests.post(post_url, headers={**headers, "Content-Type": "application/json"}, json=payload)

        print(f"Evocon response: {post_response.status_code} {post_response.text}")
        return "OK", 200

    except Exception as e:
        print(f"⚠️ Exception: {e}")
        return "Error", 500

# === MAIN ===
if __name__ == '__main__':
    print("Starting Flask app on 0.0.0.0:8080...")
    app.run(host='0.0.0.0', port=8080)
