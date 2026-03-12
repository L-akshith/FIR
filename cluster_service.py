"""
ArecaMitra Backend — Cluster Service (Spatial Risk Engine)
Detects disease outbreaks and generates concentric PostGIS risk zones.
"""

import math
from weather_service import fetch_weather, get_koleroga_zone_expansion
from supabase_service import (
    get_recent_reports,
    save_risk_zones,
    expire_old_zones,
    get_farmers_to_notify,
)
from notification_service import send_bulk_notification, build_outbreak_alert

# ─── Constants ───
CLUSTER_MIN_REPORTS = 3        # Minimum reports to form a cluster
CLUSTER_RADIUS_KM = 30         # Max distance between reports in a cluster
SEVERE_ZONE_RADIUS_KM = 10     # Inner severe core zone
WARNING_ZONE_RADIUS_KM = 30    # Outer warning zone (before expansion)
EARTH_RADIUS_KM = 6371.0


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
    Find clusters of reports for a specific disease.

    A cluster is 3+ reports within 30 km of each other.
    Uses a simple greedy approach suitable for hackathon MVP.

    Returns list of cluster dicts with center coords, reports, and count.
    """
    if len(reports) < CLUSTER_MIN_REPORTS:
        return []

    used = set()
    clusters = []

    for i, seed in enumerate(reports):
        if i in used:
            continue

        # Find all reports within CLUSTER_RADIUS_KM of this seed
        group_indices = [i]
        for j, other in enumerate(reports):
            if j in used or j == i:
                continue
            dist = haversine(
                seed["latitude"], seed["longitude"],
                other["latitude"], other["longitude"],
            )
            if dist <= CLUSTER_RADIUS_KM:
                group_indices.append(j)

        # Only keep if cluster has enough reports
        if len(group_indices) >= CLUSTER_MIN_REPORTS:
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


def _generate_point_wkt(lat: float, lon: float) -> str:
    """Generate a WKT POINT."""
    return f"SRID=4326;POINT({lon} {lat})"


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

            # Fetch weather at cluster center for zone expansion
            weather = fetch_weather(clat, clon)
            expansion = 1.0
            if disease == "koleroga":
                expansion = get_koleroga_zone_expansion(weather)

            # Severe core zone (10 km)
            zones_to_save.append({
                "disease": disease,
                "risk_level": "severe",
                "boundary": _generate_zone_wkt(clat, clon, SEVERE_ZONE_RADIUS_KM),
                "centroid": _generate_point_wkt(clat, clon),
                "case_count": cluster["case_count"],
                "radius_km": SEVERE_ZONE_RADIUS_KM,
            })

            # Warning zone (30 km, may expand)
            warning_radius = WARNING_ZONE_RADIUS_KM * expansion
            zones_to_save.append({
                "disease": disease,
                "risk_level": "warning",
                "boundary": _generate_zone_wkt(clat, clon, warning_radius),
                "centroid": _generate_point_wkt(clat, clon),
                "case_count": cluster["case_count"],
                "radius_km": round(warning_radius, 1),
            })

            # Send Push Notifications to nearby farmers
            farmers = get_farmers_to_notify(clat, clon, warning_radius)
            if farmers:
                tokens = [f.get("fcm_token") for f in farmers if f.get("fcm_token")]
                if tokens:
                    # Heuristic severity for alert based on expansion
                    alert_severity = "severe" if expansion > 1.0 else "moderate"
                    risk_msg = generate_risk_message(disease, weather)
                    title, body = build_outbreak_alert(disease, alert_severity, risk_msg)
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
