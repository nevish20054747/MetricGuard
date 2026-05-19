# MetricGuard - API Testing Guide

## Overview

Disk and network speed metrics are stored in human-readable format (KB/MB/GB) for easier monitoring and dashboard visualization.

This guide explains how to test the MetricGuard backend API endpoints that the monitoring collector communicates with. These tests verify that the API correctly receives, validates, and stores system metrics.

---

## API Endpoint Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/metrics` | Submit system metrics |
| `GET` | `/metrics` | Retrieve stored metrics |
| `GET` | `/health` | Check backend health |

---

## Prerequisites

- Backend server running on `http://localhost:5000`
- `curl` installed (comes with most OS)
- Or Python with `requests` library

---

## Test 1: Health Check

**Purpose**: Verify the backend server is running.

### Using curl:
```bash
curl -X GET http://localhost:5000/health
```

### Expected Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-05-16T14:00:00"
}
```

### Status Code: `200 OK`

---

## Test 2: POST Metrics (Valid Payload)

**Purpose**: Verify the backend accepts a valid metrics payload.

### Using curl:
```bash
curl -X POST http://localhost:5000/metrics \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-05-16T14:00:00",
    "cpu_usage": 45.2,
    "ram_usage": 62.1,
    "disk_usage": 55.0,
    "disk_read_speed": "4.39 MB",
    "disk_write_speed": "2.15 MB",
    "network_upload_speed": "200 KB",
    "network_download_speed": "300 KB",
    "process_count": 150,
    "system_load": 1.5,
    "system_uptime": "24h 0m 0s"
  }'
```

### Using Python:
```python
import requests

url = "http://localhost:5000/metrics"

payload = {
    "timestamp": "2026-05-16T14:00:00",
    "cpu_usage": 45.2,
    "ram_usage": 62.1,
    "disk_usage": 55.0,
    "disk_read_speed": "4.39 MB",
    "disk_write_speed": "2.15 MB",
    "network_upload_speed": "200 KB",
    "network_download_speed": "300 KB",
    "process_count": 150,
    "system_load": 1.5,
    "system_uptime": "24h 0m 0s"
}

response = requests.post(url, json=payload)
print(f"Status: {response.status_code}")
print(f"Body: {response.json()}")
```

### Expected Response:
```json
{
  "message": "Metrics received successfully",
  "id": "664d..."
}
```

### Status Code: `201 Created` or `200 OK`

---

## Test 3: POST Metrics (Empty Payload)

**Purpose**: Verify the backend rejects an empty payload.

### Using curl:
```bash
curl -X POST http://localhost:5000/metrics \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Expected Response:
```json
{
  "error": "Invalid payload"
}
```

### Status Code: `400 Bad Request`

---

## Test 4: POST Metrics (Missing Fields)

**Purpose**: Verify the backend handles missing metric fields.

### Using curl:
```bash
curl -X POST http://localhost:5000/metrics \
  -H "Content-Type: application/json" \
  -d '{
    "cpu_usage": 45.2,
    "ram_usage": 62.1
  }'
```

### Expected Behavior:
- Backend should either:
  - Accept partial metrics (lenient mode), OR
  - Return `400` with a list of missing fields (strict mode)
- Check with the backend team for their implementation choice.

---

## Test 5: GET Metrics

**Purpose**: Verify stored metrics can be retrieved.

### Using curl:
```bash
curl -X GET http://localhost:5000/metrics
```

### Using Python:
```python
import requests

response = requests.get("http://localhost:5000/metrics")
metrics = response.json()

print(f"Total metrics: {len(metrics)}")
for m in metrics[:3]:  # Show first 3
    print(f"  {m['timestamp']} — CPU: {m['cpu_usage']}%")
```

### Expected Response:
```json
[
  {
    "timestamp": "2026-05-16T14:00:00",
    "cpu_usage": 45.2,
    "ram_usage": 62.1,
    ...
  },
  ...
]
```

### Status Code: `200 OK`

---

## Test 6: Stress Test (Rapid POSTs)

**Purpose**: Verify the API handles rapid successive requests.

### Using Python:
```python
import requests
import time

url = "http://localhost:5000/metrics"
payload = {
    "timestamp": "2026-05-16T14:00:00",
    "cpu_usage": 50.0,
    "ram_usage": 60.0,
    "disk_usage": 70.0,
    "disk_read_speed": "1 MB",
    "disk_write_speed": "500 KB",
    "network_upload_speed": "200 KB",
    "network_download_speed": "300 KB",
    "process_count": 100,
    "system_load": 2.0,
    "system_uptime": "24h 0m 0s"
}

success = 0
fail = 0

for i in range(50):
    try:
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code in (200, 201):
            success += 1
        else:
            fail += 1
    except Exception as e:
        fail += 1

print(f"Success: {success}/50, Failed: {fail}/50")
```

### Expected Result:
- At least 48/50 requests should succeed.
- No server crashes.

---

## Test 7: Invalid Content-Type

**Purpose**: Verify the API rejects non-JSON content.

### Using curl:
```bash
curl -X POST http://localhost:5000/metrics \
  -H "Content-Type: text/plain" \
  -d "This is not JSON"
```

### Expected Response:
- Status Code: `400` or `415 Unsupported Media Type`

---

## API Test Checklist

| # | Test | Expected Status | Result |
|---|------|----------------|--------|
| 1 | Health check | 200 | ⬜ |
| 2 | POST valid metrics | 200/201 | ⬜ |
| 3 | POST empty payload | 400 | ⬜ |
| 4 | POST missing fields | 400 | ⬜ |
| 5 | GET metrics | 200 | ⬜ |
| 6 | Stress test (50 requests) | 96%+ success | ⬜ |
| 7 | Invalid Content-Type | 400/415 | ⬜ |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Connection refused` | Backend is not running. Start with `python app.py` |
| `500 Internal Server Error` | Check backend logs for exceptions |
| Slow responses | Check MongoDB performance and indexes |
| Timeout errors | Increase `REQUEST_TIMEOUT` in config.py |
