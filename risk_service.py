"""
ArecaMitra Backend — Risk Service
Point-in-polygon risk checks and vendor proximity for farmers.
"""

from supabase_service import check_point_risk, get_nearby_vendors, get_active_risk_zones, get_historical_zones


# ─── Recommendations by risk level and disease ───
RECOMMENDATIONS = {
    ("koleroga", "severe"): (
        "You are inside an active Koleroga outbreak zone. "
        "Immediate Bordeaux mixture spraying is strongly recommended. "
        "Ensure proper drainage around palms."
    ),
    ("koleroga", "warning"): (
        "Koleroga outbreak detected nearby. "
        "Pre-emptive spraying with copper fungicide advised. "
        "Monitor palms for black spots on nuts."
    ),
    ("koleroga", "historical"): (
        "This area has a history of Koleroga outbreaks. "
        "Schedule preventive spraying before monsoon season."
    ),
    ("yellow_leaf", "severe"): (
        "You are inside a Yellow Leaf Disease outbreak zone. "
        "Remove and destroy severely affected palms. "
        "Apply Imidacloprid to control leafhopper vectors."
    ),
    ("yellow_leaf", "warning"): (
        "Yellow Leaf Disease detected nearby. "
        "Monitor for yellowing of lower fronds. "
        "Consider prophylactic insecticide application."
    ),
    ("yellow_leaf", "historical"): (
        "This area has previously experienced Yellow Leaf Disease. "
        "Maintain palm nutrition and watch for leafhopper activity."
    ),
}


def _get_recommendation(disease: str, risk_level: str) -> str:
    """Get contextual recommendation based on disease and risk level."""
    return RECOMMENDATIONS.get(
        (disease, risk_level),
        "Disease activity detected in your area. Consult local agricultural officer.",
    )


def check_farmer_risk(lat: float, lon: float) -> dict:
    """
    Check if a farmer's location falls inside any risk zone
    and find nearby vendors.

    Returns:
        dict with status, disease, distance, recommendation, nearby_vendors, map_layers
    """
    # Step 1: Point-in-polygon risk check via PostGIS
    risk = check_point_risk(lat, lon)

    if risk is None:
        return {
            "status": "safe",
            "disease": None,
            "distance_to_core_km": None,
            "recommendation": "No active disease outbreaks detected near your location.",
            "nearby_vendors": [],
            "map_layers": _build_map_layers(),
        }

    disease = risk.get("disease", "unknown")
    risk_level = risk.get("risk_level", "warning")
    distance_km = round(risk.get("distance_to_core_km", 0), 1)

    # Step 2: Find nearby vendors (only for severe/warning)
    vendors = []
    if risk_level in ("severe", "warning"):
        raw_vendors = get_nearby_vendors(lat, lon, radius_m=20000)
        vendors = [
            {
                "name": v.get("vendor_name", ""),
                "distance_km": round(v.get("distance_km", 0), 1),
                "stock": v.get("products", []),
            }
            for v in raw_vendors
        ]

    # Step 3: Build response
    return {
        "status": risk_level,
        "disease": disease,
        "distance_to_core_km": distance_km,
        "recommendation": _get_recommendation(disease, risk_level),
        "nearby_vendors": vendors,
        "map_layers": _build_map_layers(),
    }


def _build_map_layers() -> dict:
    """
    Build GeoJSON-like map layer references for the frontend.
    Returns zone data categorized by risk level.
    """
    active_zones = get_active_risk_zones()
    historical_zones = get_historical_zones()

    layers = {
        "severe": [],
        "warning": [],
        "historical": [],
    }

    for zone in active_zones:
        level = zone.get("risk_level", "")
        if level in layers:
            layers[level].append({
                "id": zone.get("id"),
                "disease": zone.get("disease"),
                "radius_km": zone.get("radius_km"),
                "case_count": zone.get("case_count"),
                "centroid": zone.get("centroid"),
                "boundary": zone.get("boundary"),
            })

    for hz in historical_zones:
        layers["historical"].append({
            "id": hz.get("id"),
            "disease": hz.get("disease"),
            "district": hz.get("district"),
            "radius_km": hz.get("radius_km"),
            "years": hz.get("years"),
            "centroid": hz.get("centroid"),
        })

    return layers
