from flask import Flask, request
import requests
import base64
import json
import os
from datetime import datetime
from dateutil import parser
import pytz

app = Flask(__name__)

# Load environment variables
EVOCON_TENANT = os.environ.get("EVOCON_TENANT")
EVOCON_SECRET = os.environ.get("EVOCON_SECRET")
STATION_ID = os.environ.get("EVOCON_STATION_ID")

if not all([EVOCON_TENANT, EVOCON_SECRET, STATION_ID]):
    raise RuntimeError("Missing one or more required environment variables.")

STATION_ID = int(STATION_ID)

def get_auth_header():
    credentials = f"{EVOCON_TENANT}:{EVOCON_SECRET}".encode()
    return base64.b64encode(credentials).decode()

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        print("\n----- Incoming Webhook -----")
        print("Raw body:", request.data)
        print("Headers:", dict(request.headers))

        data = request.get_json(force=True, silent=True)
        if not data:
            return {"error": "Invalid or empty JSON"}, 400

        print("Parsed JSON:", json.dumps(data, indent=2))
        text = data.get("text", "")
        print("Webhook text:", text)

        # Parse from format: "TecnoPack2 - 2025-06-03 00:38:59 - 2100878"
        try:
            parts = text.strip().split("-")
            if len(parts) < 3:
                raise ValueError("Expected format: StationName - Timestamp - OrderNumber")

            event_time_str = parts[1].strip()
            production_order_id = parts[2].strip()

            local_tz = pytz.timezone("Europe/Athens")
            event_time_naive = parser.parse(event_time_str)
            event_time = local_tz.localize(event_time_naive)
            eventTimeISO = event_time.strftime("%Y-%m-%dT%H:%M:%S.000%z")
            eventTimeISO = eventTimeISO[:-2] + ":" + eventTimeISO[-2:]

            print("Parsed time:", eventTimeISO)
            print("Parsed productionOrderId:", production_order_id)

        except Exception as e:
            return {"error": "Failed to parse webhook text", "details": str(e)}, 400

        # Fetch job list from EVOCON
        job_list_url = f"https://api.evocon.com/api/jobs?stationId={STATION_ID}"
        headers = {
            "Authorization": f"Basic {get_auth_header()}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        jobs_response = requests.get(job_list_url, headers=headers)
        jobs = jobs_response.json()
        print("Jobs fetched:", json.dumps(jobs, indent=2))

        job = next((j for j in jobs if str(j.get("productionOrder")) == production_order_id), None)

        if not job:
            return {"error": f"No job found with productionOrder {production_order_id}"}, 404

        print("DEBUG - stationId:", STATION_ID)
        print("DEBUG - jobId:", job["id"])
        print("DEBUG - eventTimeISO:", eventTimeISO)
        print("DEBUG - unitId:", job.get("unitId", "pcs"))

        changeover_payload = {
            "jobId": job["id"],
            "plannedQty": job["plannedQty"],
            "unitQty": job.get("unitQuantity", 1),
            "notes": f"Auto CO for {production_order_id}",
            "unitId": job.get("unitId", "pcs"),
            "eventTimeISO": eventTimeISO,
            "lotCode": f"CO-{production_order_id}"
        }

        print("Posting changeover payload:", json.dumps(changeover_payload, indent=2))

        changeover_url = f"https://api.evocon.com/api/batches/{STATION_ID}"
        post_response = requests.post(changeover_url, headers=headers, json=changeover_payload)

        print("Evocon status code:", post_response.status_code)
        print("Evocon full response:", post_response.text)

        return {
            "posted_changeover": changeover_payload,
            "evocon_response": post_response.text,
            "status": post_response.status_code
        }, post_response.status_code

    except Exception as err:
        print("Unhandled error:", str(err))
        return {"error": "Internal server error", "details": str(err)}, 500

if __name__ == "__main__":
    print("Starting Flask app on 0.0.0.0:8080...")
    app.run(host="0.0.0.0", port=8080)
