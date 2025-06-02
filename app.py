
from flask import Flask, request
import requests
import base64
import json
import os

app = Flask(__name__)

EVOCON_TENANT = os.environ.get("EVOCON_TENANT")
EVOCON_SECRET = os.environ.get("EVOCON_SECRET")

def get_auth_header():
    credentials = f"{EVOCON_TENANT}:{EVOCON_SECRET}".encode()
    return base64.b64encode(credentials).decode()

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("Received webhook:", data)

    payload = {
        "stationId": data.get("stationId", 2),
        "eventId": data.get("eventId", "custom_event_1"),
        "eventTime": data.get("timestamp"),
        "eventNote": data.get("note", "Webhook-triggered event")
    }

    headers = {
        "Authorization": f"Basic {get_auth_header()}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        "https://api.evocon.com/api/import/events",
        headers=headers,
        data=json.dumps(payload)
    )

    return {"evocon_status": response.status_code, "evocon_response": response.text}
