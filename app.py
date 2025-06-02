
from flask import Flask, request
import requests
import base64
import json
import os
from datetime import datetime

app = Flask(__name__)

# Load and validate environment variables
EVOCON_TENANT = os.environ.get("EVOCON_TENANT")
EVOCON_SECRET = os.environ.get("EVOCON_SECRET")
STATION_ID = os.environ.get("EVOCON_STATION_ID")

if not all([EVOCON_TENANT, EVOCON_SECRET, STATION_ID]):
    raise RuntimeError("Missing one or more required environment variables: EVOCON_TENANT, EVOCON_SECRET, EVOCON_STATION_ID")

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
            print("No JSON received")
            return {"error": "Invalid or empty JSON"}, 400

        print("Parsed JSON:", json.dumps(data, indent=2))
        text = data.get("text", "")
        print("Webhook text:", text)

        try:
            production_order_id = text.strip().split("-")[-1].strip()
        except Exception as e:
            return {"error": "Invalid text format", "details": str(e)}, 400

        # Fetch jobs
        job_list_url = f"https://api.evocon.com/api/jobs?stationId={STATION_ID}"
        headers = {
            "Authorization": f"Basic {get_auth_header()}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        jobs_response = requests.get(job_list_url, headers=headers)
        jobs = jobs_response.json()
        print("Jobs fetched:", json.dumps(jobs, indent=2))

        job = next((j for j in jobs if str(j.get("productionOrderId")) == production_order_id), None)

        if not job:
            print(f"No job found for productionOrderId: {production_order_id}")
            return {"error": f"No job found with productionOrderId {production_order_id}"}, 404

        changeover_payload = {
            "jobId": job["id"],
            "plannedQty": job["plannedQty"],
            "unitQty": job.get("unitQuantity", 1),
            "notes": f"Auto CO for {production_order_id}",
            "unitId": job.get("unitId", "pcs"),
            "eventTimeISO": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+03:00"),
            "lotCode": f"CO-{production_order_id}"
        }

        print("Posting changeover payload:", json.dumps(changeover_payload, indent=2))

        changeover_url = f"https://api.evocon.com/api/batches/{STATION_ID}"
        post_response = requests.post(changeover_url, headers=headers, json=changeover_payload)

        print("Evocon response:", post_response.status_code, post_response.text)

        return {
            "posted_changeover": changeover_payload,
            "evocon_response": post_response.text,
            "status": post_response.status_code
        }, post_response.status_code

    except Exception as err:
        print("Unhandled error:", str(err))
        return {"error": "Internal server error", "details": str(err)}, 500

# Required for Railway hosting (bind to 0.0.0.0 and port 8080)
if __name__ == "__main__":
    print("Starting Flask app on 0.0.0.0:8080...")
    app.run(host="0.0.0.0", port=8080)
