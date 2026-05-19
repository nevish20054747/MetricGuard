# MetricGuard - Integration Testing Guide

## Overview

This guide explains how to perform **integration testing** for the MetricGuard monitoring pipeline. Integration tests verify that all components work together correctly:

```
Collector → Backend API → MongoDB → Dashboard
```

---

## Prerequisites

Before running integration tests, ensure:

1. **MongoDB** is running (local or Atlas)
2. **Backend API** is running on `http://localhost:5000`
3. **Monitoring Collector** is running
4. **Python 3.9+** is installed
5. **Dependencies installed**: `pip install -r monitoring/requirements.txt`

---

## Test 1: Verify MongoDB Connection

**Purpose**: Confirm the backend can connect to MongoDB.

### Steps:

1. Start MongoDB:
   ```bash
   # Local MongoDB
   mongod

   # Or using Docker
   docker run -d -p 27017:27017 --name mongo mongo:7.0
   ```

2. Test connection with Python:
   ```python
   from pymongo import MongoClient

   client = MongoClient("mongodb://localhost:27017/")
   db = client["metricguard_db"]

   # Insert a test document
   result = db.metrics.insert_one({"test": True, "value": 42})
   print(f"Inserted: {result.inserted_id}")

   # Read it back
   doc = db.metrics.find_one({"test": True})
   print(f"Found: {doc}")

   # Clean up
   db.metrics.delete_one({"test": True})
   print("Test passed: MongoDB connection works!")
   ```

### Expected Result:
- Document is inserted and retrieved successfully.
- No connection errors.

---

## Test 2: Verify Backend API Receives Metrics

**Purpose**: Confirm the backend API accepts POST requests at `/metrics`.

### Steps:

1. Start the backend:
   ```bash
   cd backend/
   python app.py
   ```

2. Send a test metric:
   ```bash
   curl -X POST http://localhost:5000/metrics \
     -H "Content-Type: application/json" \
     -d '{
       "timestamp": "2026-05-16T14:00:00",
       "cpu_usage": 45.2,
       "ram_usage": 62.1,
       "disk_usage": 55.0,
       "disk_read_speed": "1 MB",
       "disk_write_speed": "500 KB",
       "network_upload_speed": "200 KB",
       "network_download_speed": "300 KB",
       "process_count": 150,
       "system_load": 1.5,
       "system_uptime": "24h 0m 0s"
     }'
   ```

3. Or use Python:
   ```python
   import requests

   payload = {
      "timestamp": "2026-05-16T14:00:00",
      "cpu_usage": 45.2,
      "ram_usage": 62.1,
      "disk_usage": 55.0,
      "disk_read_speed": "1 MB",
      "disk_write_speed": "500 KB",
      "network_upload_speed": "200 KB",
      "network_download_speed": "300 KB",
      "process_count": 150,
      "system_load": 1.5,
      "system_uptime": "24h 0m 0s"
   }

   response = requests.post(
       "http://localhost:5000/metrics",
       json=payload
   )

   print(f"Status: {response.status_code}")
   print(f"Response: {response.json()}")
   ```

### Expected Result:
- Status code: `200` or `201`
- Response confirms metric was stored.

---

## Test 3: End-to-End Pipeline Test

**Purpose**: Verify the complete flow from collector to database.

### Steps:

1. Start all services:
   ```bash
   docker-compose -f docker/docker-compose.yml up --build
   ```

2. Wait 15 seconds for 3 collection cycles.

3. Check MongoDB for stored metrics:
   ```python
   from pymongo import MongoClient

   client = MongoClient("mongodb://metricguard:metricguard123@localhost:27017/metricguard_db?authSource=admin")
   db = client["metricguard_db"]

   # Count stored metrics
   count = db.metrics.count_documents({})
   print(f"Metrics stored: {count}")

   # Show the latest metric
   latest = db.metrics.find_one(sort=[("timestamp", -1)])
   print(f"Latest metric: {latest}")
   ```

### Expected Result:
- At least 3 metric documents in MongoDB.
- Each document has all 10 metric fields.

---

## Test 4: Failure Recovery Test

**Purpose**: Verify the collector handles backend downtime gracefully.

### Steps:

1. Start only the collector (without the backend):
   ```bash
   cd monitoring/
   python metric_collector.py
   ```

2. Observe logs:
   ```
   [2026-05-16 14:00:05] ERROR - Connection failed (attempt 1/3): Backend at http://localhost:5000/metrics is unreachable
   [2026-05-16 14:00:07] INFO  - Retrying in 2 seconds...
   [2026-05-16 14:00:09] ERROR - Connection failed (attempt 2/3): ...
   ```

3. Now start the backend while the collector is running.

4. Observe that the next cycle succeeds:
   ```
   [2026-05-16 14:00:20] INFO - Metrics sent successfully (status 200)
   ```

### Expected Result:
- Collector retries 3 times with exponential backoff.
- Collector does NOT crash.
- Collector recovers automatically when backend comes back.

---

## Test 5: Docker Networking Test

**Purpose**: Verify services can communicate via Docker DNS.

### Steps:

1. Start services:
   ```bash
   docker-compose -f docker/docker-compose.yml up -d
   ```

2. Enter the monitoring container:
   ```bash
   docker exec -it metricguard-monitoring sh
   ```

3. Test DNS resolution:
   ```bash
   # Ping the backend service
   python -c "import socket; print(socket.gethostbyname('backend'))"

   # Ping MongoDB
   python -c "import socket; print(socket.gethostbyname('mongodb'))"
   ```

### Expected Result:
- Both `backend` and `mongodb` resolve to internal Docker IPs.

---

## Integration Test Checklist

| # | Test | Status |
|---|------|--------|
| 1 | MongoDB connection works | ⬜ |
| 2 | Backend accepts POST /metrics | ⬜ |
| 3 | Full pipeline: Collector → Backend → MongoDB | ⬜ |
| 4 | Collector survives backend downtime | ⬜ |
| 5 | Docker DNS resolution works | ⬜ |
| 6 | Logs appear in logs/system.log | ⬜ |
| 7 | Metrics have correct timestamp format | ⬜ |
| 8 | All 10 metrics are collected | ⬜ |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ConnectionRefusedError` | Backend is not running. Start it first. |
| `pymongo.errors.ServerSelectionTimeoutError` | MongoDB is not running or wrong URI. |
| Collector crashes | Check `logs/system.log` for the full traceback. |
| Docker containers can't reach each other | Verify they're on the same Docker network. |
| Metrics missing from MongoDB | Check backend logs for errors on the `/metrics` endpoint. |
