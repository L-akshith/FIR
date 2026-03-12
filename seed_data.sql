-- =============================================================
-- ArecaMitra — Seed Data for Hackathon Demo
-- Run this AFTER supabase_schema.sql
-- =============================================================

-- =============================================================
-- Historical Outbreaks — Known Koleroga/YLD-prone districts
-- =============================================================
INSERT INTO historical_outbreaks (district, disease, centroid, radius_km, years) VALUES
    ('Shivamogga', 'koleroga', ST_SetSRID(ST_MakePoint(75.5681, 13.9299), 4326)::geography, 30, ARRAY['2020', '2021', '2022', '2023']),
    ('Uttara Kannada', 'koleroga', ST_SetSRID(ST_MakePoint(74.7421, 14.7937), 4326)::geography, 35, ARRAY['2019', '2021', '2023']),
    ('Dakshina Kannada', 'koleroga', ST_SetSRID(ST_MakePoint(75.0421, 12.8438), 4326)::geography, 25, ARRAY['2020', '2022']),
    ('Chikmagalur', 'koleroga', ST_SetSRID(ST_MakePoint(75.7747, 13.3161), 4326)::geography, 20, ARRAY['2021', '2023']),
    ('Hassan', 'yellow_leaf', ST_SetSRID(ST_MakePoint(76.0996, 13.0073), 4326)::geography, 25, ARRAY['2019', '2020', '2022']),
    ('Tumkur', 'yellow_leaf', ST_SetSRID(ST_MakePoint(77.1010, 13.3379), 4326)::geography, 20, ARRAY['2021', '2023']),
    ('Mysuru', 'yellow_leaf', ST_SetSRID(ST_MakePoint(76.6394, 12.2958), 4326)::geography, 25, ARRAY['2020', '2022', '2023']);

-- =============================================================
-- Mock Vendors — Agricultural supply stores in Karnataka
-- =============================================================
INSERT INTO vendors (name, latitude, longitude, products) VALUES
    ('Sagara Agri Store', 14.1667, 75.0333, ARRAY['Bordeaux Mixture', 'Copper Oxychloride', 'Mancozeb']),
    ('KrishiMitra Supplies, Shivamogga', 13.9299, 75.5681, ARRAY['Bordeaux Mixture', 'Imidacloprid', 'Neem Oil']),
    ('Areca Farmers Co-op, Siddapura', 14.3483, 74.8935, ARRAY['Copper Oxychloride', 'Bordeaux Mixture']),
    ('Malnad Agri Center, Chikmagalur', 13.3161, 75.7747, ARRAY['Mancozeb', 'Imidacloprid', 'Bordeaux Mixture']),
    ('Green Valley Pesticides, Mangaluru', 12.9141, 74.8560, ARRAY['Bordeaux Mixture', 'Copper Oxychloride', 'Carbendazim']),
    ('Sahyadri Seeds & Chemicals, Hassan', 13.0073, 76.0996, ARRAY['Imidacloprid', 'Neem Oil', 'Trichoderma']),
    ('Kaveri Agro Services, Mysuru', 12.2958, 76.6394, ARRAY['Bordeaux Mixture', 'Mancozeb', 'Neem Oil']),
    ('Bhadra Farm Inputs, Davangere', 14.4644, 75.9218, ARRAY['Copper Oxychloride', 'Imidacloprid']),
    ('Tunga Agri Traders, Tirthahalli', 13.6891, 75.2327, ARRAY['Bordeaux Mixture', 'Mancozeb', 'Copper Oxychloride']),
    ('Sharavathi Agro, Honnavar', 14.2798, 74.4439, ARRAY['Bordeaux Mixture', 'Carbendazim']);
