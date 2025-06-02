from flask import Flask, request
import requests
import base64
import json
import os
from datetime import datetime

app = Flask(__name__)

EVOCON_TENANT = os.environ.get("EVOCON_TENANT")
EVOCON_SECRET = os.environ.get("EVOCON_SECRET")
STATION_ID = int(os.environ.get("EVOCON_STATION_ID", 2))  # You can set this in Railway

def get_auth_header():
    credentials = f"{EVOCON_TENANT}:{EVOCON_SECRET}".encode()
    return base64.b64encode(credentials).decode()

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    text = data.get("text", "")
    print("Webhook text received:", text)

    try:
        # Extract production order ID (last part after last "-")
        production_order_id = text.strip().split("-")[-1].strip()
    except Exception as e:
        return {"error": "Invalid text format", "details": str(e)}, 400

    # Fetch job list for this station
    job_list_url = f"https://api.evocon.com/api/jobs?stationId={STATION_ID}"
    headers = {
        "Authorization": f"Basic {get_auth_header()}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    jobs_response = requests.get(job_list_url, headers=headers)
    jobs = jobs_response.json()

    # Find the job with matching productionOrderId
    job = next((j for j in jobs if str(j.get("productionOrderId")) == production_order_id), None)

    if not job:
        return {"error": f"No job found with productionOrderId {production_order_id}"}, 404

    # Prepare changeover payload
    changeover_payload = {
        "jobId": job["id"],
        "plannedQty": job["plannedQty"],
        "unitQty": job.get("unitQuantity", 1),
        "notes": f"Auto CO for {production_order_id}",
        "unitId": job.get("unitId", "pcs"),
        "eventTimeISO": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+03:00"),
        "lotCode": f"CO-{production_order_id}"
    }

    # Post changeover
    changeover_url = f"https://api.evo_
