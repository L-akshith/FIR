"""
ArecaMitra Backend — Push Notification Service
Sends disease outbreak alerts to farmers via Firebase Cloud Messaging.
"""

import requests
from config import FIREBASE_API_KEY

def send_notification(fcm_token: str, title: str, body: str, data: dict | None = None) -> bool:
    """Initialize Firebase Admin SDK (singleton)."""
    global _firebase_initialized
    if _firebase_initialized:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials

        if not os.path.exists(FIREBASE_CREDENTIALS_PATH):
            print(
                f"[FCM] WARNING: Firebase credentials file not found at "
                f"'{FIREBASE_CREDENTIALS_PATH}'. Push notifications disabled."
            )
            return False

        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred, {"projectId": FIREBASE_PROJECT_ID})
        _firebase_initialized = True
        print("[FCM] Firebase Admin SDK initialized.")
        return True

    except Exception as e:
        print(f"[FCM] Firebase init failed: {e}")
        return False


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
