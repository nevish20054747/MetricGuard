# MetricGuard AIOps Backend - Run & Integration Guide

Welcome to the backend of the **MetricGuard** AIOps platform. This application integrates a dual-model Machine Learning anomaly detection pipeline (Isolation Forest + Multivariate Autoencoder with Root Cause Analysis) into a FastAPI backend connected to a TiDB Cloud MySQL-compatible database.

---

## What Does This Backend Do?

This system serves as the central orchestration and storage engine for MetricGuard. It performs the following roles:

1. **Metrics Ingestion & Storage**: Accepts raw metrics (CPU, RAM, disk throughput, network bandwidth) collected from system endpoints. It automatically parses formatted throughput speed strings (e.g. `"4.39 MB"`, `"200 KB"`) into clean numerical values and persists them to the `metrics` table in TiDB.
2. **On-Ingest Real-Time Anomaly Detection**: Every time a metric is posted to the backend, the integrated ML pipeline optionally scores the incoming metric in real-time. If it qualifies as an anomaly, an entry is instantly generated and stored in the `anomalies` table.
3. **Traceability Linkage**: Maintains a proper one-to-many relationship (`Metric.anomalies` / `Anomaly.metric_id` -> `Metric.id`) between stored metrics and anomalies, allowing full drill-down analysis from anomalies back to the exact system metric snapshots that triggered them.
4. **Dual-Model ML Pipeline**:
   - **Isolation Forest**: Inspects instant, point-in-time anomalies (e.g., sudden massive CPU spikes, high memory utilization, or unusually slow backend response times).
   - **Multivariate Autoencoder**: Reconstructs time-series sequences (groups of 30 historical steps) to find anomalies in temporal trends and behaviors.
5. **Root Cause Analysis (RCA)**: When the Autoencoder triggers a trend anomaly, it calculates feature-wise reconstruction errors to pinpoint which resource category (CPU, Memory, Disk, or Network) is the primary contributor to the failure.
6. **REST API & Statistics**: Exposes structured API endpoints for fetching metrics history, anomaly logs, aggregate root cause stats (for frontend charts), and the current model queue/buffer levels.

---

## Directory Structure

```text
MetricGuard/ (Project Root)
├── .env                   # Database credentials and configuration
├── alembic.ini            # Alembic migration configuration
├── test_relationship.py   # Utility to verify database ORM relationships and cascade deletion
├── test_integration.py    # Integration test suite (30 tests, run with pytest)
├── alembic/
│   ├── env.py             # Alembic environment config (loads .env, connects to TiDB)
│   └── versions/          # Auto-generated migration scripts
└── app/
    ├── main.py            # FastAPI application config, lifespan events & routing mounts
    ├── database.py        # TiDB Cloud engine setup with SSL configurations
    ├── models.py          # SQLAlchemy ORM models (Metric & Anomaly with audit fields)
    ├── schemas.py         # Pydantic request & response schemas with input validation
    ├── crud.py            # Database operations (inserts, queries, filtering, pagination)
    ├── ml_service.py      # Thread-safe ML service singleton (handles TF & scikit-learn models)
    └── routers/
        ├── metrics.py     # Ingests & queries system metrics
        ├── anomalies.py   # Stores & queries historical anomalies (with filtering & sorting)
        └── ml.py          # Exposes on-demand ML predictions, RCA, and system status
```

---

## Getting Started & Run Instructions

Follow these steps to run the entire backend and testing pipeline:

### 1. Prerequisites & Virtual Environment

Ensure you are in the project root directory and activate your virtual environment:

```powershell
# Activate (.venv) in PowerShell
.venv\Scripts\Activate.ps1
```

Install the backend web, database, and machine learning packages:
```powershell
# Install FastAPI, ORM and Database Drivers
pip install fastapi uvicorn sqlalchemy pymysql cryptography python-dotenv

# Install migration and testing tools
pip install alembic httpx2 pytest

# Install ML libraries (TensorFlow, scikit-learn, joblib, etc.)
pip install -r devops/agent/requirements.txt
```

