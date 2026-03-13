-- =============================================================
-- ArecaMitra — Supabase Schema Setup
-- Run this in your Supabase SQL Editor
-- =============================================================

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- =============================================================
-- Profile Setup (Tied to Auth via Supabase OTP)
-- =============================================================
CREATE TABLE IF NOT EXISTS farmers (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    phone TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    dob DATE NOT NULL,
    address TEXT NOT NULL,
    pincode TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================
-- 1. disease_reports — Raw farmer submissions
-- =============================================================
CREATE TABLE IF NOT EXISTS disease_reports (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    image_url TEXT,
    disease TEXT NOT NULL,
    confidence FLOAT8,
    severity TEXT,
    crop_stage TEXT,
    latitude FLOAT8 NOT NULL,
    longitude FLOAT8 NOT NULL,
    location GEOGRAPHY(Point, 4326),
    temperature FLOAT8,
    humidity FLOAT8,
    rainfall FLOAT8,
    farmer_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-generate PostGIS location from lat/lon on insert
CREATE OR REPLACE FUNCTION set_report_location()
RETURNS TRIGGER AS $$
BEGIN
    NEW.location := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_report_location ON disease_reports;
CREATE TRIGGER trg_set_report_location
    BEFORE INSERT ON disease_reports
    FOR EACH ROW
    EXECUTE FUNCTION set_report_location();

-- Index for spatial queries
CREATE INDEX IF NOT EXISTS idx_reports_location ON disease_reports USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON disease_reports (created_at);

-- =============================================================
-- 2. risk_zones — Generated concentric outbreak zones
-- =============================================================
CREATE TABLE IF NOT EXISTS risk_zones (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    disease TEXT NOT NULL,
    risk_level TEXT NOT NULL CHECK (risk_level IN (
        'severe', 'warning', 'historical', 'monitor',
        'high_risk', 'moderate_risk', 'least_risk', 'projected_spread'
    )),
    boundary GEOGRAPHY(Polygon, 4326),
    centroid GEOGRAPHY(Point, 4326),
    case_count INT DEFAULT 0,
    radius_km FLOAT8,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours')
);

CREATE INDEX IF NOT EXISTS idx_zones_boundary ON risk_zones USING GIST (boundary);
CREATE INDEX IF NOT EXISTS idx_zones_expires ON risk_zones (expires_at);

-- =============================================================
-- 3. historical_outbreaks — Long-term disease risk areas
-- =============================================================
CREATE TABLE IF NOT EXISTS historical_outbreaks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    district TEXT NOT NULL,
    disease TEXT NOT NULL,
    centroid GEOGRAPHY(Point, 4326),
    radius_km FLOAT8 DEFAULT 25,
    years TEXT[] DEFAULT '{}'
);

-- =============================================================
-- 4. vendors — Agricultural supply stores
-- =============================================================
CREATE TABLE IF NOT EXISTS vendors (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    latitude FLOAT8 NOT NULL,
    longitude FLOAT8 NOT NULL,
    location GEOGRAPHY(Point, 4326),
    products TEXT[] DEFAULT '{}'
);

-- Auto-generate PostGIS location for vendors
CREATE OR REPLACE FUNCTION set_vendor_location()
RETURNS TRIGGER AS $$
BEGIN
    NEW.location := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_vendor_location ON vendors;
CREATE TRIGGER trg_set_vendor_location
    BEFORE INSERT ON vendors
    FOR EACH ROW
    EXECUTE FUNCTION set_vendor_location();

CREATE INDEX IF NOT EXISTS idx_vendors_location ON vendors USING GIST (location);

-- =============================================================
-- 5. fcm_tokens — Firebase device tokens for push notifications
-- =============================================================
CREATE TABLE IF NOT EXISTS fcm_tokens (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    farmer_hash TEXT NOT NULL,
    fcm_token TEXT NOT NULL UNIQUE,
    latitude FLOAT8,
    longitude FLOAT8,
    location GEOGRAPHY(Point, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-generate PostGIS location for fcm_tokens
CREATE OR REPLACE FUNCTION set_token_location()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.location := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
    END IF;
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_token_location ON fcm_tokens;
CREATE TRIGGER trg_set_token_location
    BEFORE INSERT OR UPDATE ON fcm_tokens
    FOR EACH ROW
    EXECUTE FUNCTION set_token_location();

CREATE INDEX IF NOT EXISTS idx_tokens_location ON fcm_tokens USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_tokens_farmer ON fcm_tokens (farmer_hash);

-- =============================================================
-- RPC Functions for spatial queries
-- =============================================================

-- Get reports within a radius (km) from a point, last N days
CREATE OR REPLACE FUNCTION get_nearby_reports(
    p_lat FLOAT8,
    p_lon FLOAT8,
    p_radius_km FLOAT8,
    p_days INT DEFAULT 14
)
RETURNS SETOF disease_reports AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM disease_reports
    WHERE created_at >= NOW() - (p_days || ' days')::INTERVAL
      AND ST_DWithin(
          location,
          ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography,
          p_radius_km * 1000
      );
END;
$$ LANGUAGE plpgsql;

-- Check if a point falls inside any active risk zone
CREATE OR REPLACE FUNCTION check_point_risk(
    p_lat FLOAT8,
    p_lon FLOAT8
)
RETURNS TABLE (
    zone_id UUID,
    disease TEXT,
    risk_level TEXT,
    distance_to_core_km FLOAT8,
    radius_km FLOAT8
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        rz.id AS zone_id,
        rz.disease,
        rz.risk_level,
        ST_Distance(
            rz.centroid,
            ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography
        ) / 1000.0 AS distance_to_core_km,
        rz.radius_km
    FROM risk_zones rz
    WHERE (rz.expires_at IS NULL OR rz.expires_at > NOW())
      AND ST_Intersects(
          rz.boundary,
          ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography
      )
    ORDER BY
        CASE rz.risk_level
            WHEN 'severe' THEN 1
            WHEN 'warning' THEN 2
            ELSE 3
        END
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Get vendors within a radius (meters) from a point
CREATE OR REPLACE FUNCTION get_nearby_vendors(
    p_lat FLOAT8,
    p_lon FLOAT8,
    p_radius_m FLOAT8 DEFAULT 20000
)
RETURNS TABLE (
    vendor_id UUID,
    vendor_name TEXT,
    distance_km FLOAT8,
    products TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        v.id AS vendor_id,
        v.name AS vendor_name,
        ST_Distance(
            v.location,
            ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography
        ) / 1000.0 AS distance_km,
        v.products
    FROM vendors v
    WHERE ST_DWithin(
        v.location,
        ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography,
        p_radius_m
    )
    ORDER BY distance_km;
END;
$$ LANGUAGE plpgsql;

-- Get FCM tokens for farmers near a point (for push notifications)
CREATE OR REPLACE FUNCTION get_tokens_near_point(
    p_lat FLOAT8,
    p_lon FLOAT8,
    p_radius_m FLOAT8 DEFAULT 30000
)
RETURNS TABLE (
    farmer_hash TEXT,
    fcm_token TEXT,
    distance_km FLOAT8
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ft.farmer_hash,
        ft.fcm_token,
        ST_Distance(
            ft.location,
            ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography
        ) / 1000.0 AS distance_km
    FROM fcm_tokens ft
    WHERE ft.location IS NOT NULL
      AND ST_DWithin(
        ft.location,
        ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography,
        p_radius_m
    )
    ORDER BY distance_km;
END;
$$ LANGUAGE plpgsql;
