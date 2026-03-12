import requests
import json
import os

BASE_URL = "http://localhost:8000"

def test_health():
    print("--- 1. Testing GET / ---")
    resp = requests.get(f"{BASE_URL}/")
    print(f"Status: {resp.status_code}")
    print(resp.json())
    print()

def test_check_risk():
    print("--- 2. Testing GET /check-risk ---")
    resp = requests.get(f"{BASE_URL}/check-risk", params={"lat": 12.2958, "lon": 76.6394})
    print(f"Status: {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except:
        print(resp.text)
    print()

def test_map():
    print("--- 3. Testing GET /map ---")
    resp = requests.get(f"{BASE_URL}/map", params={"lat": 12.2958, "lon": 76.6394, "radius": 100})
    print(f"Status: {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2)[:500] + "... [truncated]")
    except:
        print(resp.text)
    print()

def test_register_device():
    print("--- 4. Testing POST /register-device ---")
    payload = {
        "farmer_hash": "test_farmer_123",
        "fcm_token": "test_token_abc123",
        "latitude": 12.2958,
        "longitude": 76.6394
    }
    resp = requests.post(f"{BASE_URL}/register-device", json=payload)
    print(f"Status: {resp.status_code}")
    try:
        print(resp.json())
    except:
        print(resp.text)
    print()

def test_report():
    print("--- 5. Testing POST /report ---")
    
    # Create a dummy image
    test_image_path = "test_dummy_image.jpg"
    with open(test_image_path, "wb") as f:
        f.write(b"fake image data")

    try:
        with open(test_image_path, "rb") as f:
            files = {"image": ("test_dummy_image.jpg", f, "image/jpeg")}
            data = {
                "latitude": 12.2958,
                "longitude": 76.6394,
                "crop_stage": "flowering",
                "farmer_hash": "test_farmer_123"
            }
            resp = requests.post(f"{BASE_URL}/report", files=files, data=data)
            print(f"Status: {resp.status_code}")
            try:
                print(json.dumps(resp.json(), indent=2))
            except json.JSONDecodeError:
                print(resp.text)
    finally:
        if os.path.exists(test_image_path):
            os.remove(test_image_path)
    print()

def test_refresh_clusters():
    print("--- 6. Testing POST /admin/refresh-clusters ---")
    resp = requests.post(f"{BASE_URL}/admin/refresh-clusters")
    print(f"Status: {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except:
        print(resp.text)
    print()

if __name__ == "__main__":
    try:
        test_health()
        test_check_risk()
        test_map()
        test_register_device()
        test_report()
        test_refresh_clusters()
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to {BASE_URL}. Is the server running?")
