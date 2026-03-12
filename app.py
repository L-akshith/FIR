"""
ArecaMitra Backend — FastAPI Application
Main server with disease prediction, map data, risk checking, and cluster management.
"""

import os
import uuid
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from config import UPLOAD_FOLDER
from ml_model import load_model, predict_disease
from weather_service import fetch_weather, generate_risk_message
from supabase_service import (
    init_supabase,
    upload_image,
    save_report,
    get_recent_reports,
    get_active_risk_zones,
    get_historical_zones,
)
from cluster_service import run_clustering_engine, haversine
from risk_service import check_farmer_risk

# ─── Background Scheduler ───
scheduler = BackgroundScheduler()


def _scheduled_cluster_job():
    """Runs the clustering engine (called every 6 hours)."""
    try:
        run_clustering_engine()
    except Exception as e:
        print(f"[Scheduler] Cluster job error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    print("[App] Starting ArecaMitra backend...")
    load_model()
    init_supabase()

    # Schedule clustering engine every 6 hours
    scheduler.add_job(_scheduled_cluster_job, "interval", hours=6, id="cluster_job")
    scheduler.start()
    print("[App] Scheduler started (clustering every 6 hours).")

    yield

    # Shutdown
    scheduler.shutdown()
    print("[App] Scheduler stopped. Goodbye.")


# ─── App Setup ───
app = FastAPI(
    title="ArecaMitra",
    description="AI-powered crop disease surveillance for arecanut farmers",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "trace": traceback.format_exc()}
    )


# =============================================================
# GET / — Health Check
# =============================================================
@app.get("/")
async def health_check():
    return {"message": "ArecaMitra backend running"}


# =============================================================
# POST /report — Disease Report Submission
# =============================================================
@app.post("/report")
async def submit_report(
    image: UploadFile = File(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    crop_stage: str = Form("unknown"),
    farmer_hash: str = Form("anonymous"),
):
    """
    Receive a farmer's disease report:
    1. Save image → ML prediction → Weather fetch → Risk message
    2. Upload image to Supabase Storage
    3. Save report to database
    4. Return diagnosis result
    """
    # Save uploaded image to temp
    ext = os.path.splitext(image.filename or "image.jpg")[1] or ".jpg"
    temp_filename = f"{uuid.uuid4().hex}{ext}"
    temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

        # Step 1: ML prediction
        prediction = predict_disease(temp_path)

        # Step 2: Fetch weather
        weather = fetch_weather(latitude, longitude)

        # Step 3: Generate risk message
        risk_message = generate_risk_message(prediction["disease"], weather)

        # Step 4: Upload image to Supabase Storage
        try:
            image_url = upload_image(temp_path, temp_filename)
        except Exception as e:
            print(f"[Report] Image upload failed: {e}")
            image_url = None

        # Step 5: Save report to database
        report_data = {
            "image_url": image_url,
            "disease": prediction["disease"],
            "confidence": prediction["confidence"],
            "severity": prediction["severity"],
            "crop_stage": crop_stage,
            "latitude": latitude,
            "longitude": longitude,
            "temperature": weather["temperature"],
            "humidity": weather["humidity"],
            "rainfall": weather["rainfall_total"],
            "farmer_hash": farmer_hash,
        }

        try:
            save_report(report_data)
        except Exception as e:
            print(f"[Report] Database save failed: {e}")

        # Step 6: Return response
        return {
            "disease": prediction["disease"],
            "confidence": prediction["confidence"],
            "severity": prediction["severity"],
            "weather": weather,
            "risk_message": risk_message,
        }

    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


# =============================================================
# GET /map — Map Data (Pins + Zones)
# =============================================================
@app.get("/map")
async def get_map_data(
    lat: float = Query(..., description="Center latitude"),
    lon: float = Query(..., description="Center longitude"),
    radius: float = Query(100, description="Search radius in km"),
):
    """
    Return map pins (individual reports) and risk zones for the frontend map.
    """
    # Fetch recent reports within radius
    reports = get_recent_reports(lat, lon, radius, days=14)

    # Build pins (only for disease reports, not healthy)
    pins = []
    for r in reports:
        disease = r.get("disease", "")
        if disease in ("healthy", "healthy_nut", "healthy_leaf"):
            continue

        color = "red" if disease == "koleroga" else "yellow"
        pins.append({
            "id": r.get("id"),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "disease": disease,
            "confidence": r.get("confidence"),
            "severity": r.get("severity"),
            "color": color,
            "created_at": r.get("created_at"),
        })

    # Fetch zones
    active_zones = get_active_risk_zones()
    historical_zones_data = get_historical_zones()

    live_zones = {
        "severe": [],
        "warning": [],
    }
    
    historical_zones = []

    for zone in active_zones:
        level = zone.get("risk_level", "")
        if level in live_zones:
            live_zones[level].append({
                "id": zone.get("id"),
                "disease": zone.get("disease"),
                "center_lat": zone.get("centroid"),
                "radius_km": zone.get("radius_km"),
                "case_count": zone.get("case_count"),
                "boundary": zone.get("boundary"),
            })

    for hz in historical_zones_data:
        historical_zones.append({
            "id": hz.get("id"),
            "disease": hz.get("disease"),
            "district": hz.get("district"),
            "radius_km": hz.get("radius_km"),
            "years": hz.get("years"),
            "centroid": hz.get("centroid"),
        })

    return {
        "pins": pins,
        "live_zones": live_zones,
        "historical_zones": historical_zones,
    }


# =============================================================
# GET /check-risk — Farmer Risk Detection
# =============================================================
@app.get("/check-risk")
async def check_risk(
    lat: float = Query(..., description="Farmer latitude"),
    lon: float = Query(..., description="Farmer longitude"),
):
    """
    Check if a farmer's location falls inside any active risk zone.
    Returns risk level, recommendation, nearby vendors, and map layers.
    """
    result = check_farmer_risk(lat, lon)
    return result


# =============================================================
# POST /register-device — Register FCM Token
# =============================================================
from pydantic import BaseModel

class DeviceRegistration(BaseModel):
    farmer_hash: str
    fcm_token: str
    latitude: float | None = None
    longitude: float | None = None

@app.post("/register-device")
async def register_device(data: DeviceRegistration):
    """
    Register a farmer's device token for push notifications.
    """
    try:
        from supabase_service import register_fcm_token
        result = register_fcm_token(
            farmer_hash=data.farmer_hash,
            fcm_token=data.fcm_token,
            lat=data.latitude,
            lon=data.longitude,
        )
        return {"message": "Device registered successfully", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


# =============================================================
# POST /admin/refresh-clusters — Manual Cluster Refresh (Demo)
# =============================================================
@app.post("/admin/refresh-clusters")
async def refresh_clusters():
    """
    Manually trigger the clustering engine.
    Useful for hackathon demos instead of waiting 6 hours.
    """
    try:
        summary = run_clustering_engine()
        return {
            "message": "Clustering engine completed",
            **summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")


# =============================================================
# Run with: uvicorn app:app --reload --port 8000
# =============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
