"""
ArecaMitra Backend — Cluster Service (Spatial Risk Engine)
Detects disease outbreaks and generates concentric PostGIS risk zones.
"""

import math
from weather_service import fetch_weather, get_koleroga_zone_expansion, generate_risk_message
from supabase_service import (
    get_recent_reports,
    save_risk_zones,
    expire_old_zones,
    get_farmers_to_notify,
)
from notification_service import send_bulk_notification, build_outbreak_alert, send_sms_alerts_for_zone

# ─── Constants (Spatial Intelligence System) ───
EARTH_RADIUS_KM = 6371.0

# Classification Radii (km)
RADIUS_MONITOR = 5.0          # 1 Case
RADIUS_EARLY_WARNING = 8.0    # 2 Cases
RADIUS_OUTBREAK_CORE = 15.0   # 3+ Cases

CLUSTER_GROUPING_DISTANCE = 30.0 # Distance to group points into a cluster


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in km."""
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return EARTH_RADIUS_KM * c


def _find_clusters(reports: list, disease: str) -> list[dict]:
    """
    Groups reports within 30km into clusters. (Simplified DBSCAN for Hackathon)
    """
    if not reports:
        return []

    used = set()
    clusters = []

    for i, seed in enumerate(reports):
        if i in used:
            continue

        # Find all reports within CLUSTER_GROUPING_DISTANCE of this seed
        group_indices = [i]
        for j, other in enumerate(reports):
            if j in used or j == i:
                continue
            dist = haversine(
                seed["latitude"], seed["longitude"],
                other["latitude"], other["longitude"],
            )
            if dist <= CLUSTER_GROUPING_DISTANCE:
                group_indices.append(j)

        # Form a cluster (even size 1 is a monitor cluster now)
        group = [reports[idx] for idx in group_indices]
        for idx in group_indices:
            used.add(idx)

        # Compute centroid
        center_lat = sum(r["latitude"] for r in group) / len(group)
        center_lon = sum(r["longitude"] for r in group) / len(group)

        clusters.append({
            "disease": disease,
            "center_lat": round(center_lat, 6),
            "center_lon": round(center_lon, 6),
            "case_count": len(group),
            "reports": group,
        })

    return clusters


def _generate_zone_wkt(center_lat: float, center_lon: float, radius_km: float, num_points: int = 64) -> str:
    """
    Generate a WKT POLYGON approximating a circle.
    Used for PostGIS boundary column.
    """
    points = []
    for i in range(num_points + 1):
        angle = math.radians(360.0 * i / num_points)
        # Approximate offset in degrees
        dlat = (radius_km / EARTH_RADIUS_KM) * math.degrees(1) * math.cos(angle)
        dlon = (radius_km / (EARTH_RADIUS_KM * math.cos(math.radians(center_lat)))) * math.degrees(1) * math.sin(angle)
        points.append(f"{round(center_lon + dlon, 8)} {round(center_lat + dlat, 8)}")

    return f"SRID=4326;POLYGON(({', '.join(points)}))"


def _generate_directional_zone_wkt(center_lat: float, center_lon: float, core_radius: float, expansion: float, wind_deg: float, num_points: int = 64) -> str:
    """
    Generate an elongated WKT POLYGON pointing in the direction of the wind.
    """
    # Wind blows FROM wind_deg, so spread is TOWARDS (wind_deg + 180) % 360
    spread_deg = (wind_deg + 180) % 360
    spread_rad = math.radians(spread_deg)
    
    points = []
    for i in range(num_points + 1):
        angle = math.radians(360.0 * i / num_points)
        
        # Add a directional lobe on the downwind side
        extra_radius = expansion * max(0, math.cos(angle - spread_rad))
        r = core_radius + extra_radius
        
        dlat = (r / EARTH_RADIUS_KM) * math.degrees(1) * math.cos(angle)
        dlon = (r / (EARTH_RADIUS_KM * math.cos(math.radians(center_lat)))) * math.degrees(1) * math.sin(angle)
        points.append(f"{round(center_lon + dlon, 8)} {round(center_lat + dlat, 8)}")

    return f"SRID=4326;POLYGON(({', '.join(points)}))"


def _generate_point_wkt(lat: float, lon: float) -> str:
    """Generate a WKT POINT."""
    return f"SRID=4326;POINT({lon} {lat})"


def _generate_square_wkt(center_lat: float, center_lon: float, half_side_km: float) -> str:
    """
    Generate a WKT POLYGON representing a square (rotated 45°).
    half_side_km is the distance from center to each corner (circumradius).
    To inscribe a square within an outer circle of 4km radius, use half_side_km = 4 / sqrt(2) ≈ 2.828 km.
    """
    lat_deg_per_km = math.degrees(1.0 / EARTH_RADIUS_KM)
    lon_deg_per_km = math.degrees(1.0 / (EARTH_RADIUS_KM * math.cos(math.radians(center_lat))))

    dlat = half_side_km * lat_deg_per_km
    dlon = half_side_km * lon_deg_per_km

    # Four corners of a square aligned to N/S/E/W
    corners = [
        (center_lon - dlon, center_lat + dlat),  # NW
        (center_lon + dlon, center_lat + dlat),  # NE
        (center_lon + dlon, center_lat - dlat),  # SE
        (center_lon - dlon, center_lat - dlat),  # SW
        (center_lon - dlon, center_lat + dlat),  # Close ring
    ]
    pts = [f"{round(lon, 8)} {round(lat, 8)}" for lon, lat in corners]
    return f"SRID=4326;POLYGON(({', '.join(pts)}))"


def run_clustering_engine() -> dict:
    """
    Main clustering engine entry point.

    1. Expire old zones
    2. Fetch recent reports (14 days, confidence > 0.6)
    3. Group by disease
    4. Find clusters
    5. Generate concentric zones (severe + warning)
    6. Save to risk_zones table

    Returns summary of zones created.
    """
    print("[Cluster] Running clustering engine...")

    # Step 1: Clean up expired zones
    expire_old_zones()

    # Step 2: Fetch recent reports — use a central Karnataka point with large radius
    # to get all reports across the state
    all_reports = get_recent_reports(
        lat=13.5, lon=75.5, radius_km=500, days=14
    )

    # Filter by confidence
    valid_reports = [r for r in all_reports if (r.get("confidence") or 0) > 0.6]

    # Step 3: Group by disease (exclude healthy)
    disease_groups: dict[str, list] = {}
    for report in valid_reports:
        disease = report.get("disease", "")
        if disease in ("healthy", "healthy_nut", "healthy_leaf"):
            continue
        disease_groups.setdefault(disease, []).append(report)

    # Step 4 & 5: Find clusters and generate zones
    zones_to_save = []
    total_clusters = 0

    for disease, reports in disease_groups.items():
        clusters = _find_clusters(reports, disease)
        total_clusters += len(clusters)

        for cluster in clusters:
            clat = cluster["center_lat"]
            clon = cluster["center_lon"]
            count = cluster["case_count"]

            # Fetch weather at cluster center for notifications
            weather = fetch_weather(clat, clon)

            # ── 3-Tier Concentric Boundaries ──────────────────────────────
            # Tier 1: HIGH RISK — inner solid red circle (2 km)
            RADIUS_HIGH    = 2.0
            # Tier 2: MODERATE RISK — orange square (inscribed in 4km outer, so halfside ≈ 2.828 km)
            SQUARE_HALF    = 4.0 / math.sqrt(2)   # ≈ 2.828 km
            # Tier 3: LEAST AFFECTED — outer dashed yellow circle (4 km)
            RADIUS_LEAST   = 4.0

            zones_to_save.append({
                "disease": disease,
                "risk_level": "high_risk",
                "boundary": _generate_zone_wkt(clat, clon, RADIUS_HIGH),
                "centroid": _generate_point_wkt(clat, clon),
                "case_count": count,
                "radius_km": RADIUS_HIGH,
            })
            zones_to_save.append({
                "disease": disease,
                "risk_level": "moderate_risk",
                "boundary": _generate_square_wkt(clat, clon, SQUARE_HALF),
                "centroid": _generate_point_wkt(clat, clon),
                "case_count": count,
                "radius_km": SQUARE_HALF,
            })
            zones_to_save.append({
                "disease": disease,
                "risk_level": "least_risk",
                "boundary": _generate_zone_wkt(clat, clon, RADIUS_LEAST),
                "centroid": _generate_point_wkt(clat, clon),
                "case_count": count,
                "radius_km": RADIUS_LEAST,
            })

            # Wind-directed projected spread (keep for analysis panel)
            expansion = 0.0
            
            # --- PHASE 7: DISPATCH SMS ALERTS FOR NEW CLUSTER ---
            send_sms_alerts_for_zone(
                lat=clat, 
                lon=clon, 
                radius_km=SQUARE_HALF, 
                disease=disease, 
                risk_level="high_risk"
            )

            if disease == "koleroga":
                rainfall = weather.get("rainfall_total", 0)
                humidity = weather.get("humidity", 0)
                if rainfall > 80 and humidity > 85:
                    expansion = min(rainfall / 8.0, 30.0)
            elif disease == "yellow_leaf":
                temp = weather.get("temperature", 0)
                if 25 <= temp <= 32:
                    expansion = 10.0

            if expansion > 0:
                wind_deg = weather.get("wind_direction", 0)
                directional_boundary = _generate_directional_zone_wkt(clat, clon, RADIUS_HIGH, expansion, wind_deg)
                zones_to_save.append({
                    "disease": disease,
                    "risk_level": "projected_spread",
                    "boundary": directional_boundary,
                    "centroid": _generate_point_wkt(clat, clon),
                    "case_count": count,
                    "radius_km": round(RADIUS_HIGH + expansion, 1),
                })

            # Push Notifications to nearby farmers
            farmers = get_farmers_to_notify(clat, clon, RADIUS_LEAST)
            if farmers:
                tokens = [f.get("fcm_token") for f in farmers if f.get("fcm_token")]
                if tokens:
                    risk_msg = generate_risk_message(disease, weather)
                    title, body = build_outbreak_alert(disease, "severe", risk_msg)
                    send_bulk_notification(tokens, title, body)

    # Step 6: Save zones
    if zones_to_save:
        save_risk_zones(zones_to_save)

    summary = {
        "clusters_found": total_clusters,
        "zones_created": len(zones_to_save),
    }
    print(f"[Cluster] Done. {summary}")
    return summary