### 2. Configure the Environment (`.env`)

Verify that the `.env` file in the project root contains your database connection parameters:
```env
DB_HOST=your-tidb-cluster-hostname.tidbcloud.com
DB_PORT=4000
DB_USER=your-database-username
DB_PASSWORD=your-database-password
DB_NAME=your-database-name
```

### 3. Start the FastAPI Server

Launch Uvicorn in the terminal:
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*On startup, the system will automatically verify database connectivity, provision the database tables if they are missing, and load the pre-trained ML models from `devops/models/` into memory.*

### 4. Run Database Migrations (Alembic)

Apply the latest schema migrations to synchronize TiDB with the ORM models:
```powershell
# Apply all pending migrations
.venv\Scripts\alembic.exe upgrade head

# Check current migration version
.venv\Scripts\alembic.exe current

# Generate a new migration after model changes
.venv\Scripts\alembic.exe revision --autogenerate -m "description"
```

---

## Running the Complete System (Collector & Detector)

Open two additional terminal windows (with `.venv` active) to test the continuous monitoring pipeline:

### Terminal A: Run the Metrics Collector
Start the collector to capture live system statistics and send them to the backend:
```powershell
python devops/agent/main.py
```
*This script starts the MetricGuard Agent, which collects system metrics at a configurable interval and posts them directly to the backend API. It also monitors log files in the background via watchdog/pygtail.*

### Terminal B: Run the Real-Time AI Detector
Start the standalone monitoring loop to analyze and report anomalies:
```powershell
python devops/monitoring/realtime_ai_detection.py
```
*This script polls the backend database for the latest records, performs local model predictions, and POSTs any detected anomalies with full root cause analysis (RCA) stats back to the database.*

---

## Testing

### Integration Test Suite
Run the full 30-test integration suite against the live database:
```powershell
.venv\Scripts\python.exe -m pytest test_integration.py -v
```

The suite covers: health check, metrics CRUD, anomalies CRUD, FK enforcement, one-to-many relationships, cascade delete, filtering/sorting/pagination, RCA stats, and input validation.

### Relationship Linkage Tests
Verify database ORM mappings, relationships, and cascade-deletion behavior:
```powershell
python test_relationship.py
```

---

## Testing Backend Endpoints Manually

You can query the API server directly using native PowerShell commandlets:

### Health Check
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

### Check ML Model Status & Buffer Fill Level
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ml/status"
```

### Get Aggregated Root Cause Statistics (RCA counts)
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ml/rca/stats"
```

### POST a Sample Metric to Trigger Prediction
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ml/predict" `
  -Method Post `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{
    "timestamp": "2026-06-04T12:00:00",
    "cpu_usage": 95.0,
    "ram_usage": 98.0,
    "disk_usage": 80.0,
    "disk_read_speed": "15.0 MB",
    "disk_write_speed": "10.0 MB",
    "network_upload_speed": "500 KB",
    "network_download_speed": "10 MB",
    "process_count": 400,
    "system_load": 8.5,
    "system_uptime": "10h"
  }'
```

### Get Anomalies with Filtering, Sorting & Pagination
```powershell
# Filter by severity, include parent metric, limit to 5 results
Invoke-RestMethod -Uri "http://127.0.0.1:8000/anomalies/?severity=critical&include_metric=true&limit=5"

# Sort by anomaly_score ascending, page 2
Invoke-RestMethod -Uri "http://127.0.0.1:8000/anomalies/?sort_by=anomaly_score&sort_order=asc&offset=10&limit=10"

# Filter by detection method
Invoke-RestMethod -Uri "http://127.0.0.1:8000/anomalies/?detected_by=isolation_forest"
```

### Get Anomalies Generated from a Specific Metric (e.g., ID 2)
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/metrics/2/anomalies"
```
