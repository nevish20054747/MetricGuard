# Phase 5 — Database Integration & Persistence Layer: Walkthrough

## Summary

This walkthrough covers all production-grade improvements made to MetricGuard's database persistence layer, completing Phase 5 of the project.

---

## Changes Made

### 1. Database Connection & Health ([database.py](file:///d:/College/Mini%20Project/Implementation/MetricGuard/app/database.py))
- Exposed `DATABASE_URL` and `connect_args` at module level for reuse by Alembic
- Added `verify_db_connection(db)` utility — executes `SELECT 1` to confirm connectivity

### 2. ORM Models ([models.py](file:///d:/College/Mini%20Project/Implementation/MetricGuard/app/models.py))
- **Metric**: Added `created_at`, `updated_at` audit fields with `server_default=func.now()`
- **Anomaly**: 
  - Changed `metric_id` from `nullable=True` → `nullable=False`
  - Added `detected_by` column
  - Added `severity` index
  - Added `CheckConstraint` for `anomaly_score >= 0.0`
  - Added `CheckConstraint` for valid severity values
  - Added `created_at`, `updated_at` audit fields

### 3. Pydantic Schemas ([schemas.py](file:///d:/College/Mini%20Project/Implementation/MetricGuard/app/schemas.py))
- `AnomalyBase.metric_id` is now mandatory (`int`, not `Optional`)
- `MetricResponse` and `AnomalyResponse` include `created_at`/`updated_at`

### 4. CRUD Layer ([crud.py](file:///d:/College/Mini%20Project/Implementation/MetricGuard/app/crud.py))
- `insert_anomaly()` validates `metric_id is not None` before insert
- Added `get_anomalies_filtered()` with:
  - Filtering by `severity`, `root_cause`, `detected_by`
  - Sorting by any column with `asc`/`desc`
  - Pagination via `limit`/`offset`
  - Optional eager-loading of parent metric via `joinedload`

### 5. Metrics Router ([metrics.py](file:///d:/College/Mini%20Project/Implementation/MetricGuard/app/routers/metrics.py))
- `POST /metrics/` now runs ML pipeline inline when `detect=true` (default)
- Anomalies detected on ingest are stored with the just-created `metric_id`

### 6. Anomalies Router ([anomalies.py](file:///d:/College/Mini%20Project/Implementation/MetricGuard/app/routers/anomalies.py))
- `GET /anomalies/` supports `limit`, `offset`, `sort_by`, `sort_order`, `severity`, `root_cause`, `detected_by`, `include_metric` query params

### 7. ML Router ([ml.py](file:///d:/College/Mini%20Project/Implementation/MetricGuard/app/routers/ml.py))
- `POST /ml/predict` now persists the metric record first, then uses its ID for the anomaly insert

### 8. Application Startup ([main.py](file:///d:/College/Mini%20Project/Implementation/MetricGuard/app/main.py))
- Lifespan startup chain: verify DB connection → create tables → load ML models
- `GET /health` returns `{ status, api, database, timestamp }`

### 9. Alembic Migrations
- **[alembic.ini](file:///d:/College/Mini%20Project/Implementation/MetricGuard/alembic.ini)**: Configured with `prepend_sys_path = .`; `sqlalchemy.url` is set dynamically from `env.py`
- **[alembic/env.py](file:///d:/College/Mini%20Project/Implementation/MetricGuard/alembic/env.py)**: Loads `.env` from project root, imports `DATABASE_URL` + `connect_args` from `app.database`, and points at `Base.metadata` for autogenerate
- **[Initial migration](file:///d:/College/Mini%20Project/Implementation/MetricGuard/alembic/versions/b7a7bd7126eb_initial_schema.py)**: Creates `metrics` and `anomalies` tables with all columns, indexes, FK, and check constraints

### 10. Integration Tests ([test_integration.py](file:///d:/College/Mini%20Project/Implementation/MetricGuard/test_integration.py))

| Test Class | What it covers |
|---|---|
| `TestHealthCheck` | `/health` endpoint returns 200 with proper structure |
| `TestMetricsCRUD` | Metric insertion, value storage, speed string parsing, audit fields, ordering |
| `TestAnomaliesCRUD` | Anomaly insertion, FK enforcement (missing/invalid metric_id), audit fields |
| `TestOneToMany` | `/metrics/{id}/anomalies` returns linked anomalies, 404 for missing metric |
| `TestAnomalyFiltering` | Severity filter, detected_by filter, sort by score, pagination, include_metric |
| `TestRCAStats` | `/ml/rca/stats` returns totals, by_root_cause, by_severity |
| `TestCascadeDelete` | ORM-level cascade delete (parent Metric → child Anomalies) |
| `TestInputValidation` | Negative score rejected by check constraint, invalid severity rejected |

---

## How to Verify

### Alembic Migrations
```bash
# Apply migrations to TiDB (creates tables if they don't exist)
.venv\Scripts\alembic.exe upgrade head

# Check current migration version
.venv\Scripts\alembic.exe current

# Generate a new migration after model changes
.venv\Scripts\alembic.exe revision --autogenerate -m "description"
```

### Integration Tests
```bash
# Run all integration tests
.venv\Scripts\python.exe -m pytest test_integration.py -v

# Run a specific test class
.venv\Scripts\python.exe -m pytest test_integration.py::TestHealthCheck -v
```

### Manual API Testing
```powershell
# Health check
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"

# Insert metric (without ML detection)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/metrics/?detect=false" -Method Post `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{ "timestamp": "2026-06-04T12:00:00", "cpu_usage": 95.0, "ram_usage": 80.0 }'

# Query anomalies with filtering
Invoke-RestMethod -Uri "http://127.0.0.1:8000/anomalies/?severity=critical&include_metric=true&limit=5"
```
