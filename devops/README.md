# 🛡️ MetricGuard — DevOps & Monitoring Module

> **AI-Powered Real-Time System Monitoring and Anomaly Detection Platform**
>
> *Member 4 — DevOps, Monitoring Infrastructure & Deployment*

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Metrics Collected](#metrics-collected)
- [Quick Start](#quick-start)
- [Installation (Manual)](#installation-manual)
- [Docker Deployment](#docker-deployment)
- [Configuration](#configuration)
- [Logging](#logging)
- [Testing](#testing)
- [Deployment Guides](#deployment-guides)
- [Integration with Other Modules](#integration-with-other-modules)
- [Troubleshooting](#troubleshooting)
- [Team Responsibilities](#team-responsibilities)

---

## Overview

This module is responsible for the **DevOps and Monitoring infrastructure** of MetricGuard. It handles:

| Responsibility | Description |
|---------------|-------------|
| **Metric Collection** | Collects 10 live system metrics every 5 seconds using `psutil` |
| **Backend Communication** | Sends metrics to the backend API via HTTP POST with retry logic |
| **Logging** | Centralized logging to console and file (`logs/system.log`) |
| **Docker** | Containerized deployment with Docker Compose |
| **Testing** | Stress tests, anomaly tests, API tests, integration tests |
| **Deployment** | Guides for Docker, Render, and MongoDB Atlas |

**Responsibilities NOT handled by this module:**
- ❌ Frontend/Dashboard (handled by Member 1)
- ❌ Backend API (handled by Member 2)
- ❌ ML/AI Model (handled by Member 3)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MetricGuard System                       │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  MONITORING  │    │   BACKEND    │    │   DATABASE   │   │
│  │ (This Module)│───▶│   (API)      │───▶│  (MongoDB)  │   │
│  │              │    │              │    │              │   │
│  │ metric_      │    │ POST /metrics│    │ metrics      │   │
│  │ collector.py │    │              │    │ collection   │   │
│  └──────────────┘    └──────┬───────┘    └──────────────┘   │
│                             │                               │
│                             ▼                               │
│                    ┌──────────────┐    ┌──────────────┐     │
│                    │  ML ENGINE   │    │  DASHBOARD   │     │
│                    │  (Anomaly    │    │  (Frontend)  │     │
│                    │  Detection)  │    │              │     │
│                    └──────────────┘    └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow:

```
psutil → metric_collector.py → HTTP POST → Backend API → MongoDB
                                                ↓
                                         ML Model → Alerts
                                                ↓
                                           Dashboard
```

---

## Project Structure

```
devops/
│
├── monitoring/                    # Core monitoring code
│   ├── metric_collector.py        # Main collector (collects & sends metrics)
│   ├── logger.py                  # Centralized logging setup
│   ├── config.py                  # Configuration management
│   └── requirements.txt           # Python dependencies
│
├── docker/                        # Container configuration
│   ├── Dockerfile.monitoring      # Docker image for the collector
│   └── docker-compose.yml         # Multi-service orchestration
│
├── testing/                       # Test scripts and guides
│   ├── anomaly_test.py            # Stress tests & anomaly simulation
│   ├── integration_test.md        # Integration testing guide
│   └── api_test.md                # API testing guide
│
├── deployment/                    # Deployment documentation
│   ├── docker_deployment.md       # Docker deployment guide
│   ├── render_setup.md            # Render.com deployment guide
│   └── mongodb_atlas.md           # MongoDB Atlas setup guide
│
├── logs/                          # Log output directory
│   └── system.log                 # Application logs (auto-populated)
│
└── README.md                      # This file
```

---

## Metrics Collected

The collector gathers **10 system metrics** every 5 seconds:
**Note:** Disk and network speed metrics are stored in human-readable format (KB/MB/GB) for easier monitoring and dashboard visualization.

| # | Metric | psutil Function | Unit |
|---|--------|----------------|------|
| 1 | CPU Usage | `psutil.cpu_percent(interval=1)` | % |
| 2 | RAM Usage | `psutil.virtual_memory().percent` | % |
| 3 | Disk Usage | `psutil.disk_usage('/')` | % |
| 4 | Disk Read Speed | `psutil.disk_io_counters().read_bytes` | formatted string (KB/MB/GB) |
| 5 | Disk Write Speed | `psutil.disk_io_counters().write_bytes` | formatted string (KB/MB/GB) |
| 6 | Network Upload Speed | `psutil.net_io_counters().bytes_sent` | formatted string (KB/MB/GB) |
| 7 | Network Download Speed | `psutil.net_io_counters().bytes_recv` | formatted string (KB/MB/GB) |
| 8 | Process Count | `len(psutil.pids())` | count |
| 9 | System Load | `psutil.getloadavg()[0]` | avg |
| 10 | System Uptime | `time.time() - psutil.boot_time()` | formatted string (h/m/s) |

### Sample JSON Payload:

```json
{
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
```

---

## Quick Start

### Option A: Run with Docker (Recommended)

```bash
cd devops/
docker-compose -f docker/docker-compose.yml up --build
```

### Option B: Run Manually

```bash
cd devops/monitoring/
pip install -r requirements.txt
python metric_collector.py
```

---

## Installation (Manual)

### Prerequisites

- Python 3.9 or later
- pip (Python package manager)
- Git

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd devops/
```

### Step 2: Create a Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r monitoring/requirements.txt
```

### Step 4: Run the Collector

```bash
cd monitoring/
python metric_collector.py
```

### Expected Output:

```
[2026-05-16 14:00:00] INFO - =======================================================
[2026-05-16 14:00:00] INFO - MetricGuard Monitoring Collector - Starting Up
[2026-05-16 14:00:00] INFO - =======================================================
[2026-05-16 14:00:00] INFO - Backend URL    : http://localhost:5000/metrics
[2026-05-16 14:00:00] INFO - Interval       : 5 seconds
[2026-05-16 14:00:00] INFO - --- Collection Cycle #1 ---
[2026-05-16 14:00:00] INFO - Collecting system metrics...
[2026-05-16 14:00:01] INFO - Metrics collected successfully
[2026-05-16 14:00:01] INFO - Sending metrics to http://localhost:5000/metrics (attempt 1/3)
```

> **Note**: The collector includes exception handling and retry logic to ensure stable **continuous monitoring**.

---

## Docker Deployment

### Build and Run:

```bash
cd devops/
docker-compose -f docker/docker-compose.yml up --build -d
```

### Check Status:

```bash
docker ps
```

### View Logs:

```bash
docker logs <container-name> -f
```
(Replace `<container-name>` with your running monitoring container name.)

### Stop:

```bash
docker-compose -f docker/docker-compose.yml down
```

> 📖 For the full Docker deployment guide, see [`deployment/docker_deployment.md`](deployment/docker_deployment.md)

---

## Configuration

All settings are managed through environment variables with sensible defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://localhost:5000/metrics` | Backend API endpoint |
| `COLLECTION_INTERVAL` | `5` | Seconds between collections |
| `MAX_RETRIES` | `3` | Retry attempts on failure |
| `RETRY_DELAY` | `2` | Base delay between retries (exponential backoff) |
| `REQUEST_TIMEOUT` | `10` | HTTP request timeout (seconds) |
| `LOG_FILE` | `logs/system.log` | Log file path |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `DISK_PATH` | `/` | Disk path for usage monitoring |

### Override with Environment Variables:

```bash
# Linux/Mac
export BACKEND_URL=http://myserver:5000/metrics
export COLLECTION_INTERVAL=10

# Windows (PowerShell)
$env:BACKEND_URL = "http://myserver:5000/metrics"
$env:COLLECTION_INTERVAL = "10"
```

### Override with .env File:

Create a `.env` file in the `monitoring/` directory:

```env
BACKEND_URL=http://myserver:5000/metrics
COLLECTION_INTERVAL=10
LOG_LEVEL=DEBUG
```

---

## Logging

### Log Location:
- **Console**: Real-time output to terminal
- **File**: `logs/system.log`

### Log Format:
```
[2026-05-16 14:00:00] INFO - Metrics collected successfully
[2026-05-16 14:00:01] ERROR - Connection failed (attempt 1/3): Backend unreachable
[2026-05-16 14:00:03] INFO - Retrying in 2 seconds...
```

### What Gets Logged:
- ✅ Collector startup and configuration
- ✅ Each collection cycle
- ✅ Successful metric deliveries
- ✅ API failures and error details
- ✅ Retry attempts with backoff timing
- ✅ Unexpected exceptions with full tracebacks

---

## Testing

### Run All Tests:

```bash
cd devops/
python -m pytest testing/anomaly_test.py -v
```

### Run Specific Test Categories:

```bash
# CPU stress test
python -m pytest testing/anomaly_test.py::TestCPUStress -v

# RAM stress test
python -m pytest testing/anomaly_test.py::TestRAMStress -v

# Fake anomaly generation
python -m pytest testing/anomaly_test.py::TestFakeAnomaly -v

# Full collection test
python -m pytest testing/anomaly_test.py::TestFullCollection -v
```

### Test Categories:

| Test Suite | Purpose |
|-----------|---------|
| `TestCPUStress` | Burns CPU and verifies collector detects spike |
| `TestRAMStress` | Allocates 200MB RAM and verifies detection |
| `TestFakeAnomaly` | Creates synthetic extreme metric payloads |
| `TestFullCollection` | Verifies all 10 metrics are collected |

> 📖 For API testing, see [`testing/api_test.md`](testing/api_test.md)
>
> 📖 For integration testing, see [`testing/integration_test.md`](testing/integration_test.md)

---

## Deployment Guides

| Guide | Description |
|-------|-------------|
| [`docker_deployment.md`](deployment/docker_deployment.md) | Deploy with Docker Compose (recommended) |
| [`render_setup.md`](deployment/render_setup.md) | Deploy to Render.com cloud |
| [`mongodb_atlas.md`](deployment/mongodb_atlas.md) | Set up MongoDB Atlas (cloud database) |

---

## Integration with Other Modules

### For the Backend Team (Member 2):

The monitoring collector sends a `POST` request to:
```
http://localhost:5000/metrics
```

**Expected request:**
- Method: `POST`
- Content-Type: `application/json`
- Body: JSON object with 10 metrics + timestamp

**Expected response:**
- Status: `200` or `201`
- Body: Confirmation JSON

### For the ML Team (Member 3):

Metrics are stored in MongoDB in the `metrics` collection of the `metricguard_db` database. The ML model can query:

```python
db.metrics.find().sort("timestamp", -1).limit(100)
```

### For the Frontend Team (Member 1):

The backend provides the metrics via its API. The frontend does not interact with this module directly.

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ModuleNotFoundError: psutil` | Dependencies not installed | Run `pip install -r monitoring/requirements.txt` |
| `ConnectionRefusedError` | Backend not running | Start the backend first, or collector will retry |
| Collector crashes | Should not happen (catch-all in place) | Check `logs/system.log` for details |
| No logs appearing | Log directory missing | Create `logs/` directory manually |
| Docker build fails | Missing files or wrong path | Ensure you run from `devops/` root |
| Port 5000 in use | Another service on port 5000 | Change port in docker-compose.yml |
| `psutil.getloadavg()` returns 0 | Normal on Windows | Load average is Linux/Mac specific |

---

## Team Responsibilities

| Member | Role | Handles |
|--------|------|---------|
| Member 1 | Frontend | Dashboard, UI, real-time charts |
| Member 2 | Backend | REST API, MongoDB CRUD, WebSocket |
| Member 3 | ML/AI | Anomaly detection model, training |
| **Member 4** | **DevOps** | **Monitoring, Docker, deployment, testing** |

---

## License

This project is for educational purposes as part of the MetricGuard mini project.

---

*Built with ❤️ by the MetricGuard DevOps Team*
