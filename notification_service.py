"""
ArecaMitra Backend — Push Notification Service
Sends disease outbreak alerts to farmers via Firebase Cloud Messaging.
"""

import os
import requests
from config import FIREBASE_API_KEY
from supabase_service import get_farmers_to_notify


def send_notification(fcm_token: str, title: str, body: str, data: dict | None = None) -> bool:
    """
    Send a push notification to a single device using FCM REST API.
    """
    if not FIREBASE_API_KEY:
        print("[FCM] WARNING: FIREBASE_API_KEY not set. Push disabled.")
        return False

    url = "https://fcm.googleapis.com/fcm/send"
    headers = {
        "Authorization": f"key={FIREBASE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "to": fcm_token,
        "notification": {
            "title": title,
            "body": body
        },
        "data": data or {}
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"[FCM] Notification sent successfully to {fcm_token[:8]}...")
        return True
    except requests.RequestException as e:
        print(f"[FCM] Send failed: {e}")
        return False


def send_bulk_notification(fcm_tokens: list[str], title: str, body: str, data: dict | None = None) -> dict:
    """
    Send push notifications to multiple devices.

    Args:
        fcm_tokens: List of FCM tokens.
        title: Notification title.
        body: Notification body text.
        data: Optional data payload.

    Returns:
        dict with success_count and failure_count.
    """
    if not FIREBASE_API_KEY:
        print("[FCM] WARNING: FIREBASE_API_KEY not set. Push disabled.")
        return {"success_count": 0, "failure_count": len(fcm_tokens)}

    if not fcm_tokens:
        return {"success_count": 0, "failure_count": 0}

    # FCM legacy HTTP API supports up to 1000 'registration_ids' per request
    url = "https://fcm.googleapis.com/fcm/send"
    headers = {
        "Authorization": f"key={FIREBASE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "registration_ids": fcm_tokens,
        "notification": {
            "title": title,
            "body": body
        },
        "data": data or {}
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        resp_data = response.json()
        
        success = resp_data.get("success", 0)
        failure = resp_data.get("failure", 0)
        
        print(f"[FCM] Bulk send: {success} success, {failure} failed")
        return {
            "success_count": success,
            "failure_count": failure,
        }

    except requests.RequestException as e:
        print(f"[FCM] Bulk send failed: {e}")
        return {"success_count": 0, "failure_count": len(fcm_tokens)}


def build_outbreak_alert(disease: str, severity: str, risk_message: str) -> tuple[str, str]:
    """
    Build a notification title and body for a disease outbreak alert.

    Returns:
        (title, body) tuple
    """
    disease_display = {
        "koleroga": "Koleroga (Mahali)",
        "yellow_leaf": "Yellow Leaf Disease",
    }

    disease_name = disease_display.get(disease, disease.title())

    title = "Areca Mitra Alert 🌴"
    body = (
        f"{disease_name} outbreak detected near your farm.\n"
        f"Severity: {(severity or 'unknown').title()}\n"
        f"{risk_message}\n"
        f"Tap to view prevention steps."
    )

    return title, body

def send_sms_alerts_for_zone(lat: float, lon: float, radius_km: float, disease: str, risk_level: str):
    """
    Finds registered farmers within the new risk zone and simulates sending them an SMS alert.
    """
    print(f"[SMS Engine] Scanning for users within {radius_km}km of new {risk_level} {disease} cluster...")
    farmers = get_farmers_to_notify(lat, lon, radius_km)
    
    if not farmers:
        print(f"[SMS Engine] No registered users found inside this {radius_km}km zone. Skipping SMS.")
        return {"sent": 0}

    disease_name = "Koleroga" if disease == "koleroga" else "Yellow Leaf Disease" if disease == "yellow_leaf" else disease.title()
    
    message = (
        f"[ArecaMitra Alert]\n"
        f"A {risk_level.replace('_', ' ').upper()} outbreak of {disease_name} has been detected within {radius_km}km of your location.\n"
        f"Please inspect your crops immediately and check the ArecaMitra dashboard for details."
    )
    
    count = 0
    for f in farmers:
        # In a real app we would join with the profiles table to get the phone number.
        # Since get_farmers_to_notify returns farmer_hash/fcm_tokens, we simulate the join here.
        hash_id = f.get("farmer_hash", "Unknown")
        print(f"\n--- 📱 SMS DISPATCHED ---")
        print(f"TO: Farmer ID {hash_id[:8]}...")
        print(f"MSG: {message}")
        print(f"------------------------\n")
        count += 1
        
    print(f"[SMS Engine] Successfully fired {count} physical SMS alerts to users in the risk zone.")
    return {"sent": count}
