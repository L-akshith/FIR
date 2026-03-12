"""
ArecaMitra Backend — Supabase Service
Handles database operations, image storage, and PostGIS spatial queries via RPC.
"""

import os
import uuid
from datetime import datetime
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET

# ─── Singleton Client ───
_client: Client | None = None


def init_supabase() -> Client:
    """Initialize and return the Supabase client (singleton)."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[Supabase] Client initialized.")
    return _client


def upload_image(file_path: str, filename: str | None = None) -> str:
    """
    Upload an image to Supabase Storage.

    Returns:
        Public URL of the uploaded image.
    """
    client = init_supabase()

    if filename is None:
        ext = os.path.splitext(file_path)[1] or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"

    with open(file_path, "rb") as f:
        file_data = f.read()

    # Upload to storage bucket
    client.storage.from_(SUPABASE_BUCKET).upload(
        path=filename,
        file=file_data,
        file_options={"content-type": "image/jpeg"},
    )

    # Get public URL
    public_url = client.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
    return public_url


def save_report(data: dict) -> dict:
    """
    Insert a disease report into the disease_reports table.

    Args:
        data: dict with keys matching disease_reports columns.

    Returns:
        The inserted row data.
    """
    client = init_supabase()

    row = {
        "image_url": data.get("image_url"),
        "disease": data["disease"],
        "confidence": data.get("confidence"),
        "severity": data.get("severity"),
        "crop_stage": data.get("crop_stage"),
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "temperature": data.get("temperature"),
        "humidity": data.get("humidity"),
        "rainfall": data.get("rainfall"),
        "farmer_hash": data.get("farmer_hash"),
    }

    result = client.table("disease_reports").insert(row).execute()
    return result.data[0] if result.data else row


def get_recent_reports(
    lat: float, lon: float, radius_km: float, days: int = 14
) -> list:
    """
    Fetch disease reports within a radius from the last N days.
    Uses the PostGIS RPC function `get_nearby_reports`.
    """
    client = init_supabase()

    result = client.rpc(
        "get_nearby_reports",
        {"p_lat": lat, "p_lon": lon, "p_radius_km": radius_km, "p_days": days},
    ).execute()

    return result.data or []


def get_active_risk_zones() -> list:
    """Fetch all non-expired risk zones."""
    client = init_supabase()

    result = (
        client.table("risk_zones")
        .select("*")
        .gte("expires_at", datetime.utcnow().isoformat())
        .execute()
    )
    return result.data or []


def get_historical_zones() -> list:
    """Fetch all historical outbreak zones."""
    client = init_supabase()

    result = client.table("historical_outbreaks").select("*").execute()
    return result.data or []


def save_risk_zones(zones: list[dict]) -> list:
    """
    Bulk insert risk zones into the risk_zones table.

    Args:
        zones: list of dicts with disease, risk_level, boundary (WKT),
               centroid (WKT), case_count, radius_km
    """
    client = init_supabase()

    if not zones:
        return []

    result = client.table("risk_zones").insert(zones).execute()
    return result.data or []


def expire_old_zones() -> None:
    """Delete risk zones that have expired."""
    client = init_supabase()

    client.table("risk_zones").delete().lt(
        "expires_at", datetime.utcnow().isoformat()
    ).execute()
    print("[Supabase] Expired old risk zones.")


def check_point_risk(lat: float, lon: float) -> dict | None:
    """
    Check if a farmer's location falls inside any active risk zone.
    Uses the PostGIS RPC function `check_point_risk`.
    """
    client = init_supabase()

    result = client.rpc(
        "check_point_risk", {"p_lat": lat, "p_lon": lon}
    ).execute()

    if result.data:
        return result.data[0]
    return None


def get_nearby_vendors(lat: float, lon: float, radius_m: float = 20000) -> list:
    """
    Find agricultural vendors within a radius.
    Uses the PostGIS RPC function `get_nearby_vendors`.
    """
    client = init_supabase()

    result = client.rpc(
        "get_nearby_vendors",
        {"p_lat": lat, "p_lon": lon, "p_radius_m": radius_m},
    ).execute()

    return result.data or []


def register_fcm_token(farmer_hash: str, fcm_token: str, lat: float | None = None, lon: float | None = None) -> dict:
    """
    Register or update an FCM token for a farmer.
    """
    client = init_supabase()

    # Use upsert based on the fcm_token (which is UNIQUE in schema)
    # Actually, Supabase upsert usually needs a primary key or specific constraint.
    # We will do a match and update if exists, else insert.
    existing = client.table("fcm_tokens").select("*").eq("fcm_token", fcm_token).execute()
    
    row = {
        "farmer_hash": farmer_hash,
        "fcm_token": fcm_token,
    }
    if lat is not None and lon is not None:
        row["latitude"] = lat
        row["longitude"] = lon

    if existing.data:
        result = client.table("fcm_tokens").update(row).eq("fcm_token", fcm_token).execute()
    else:
        result = client.table("fcm_tokens").insert(row).execute()
        
    return result.data[0] if result.data else row


def get_farmers_to_notify(lat: float, lon: float, radius_km: float = 30) -> list:
    """
    Get FCM tokens for farmers within the given radius (in km).
    Uses the PostGIS RPC function `get_tokens_near_point`.
    """
    client = init_supabase()

    result = client.rpc(
        "get_tokens_near_point",
        {"p_lat": lat, "p_lon": lon, "p_radius_m": radius_km * 1000},
    ).execute()

    return result.data or []
