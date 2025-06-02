from flask import Flask, request
import requests
import base64
import json
import os
from datetime import datetime

app = Flask(__name__)

EVOCON_TENANT = os.environ.get("EVOCON_TENANT")
EVOCON_SECRET = os.environ.get("EVOCON_SECRET")
STATION_ID = int(os.environ.get("EVOCON_STATION_ID", 2))  # Set this in Railway

def get_auth_header():
    credentials = f"{EVOCON_TENANT}:{EVOCON_SECRET}".encode()
    return base64.b64encode(credentials).decode()

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    text = data.get("text", "")
    print("Webhook text received:", text)

    try:
        production_order_id = text.strip().split("-")[-1].strip()
    except Exception as e:
        return {"error": "Invalid text format", "details": str(e)}, 400

    job_list_url = f"https://api.evocon.com/api/jobs?stationId={STATION_ID}"
    headers = {
        "Authorization": f"Basic {get_auth_header()}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    jobs_response = requests.get(job_list_url, headers=headers)
    jobs = jobs_response.json()

    job = next((j for j in jobs if str(j.get("productionOrderId")) == production_order_id), None)

    if not job:
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

    changeover_url = f"https://api.evocon.com/api/batches/{STATION_ID}"
    post_response = requests.post(changeover_url, headers=headers, json=changeover_payload)

    return {
        "posted_changeover": changeover_payload,
        "evocon_response": post_response.text,
        "status": post_response.status_code
    }, post_response.status_code
