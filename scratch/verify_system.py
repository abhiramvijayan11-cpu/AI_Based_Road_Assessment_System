import os
import sys
import json
import sqlite3

# Ensure project root is in sys.path
PROJECT_ROOT = r"c:\\road project"
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from app import app, DATABASE, create_database

def test_database_initialization():
    # Remove existing DB for a clean test
    if os.path.exists(DATABASE):
        os.remove(DATABASE)
    create_database()
    assert os.path.exists(DATABASE), "Database file was not created"
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='road_segments';")
    assert cur.fetchone() is not None, "road_segments table missing"
    conn.close()
    print("Database initialization test passed")

def test_upload_endpoint():
    client = app.test_client()
    # Sample payload mimicking Android upload
    payload = {
        "latitude": 12.9716,
        "longitude": 77.5946,
        "speed": 30,
        "vibration": 0.5,
        "road_health": 0.8,
        "road_id": "sample-road-id"
    }
    response = client.post("/upload", json=payload)
    assert response.status_code == 200, f"Upload endpoint returned {response.status_code}"
    data = response.get_json()
    assert data.get('status') == 'success', "Upload endpoint did not return success"
    print("/upload endpoint test passed")

def test_latest_location_endpoint():
    client = app.test_client()
    # First, ensure there is a latest location (set by previous upload)
    payload = {
        "latitude": 12.9716,
        "longitude": 77.5946,
        "speed": 30,
        "vibration": 0.5,
        "road_health": 0.8,
        "road_id": "sample-road-id"
    }
    client.post("/upload", json=payload)
    response = client.get("/latest_location")
    assert response.status_code == 200, f"Latest location endpoint returned {response.status_code}"
    data = response.get_json()
    assert 'latitude' in data and 'longitude' in data, "Latest location data missing"
    print("/latest_location endpoint test passed")

if __name__ == "__main__":
    print("--- Running System Integration Tests ---")
    test_database_initialization()
    test_upload_endpoint()
    test_latest_location_endpoint()
    print("--- All tests passed ---")
