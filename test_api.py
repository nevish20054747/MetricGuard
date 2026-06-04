"""
MetricGuard API Endpoint Test Script

Run the FastAPI server first:
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Then in a separate terminal run:
    python test_api.py
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"


def test_health():
    print("1. Testing /health endpoint...")
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    data = r.json()
    print(f"   -> Status: {data['status']} | Service: {data['service']}")
    return True


def test_post_metric():
    print("2. Testing POST /metrics/ ...")
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cpu_usage": 45.6,
        "ram_usage": 72.3,
        "disk_usage": 55.0,
        "disk_read_speed": "4.39 MB",
        "disk_write_speed": "200.00 KB",
        "network_upload_speed": "1.25 MB",
        "network_download_speed": "32.50 KB",
        "process_count": 312,
        "system_load": None,
        "system_uptime": "5h 30m 12s"
    }
    r = requests.post(f"{BASE_URL}/metrics/", json=payload)
    assert r.status_code == 201, f"POST /metrics/ failed: {r.status_code} - {r.text}"
    data = r.json()
    print(f"   -> Metric stored (ID: {data['id']}, CPU: {data['cpu_usage']}%)")
    return data["id"]


def test_get_metrics():
    print("3. Testing GET /metrics/ ...")
    r = requests.get(f"{BASE_URL}/metrics/", params={"limit": 5})
    assert r.status_code == 200, f"GET /metrics/ failed: {r.status_code}"
    data = r.json()
    print(f"   -> Retrieved {len(data)} metric records.")
    if data:
        latest = data[0]
        print(f"   -> Latest: ID={latest['id']}, CPU={latest['cpu_usage']}%, Memory={latest['memory_usage']}%")
    return True


def test_post_anomaly():
    print("4. Testing POST /anomalies/ ...")
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "anomaly_score": 0.923,
        "root_cause": "CPU Usage",
        "severity": "CRITICAL",
        "detected_by": "Isolation Forest + LSTM Autoencoder"
    }
    r = requests.post(f"{BASE_URL}/anomalies/", json=payload)
    assert r.status_code == 201, f"POST /anomalies/ failed: {r.status_code} - {r.text}"
    data = r.json()
    print(f"   -> Anomaly stored (ID: {data['id']}, Root Cause: {data['root_cause']})")
    return data["id"]


def test_get_anomalies():
    print("5. Testing GET /anomalies/ ...")
    r = requests.get(f"{BASE_URL}/anomalies/", params={"limit": 5})
    assert r.status_code == 200, f"GET /anomalies/ failed: {r.status_code}"
    data = r.json()
    print(f"   -> Retrieved {len(data)} anomaly records.")
    if data:
        latest = data[0]
        print(f"   -> Latest: ID={latest['id']}, Score={latest['anomaly_score']}, Severity={latest['severity']}")
    return True


if __name__ == "__main__":
    print("=" * 55)
    print("MetricGuard API Endpoint Verification")
    print("=" * 55)

    try:
        test_health()
        test_post_metric()
        test_get_metrics()
        test_post_anomaly()
        test_get_anomalies()
        print("\n🎉 All API endpoint tests PASSED!")
    except requests.ConnectionError:
        print("\n[ERROR] Cannot connect to the server.")
        print("Make sure the FastAPI server is running:")
        print("  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000")
    except AssertionError as e:
        print(f"\n[ERROR] Test failed: {e}")
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
