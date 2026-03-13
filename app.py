"""
ArecaMitra Backend — FastAPI Application
Main server with disease prediction, map data, risk checking, and cluster management.
"""

import os
import uuid
import shutil
from contextlib import asynccontextmanager
from typing import List, Tuple

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
import csv
import math
import shapely.wkb # Added shapely.wkb import

# ─── Pure Python Monotone Chain Convex Hull ───
def compute_convex_hull(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Computes the convex hull of a set of 2D points."""
    points = sorted(set(points))
    if len(points) <= 1:
        return points

    def cross(o: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: List[Tuple[float, float]] = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: List[Tuple[float, float]] = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]

def get_historical_csv_clusters(center_lat: float, center_lon: float, max_radius_km: float):
    """
    Reads the historical CSV, filters by radius from center, groups by taluk, and returns:
      - village_pins: individual village markers within radius
      - taluk_zones: 3-tier concentric zones per taluk (computed from local villages only)
    """
    filepath = "arecanut_historical_dataset.csv"
    if not os.path.exists(filepath):
        return {"village_pins": [], "taluk_zones": []}

    # Group villages by district+taluk
    taluk_groups: dict[str, list] = {}
    village_pins = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    lat = float(row['latitude'])
                    lon = float(row['longitude'])
                    
                    # Filter: Only include villages within the requested map radius
                    dist_to_user = haversine(center_lat, center_lon, lat, lon)
                    if dist_to_user > max_radius_km:
                        continue
                        
                    incidence = float(row.get('disease_incidence', 0))
                    intensity = float(row.get('disease_intensity', 0))
                    district = row.get('district', '')
                    taluk = row.get('taluk', '')
                    village = row.get('village', '')
                    key = f"{district}_{taluk}"

                    taluk_groups.setdefault(key, []).append({
                        "lat": lat, "lon": lon,
                        "incidence": incidence, "intensity": intensity,
                        "district": district, "taluk": taluk, "village": village,
                    })

                    # Determine per-village color from incidence
                    if incidence >= 30:
                        color = "#EF4444"  # red — high
                        sev = "high"
                    elif incidence >= 10:
                        color = "#F97316"  # orange — moderate
                        sev = "moderate"
                    elif incidence > 0:
                        color = "#EAB308"  # yellow — low
                        sev = "low"
                    else:
                        color = "#6B7280"  # grey — none
                        sev = "none"

                    village_pins.append({
                        "id": f"csv-{key}-{village}",
                        "latitude": lat,
                        "longitude": lon,
                        "disease": "Yellow Leaf" if incidence > 0 else "healthy",
                        "confidence": float(f"{incidence:.1f}"),
                        "severity": sev,
                        "color": color,
                        "village": village,
                        "taluk": taluk,
                        "district": district,
                        "incidence": incidence,
                        "intensity": intensity,
                    })
                except (ValueError, KeyError):
                    continue
    except Exception as e:
        print(f"Error reading historical CSV: {e}")
        return {"village_pins": [], "taluk_zones": []}

    # Compute per-taluk concentric zones
    taluk_zones = []
    for key, villages in taluk_groups.items():
        lats = [v["lat"] for v in villages]
        lons = [v["lon"] for v in villages]
        incidences = [v["incidence"] for v in villages]
        intensities = [v["intensity"] for v in villages]

        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        avg_incidence = sum(incidences) / len(incidences)
        avg_intensity = sum(intensities) / len(intensities)
        max_incidence = max(incidences)

        # Compute actual geographic radius from village spread (haversine to farthest)
        max_dist_km = 0.0
        for v in villages:
            d = haversine(center_lat, center_lon, v["lat"], v["lon"])
            if d > max_dist_km:
                max_dist_km = d

        # Clamp between 2 and 15 km
        spread_radius = max(2.0, min(max_dist_km * 1.1, 15.0))

        # Severity classification from average incidence
        if avg_incidence >= 25:
            severity = "high_risk"
        elif avg_incidence >= 10:
            severity = "moderate_risk"
        else:
            severity = "least_risk"

        district = villages[0]["district"]
        taluk = villages[0]["taluk"]
        affected_count = len([v for v in villages if v["incidence"] > 0])

        # Inner circle: 50% of spread radius
        inner_r = float(f"{spread_radius * 0.5:.2f}")
        # Square: 75% of spread radius
        sq_half = float(f"{spread_radius * 0.75:.2f}")
        # Outer circle: full spread radius
        outer_r = float(f"{spread_radius:.2f}")

        taluk_zones.append({
            "id": f"taluk-{key}",
            "taluk": taluk,
            "district": district,
            "center_lat": center_lat,
            "center_lon": center_lon,
            "severity": severity,
            "avg_incidence": float(f"{avg_incidence:.1f}"),
            "avg_intensity": float(f"{avg_intensity:.1f}"),
            "max_incidence": max_incidence,
            "affected_villages": affected_count,
            "total_villages": len(villages),
            "inner_radius_km": inner_r,
            "square_half_km": sq_half,
            "outer_radius_km": outer_r,
        })

    return {"village_pins": village_pins, "taluk_zones": taluk_zones}


def get_historical_yellow_leaf_polygon():
    """Generates the outer convex hull for historical polygon overlay."""
    filepath = "arecanut_historical_dataset.csv"
    if not os.path.exists(filepath):
        return []

    affected_points = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    incidence = float(row.get('disease_incidence', 0))
                    if incidence > 0:
                        lat = float(row['latitude'])
                        lon = float(row['longitude'])
                        affected_points.append((lat, lon))
                except ValueError:
                    continue
    except Exception as e:
        print(f"Error reading historical CSV: {e}")
        return []

    if len(affected_points) < 3:
        return affected_points

    hull = compute_convex_hull(affected_points)
    return [{"lat": p[0], "lng": p[1]} for p in hull]



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
# POST /cluster — Manually Trigger Zone Generation
# =============================================================
@app.post("/cluster")
async def trigger_cluster():
    """Manually trigger the clustering engine to generate/refresh risk zones."""
    try:
        result = run_clustering_engine()
        return {"status": "ok", "summary": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

    live_zones = []
    historical_zones = []

    for zone in active_zones:
        centroid_val = zone.get("centroid")
        boundary_val = zone.get("boundary")
        
        # Decode EWKB Hex if needed
        if centroid_val and isinstance(centroid_val, str) and centroid_val.startswith("010"):
            try:
                centroid_val = shapely.wkb.loads(bytes.fromhex(centroid_val)).wkt
            except Exception:
                pass
                
        if boundary_val and isinstance(boundary_val, str) and boundary_val.startswith("010"):
            try:
                boundary_val = shapely.wkb.loads(bytes.fromhex(boundary_val)).wkt
            except Exception:
                pass

        live_zones.append({
            "id": zone.get("id"),
            "disease": zone.get("disease"),
            "risk_level": zone.get("risk_level"),
            "center_lat": centroid_val,
            "radius_km": zone.get("radius_km"),
            "case_count": zone.get("case_count"),
            "boundary": boundary_val,
        })

    for hz in historical_zones_data:
        hz_centroid = hz.get("centroid")
        if hz_centroid and isinstance(hz_centroid, str) and hz_centroid.startswith("010"):
            try:
                hz_centroid = shapely.wkb.loads(bytes.fromhex(hz_centroid)).wkt
            except Exception:
                pass
                
        historical_zones.append({
            "id": hz.get("id"),
            "disease": hz.get("disease"),
            "district": hz.get("district"),
            "radius_km": hz.get("radius_km"),
            "years": hz.get("years"),
            "centroid": hz_centroid,
        })

    # Read the historical raw dataset and get outer boundary
    historical_polygon = get_historical_yellow_leaf_polygon()

    # Build taluk-level clusters from CSV data scoped to viewport
    csv_clusters = get_historical_csv_clusters(lat, lon, radius)

    # Fetch regional weather for Map Analysis Panel
    weather = fetch_weather(lat, lon)
    wind_data = {
        "speed": weather.get("wind_speed", 0),
        "deg": weather.get("wind_direction", 0),
    }

    return {
        "pins": pins,
        "live_zones": live_zones,
        "historical_zones": historical_zones,
        "historical_polygon": historical_polygon,
        "wind_data": wind_data,
        "csv_village_pins": csv_clusters.get("village_pins", []),
        "csv_taluk_zones": csv_clusters.get("taluk_zones", []),
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
# GET /advisory — Dynamic Home Advisory (Phase 7)
# =============================================================
@app.get("/advisory")
async def get_advisory(lat: float, lon: float):
    """
    Synthesize weather, wind, and local disease density into a rich text explanation.
    """
    from supabase_service import get_recent_reports
    
    # 1. Fetch risk status
    risk = check_farmer_risk(lat, lon)
    
    # 2. Fetch weather
    weather = fetch_weather(lat, lon)
    
    # 3. Fetch recent CNN reports inside 15km
    nearby_reports = get_recent_reports(lat, lon, 15)
    
    status = risk.get("status", "safe")
    disease = risk.get("disease", "unknown")
    
    if len(nearby_reports) == 0:
        return {
            "status": "safe",
            "advisory": (
                f"No immediate threats detected. "
                f"Conditions: {weather.get('temperature')}°C, {weather.get('humidity')}% humidity. "
                f"Continue regular maintenance."
            )
        }
        
    disease_name = "Koleroga" if disease == "koleroga" else "Yellow Leaf" if disease == "yellow_leaf" else (disease or "Unknown").title()
    wind_speed = weather.get("wind_speed", 0)
    humidity = weather.get("humidity", 0)
    
    # Dynamically generate text
    if status in ("severe", "warning"):
        advisory_msg = (
            f"⚠️ The issue may be caused from {disease_name} spreading due to "
            f"{humidity}% humidity and {wind_speed} km/h winds. "
            f"{len(nearby_reports)} recent CNN-verified cases detected nearby. "
            f"Please inspect your crops immediately."
        )
    else:
        advisory_msg = (
            f"A minor presence of {disease_name} was noted historically. "
            f"Current weather ({humidity}% humidity) is being monitored. "
            f"Ensure adequate palm nutrition."
        )

    return {
        "status": status,
        "advisory": advisory_msg,
        "reports_count": len(nearby_reports)
    }

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
