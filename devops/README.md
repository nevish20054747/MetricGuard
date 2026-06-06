# 🛡️ MetricGuard — DevOps & Monitoring Module

> **AI-Powered Real-Time System Monitoring and Anomaly Detection Platform**
>
> *Member 4 — DevOps, Monitoring Infrastructure & Deployment*

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
  - [System Architecture](#system-architecture)
  - [Agent Internal Architecture](#agent-internal-architecture)
  - [Metrics Pipeline](#metrics-pipeline)
  - [Log Collection Pipeline](#log-collection-pipeline)
- [Project Structure](#project-structure)
- [Metrics Collected](#metrics-collected)
- [Quick Start](#quick-start)
- [Installation (Manual)](#installation-manual)
- [Configuration (config.yaml)](#configuration-configyaml)
  - [Backend & Identity](#backend--identity)
  - [Retry & Resilience](#retry--resilience)
  - [Logging](#logging-configuration)
  - [Metric Toggles](#metric-toggles)
  - [Log Collection](#log-collection-configuration)
- [Log Monitoring Pipeline](#log-monitoring-pipeline)
  - [How watchdog Works](#how-watchdog-works)
  - [How pygtail Prevents Duplicates](#how-pygtail-prevents-duplicates)
  - [Log Parsing](#log-parsing)
  - [Watched Log Files](#watched-log-files)
- [Retry Logic & Resilience](#retry-logic--resilience)
- [Graceful Shutdown](#graceful-shutdown)
- [Logging & Observability](#logging--observability)
- [Docker Deployment](#docker-deployment)
- [Testing](#testing)
- [Deployment Guides](#deployment-guides)
- [Integration with Other Modules](#integration-with-other-modules)
- [Troubleshooting](#troubleshooting)
- [Deprecated Legacy Architecture](#deprecated-legacy-architecture)
- [Team Responsibilities](#team-responsibilities)

---

## Overview

This module is responsible for the **DevOps and Monitoring infrastructure** of MetricGuard. It provides a production-ready, modular **MetricGuard Agent** that behaves similarly to industry-standard monitoring agents such as Datadog Agent, Metricbeat, Node Exporter, and New Relic Agent.

| Responsibility | Description |
|---|---|
| **Metric Collection** | Collects 10 live system metrics at configurable intervals using `psutil` |
| **Log Collection** | Watches application log files for new lines, parses them into structured JSON, and ships them to the backend |
| **Backend Communication** | Sends metrics and logs to the backend API via HTTP POST with retry logic and exponential backoff |
| **YAML Configuration** | All agent behavior is driven by a single `config.yaml` file — no code changes needed for deployment tuning |
| **Logging & Observability** | Dual-output logging (console + file) with structured format, startup banners, and per-cycle status |
| **Docker** | Containerized deployment with Docker Compose orchestration |
| **Testing** | Stress tests, anomaly simulation, monitoring verification, API tests, integration tests |
| **Deployment** | Guides for Docker, Render.com, and MySQL/TiDB Cloud database setup |

**Responsibilities NOT handled by this module:**
- ❌ Frontend/Dashboard (handled by Member 1)
- ❌ Backend API / Database (handled by Member 2)
- ❌ ML/AI Anomaly Detection Model (handled by Member 3)

---

## Architecture

### System Architecture

The MetricGuard Agent sits at the edge of the platform, continuously collecting system metrics and application logs and shipping them to the backend for storage, analysis, and visualization.

```
┌──────────────────────────────────────────────────────────────────────┐
│                         MetricGuard System                           │
│                                                                      │
│  ┌───────────────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │    METRICGUARD AGENT  │    │   BACKEND    │    │   DATABASE   │   │
│  │    (This Module)      │───▶│   (API)      │───▶│  MySQL /     │   │
│  │                       │    │              │    │  TiDB Cloud  │   │
│  │  collector.py ────────│──▶ │ POST /metrics│    │ metrics tbl  │   │
│  │  log_collector.py ────│──▶ │ POST /logs   │    │ logs tbl     │   │
│  └───────────────────────┘    └──────┬───────┘    └──────────────┘   │
│                                      │                               │
│                                      ▼                               │
│                             ┌──────────────┐    ┌──────────────┐     │
│                             │  ML ENGINE   │    │  DASHBOARD   │     │
│                             │  (Anomaly    │    │  (Frontend)  │     │
│                             │  Detection)  │    │              │     │
│                             └──────────────┘    └──────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
```

### Agent Internal Architecture

The agent is composed of five focused modules, orchestrated by `main.py`:

```
                  ┌────────────────┐
                  │   config.yaml  │
                  └───────┬────────┘
                          │ load + validate
                          ▼
┌───────────┐     ┌──────────────┐      ┌──────────────┐
│ logger.py │◀────│   main.py    │─────▶│ collector.py │
└───────────┘     │   (loop)     │      │  (psutil)    │
                  │              │      └──────┬───────┘
                  │              │             │ metrics payload
                  │              │             ▼
                  │              │      ┌──────────────┐
                  │              │─────▶│  sender.py   │──▶ POST /metrics
                  │              │      └──────────────┘
                  │              │             ▲
                  │              │             │ log entries
                  │              │      ┌──────┴───────┐
                  │              │─────▶│log_collector │
                  └──────────────┘      │  (watchdog)  │
                                        │  (pygtail)   │
                                        └──────────────┘
                                               ▲
                                        watched_logs/
                                        ├── application.log
                                        ├── database.log
                                        └── server.log
```

### Metrics Pipeline

```
psutil  →  collector.py  →  sender.py  →  POST /metrics  →  Backend API  →  MySQL (TiDB Cloud)
                                                                ↓
                                                         ML Engine → Alerts
                                                                ↓
                                                           Dashboard
```

### Log Collection Pipeline

```
application.log ──┐
database.log ─────┤  watchdog (filesystem events)
server.log ───────┘         │
                            ▼
                  ┌──────────────────┐
                  │  log_collector   │
                  │  (pygtail reads  │
                  │   only NEW lines)│
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │   log_parser     │
                  │  (regex → JSON)  │
                  └────────┬─────────┘
                           │
                      POST /logs
                           │
                           ▼
                   ┌──────────────────┐     ┌────────────────┐
                   │  Backend API     │────▶│ MySQL (TiDB    │
                   │  (logs router)   │     │ Cloud) / logs  │
                   └──────────────────┘     └────────────────┘
```

---

## Project Structure

```
devops/
│
├── agent/                              # ✅ ACTIVE — Production-ready modular agent
│   ├── main.py                         #    Entry point — orchestrates all modules
│   ├── collector.py                    #    psutil metric collection (modular functions)
│   ├── sender.py                       #    HTTP POST to /metrics and /logs with retry
│   ├── log_collector.py                #    watchdog + pygtail log monitoring
│   ├── log_parser.py                   #    Regex-based log line → structured JSON
│   ├── logger.py                       #    Centralized dual-output logging setup
│   ├── config.py                       #    YAML loader with validation + defaults
│   ├── config.yaml                     #    All runtime configuration
│   ├── requirements.txt                #    Python dependencies
│   ├── logs/                           #    Agent log output directory
│   │   └── agent.log                   #        Agent runtime logs (auto-populated)
│   └── watched_logs/                   #    Log files monitored by the agent
│       ├── application.log             #        Application-level logs
│       ├── database.log                #        Database-related logs
│       └── server.log                  #        Server/infrastructure logs
│
├── monitoring/                         # ⚠️ DEPRECATED — Legacy single-file collector
│   ├── metric_collector.py             #    Original monolithic collector + sender
│   ├── config.py                       #    Env-var-based configuration
│   ├── logger.py                       #    Original logging module
│   ├── requirements.txt                #    Legacy dependencies
│   └── realtime_ai_detection.py        #    Standalone AI detection script
│
├── docker/                             # Container configuration
│   ├── Dockerfile.monitoring           #    Docker image for the agent
│   └── docker-compose.yml              #    Multi-service orchestration
│
├── testing/                            # Test scripts and guides
│   ├── anomaly_test.py                 #    Stress tests & anomaly simulation
│   ├── agent_test.py                   #    Agent pipeline verification
│   ├── rca_test.py                     #    Root cause analysis tests
│   ├── integration_test.md             #    Integration testing guide
│   └── api_test.md                     #    API testing guide
│
├── deployment/                         # Deployment documentation
│   ├── docker_deployment.md            #    Docker deployment guide
│   ├── render_setup.md                 #    Render.com deployment guide
│   └── tidb_cloud_setup.md             #    TiDB Cloud database setup guide
│
└── README.md                           # This file
```

> **Note:** The `monitoring/` directory is the original (now deprecated) implementation. The `agent/` directory is the active, production-ready architecture. See [Deprecated Legacy Architecture](#deprecated-legacy-architecture) for migration details.

---

## Metrics Collected

The agent gathers **10 system metrics** at a configurable interval (default: 30 seconds). Each metric has its own modular collection function with isolated error handling — a single failing metric never prevents the rest from being collected.

> **Note:** Disk I/O and network speed metrics report **delta speed** (bytes since last collection), formatted as human-readable strings (KB/MB/GB). Individual metrics can be disabled via `config.yaml` toggles.

| # | Metric | psutil Function | Unit | Config Toggle |
|---|--------|----------------|------|---------------|
| 1 | CPU Usage | `psutil.cpu_percent(interval=1)` | % | `cpu` |
| 2 | RAM Usage | `psutil.virtual_memory().percent` | % | `memory` |
| 3 | Disk Usage | `psutil.disk_usage('/').percent` | % | `disk` |
| 4 | Disk Read Speed | `psutil.disk_io_counters().read_bytes` | formatted (KB/MB/GB) | `disk` |
| 5 | Disk Write Speed | `psutil.disk_io_counters().write_bytes` | formatted (KB/MB/GB) | `disk` |
| 6 | Network Upload Speed | `psutil.net_io_counters().bytes_sent` | formatted (KB/MB/GB) | `network` |
| 7 | Network Download Speed | `psutil.net_io_counters().bytes_recv` | formatted (KB/MB/GB) | `network` |
| 8 | Process Count | `len(psutil.pids())` | count | `process_count` |
| 9 | System Load | `psutil.getloadavg()[0]` | avg | `system_load` |
| 10 | System Uptime | `time.time() - psutil.boot_time()` | formatted (h/m/s) | `system_uptime` |

### Sample Metrics JSON Payload

Every payload includes a `timestamp` and the `agent_name` configured in `config.yaml`:

```json
{
  "timestamp": "2026-06-05T22:30:00",
  "agent_name": "machine-01",
  "cpu_usage": 45.2,
  "ram_usage": 62.1,
  "disk_usage": 55.0,
  "disk_read_speed": "4.39 MB",
  "disk_write_speed": "2.15 MB",
  "network_upload_speed": "200.00 KB",
  "network_download_speed": "300.00 KB",
  "process_count": 150,
  "system_load": 1.5,
  "system_uptime": "24h 0m 0s"
}
```

### Sample Log JSON Payload

Each parsed log line is sent as a structured entry to `POST /logs`:

```json
{
  "timestamp": "2026-06-05 10:15:00",
  "level": "ERROR",
  "message": "Database connection timeout after 30s",
  "service_name": "database-service"
}
```

---

## Quick Start

### Option A: Run with Docker (Recommended)

```bash
cd devops/
docker-compose -f docker/docker-compose.yml up --build
```

### Option B: Run the Agent Manually

```bash
cd devops/agent/
pip install -r requirements.txt
python main.py
```

The agent starts collecting metrics immediately and watches log files in the background. Press `Ctrl+C` for a clean shutdown.

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
pip install -r agent/requirements.txt
```

The agent requires the following packages:

| Package | Version | Purpose |
|---------|---------|---------|
| `psutil` | ≥ 5.9.8 | System metrics collection |
| `requests` | ≥ 2.31.0 | HTTP communication with backend |
| `PyYAML` | ≥ 6.0 | YAML configuration loading |
| `watchdog` | ≥ 4.0.0 | Filesystem event monitoring for log collection |
| `pygtail` | ≥ 0.14.0 | Incremental log file reading |

### Step 4: Configure the Agent

Edit `agent/config.yaml` to set your backend URL and preferences. See [Configuration](#configuration-configyaml) for a full reference.

### Step 5: Run the Agent

```bash
cd agent/
python main.py
```

### Expected Startup Output

```
[2026-06-05 22:30:00] INFO     — ==========================================================
[2026-06-05 22:30:00] INFO     —   MetricGuard Agent — Starting Up
[2026-06-05 22:30:00] INFO     — ==========================================================
[2026-06-05 22:30:00] INFO     —   Agent Name       : machine-01
[2026-06-05 22:30:00] INFO     —   Backend URL      : http://backend:5000/metrics
[2026-06-05 22:30:00] INFO     —   Collect Interval : 30 s
[2026-06-05 22:30:00] INFO     —   Max Retries      : 3
[2026-06-05 22:30:00] INFO     —   Retry Delay      : 2 s (exponential)
[2026-06-05 22:30:00] INFO     —   Request Timeout  : 10 s
[2026-06-05 22:30:00] INFO     —   Log File         : logs/agent.log
[2026-06-05 22:30:00] INFO     —   Log Level        : INFO
[2026-06-05 22:30:00] INFO     —   Disk Path        : /
[2026-06-05 22:30:00] INFO     —   Platform         : Windows-10-...
[2026-06-05 22:30:00] INFO     —   Enabled Metrics  :
[2026-06-05 22:30:00] INFO     —       cpu              ON
[2026-06-05 22:30:00] INFO     —       memory           ON
[2026-06-05 22:30:00] INFO     —       disk             ON
[2026-06-05 22:30:00] INFO     —       network          ON
[2026-06-05 22:30:00] INFO     —       process_count    ON
[2026-06-05 22:30:00] INFO     —       system_load      ON
[2026-06-05 22:30:00] INFO     —       system_uptime    ON
[2026-06-05 22:30:00] INFO     —   Log Watch Files  :
[2026-06-05 22:30:00] INFO     —       watched_logs/application.log
[2026-06-05 22:30:00] INFO     —       watched_logs/database.log
[2026-06-05 22:30:00] INFO     —       watched_logs/server.log
[2026-06-05 22:30:00] INFO     — ==========================================================
[2026-06-05 22:30:00] INFO     — ==================================================
[2026-06-05 22:30:00] INFO     —   Log Collector — Starting
[2026-06-05 22:30:00] INFO     — ==================================================
[2026-06-05 22:30:00] INFO     — ——— Collection Cycle #1 ———
[2026-06-05 22:30:00] INFO     — Collecting system metrics...
[2026-06-05 22:30:01] INFO     — Metrics collected successfully
[2026-06-05 22:30:01] INFO     — Sending metrics to http://backend:5000/metrics (attempt 1/3)
```

> **Note:** The agent includes comprehensive exception handling and retry logic to ensure stable, continuous monitoring. It **never crashes** — any unexpected error is caught, logged, and the loop continues.

---

## Configuration (config.yaml)

All agent behavior is driven by a single YAML file: `agent/config.yaml`. The configuration is loaded and validated at startup by `config.py`, which uses a **frozen dataclass** to ensure immutability at runtime. Every field has a safe default — if a key is missing or malformed, the agent logs a warning and continues with the default value.

### Backend & Identity

```yaml
# URL where collected metrics are POSTed
backend_url: "http://backend:5000/metrics"

# How often (seconds) the agent collects and sends metrics
collection_interval: 30

# Human-readable name for this machine / instance
# Included in every payload so the backend can distinguish hosts
agent_name: "machine-01"
```

### Retry & Resilience

```yaml
# How many times to retry a failed POST
max_retries: 3

# Base delay (seconds) between retries — doubles each attempt
retry_delay: 2

# Seconds before an HTTP request is abandoned
request_timeout: 10
```

### Logging Configuration

```yaml
# Path to the agent's persistent log file
log_file: "logs/agent.log"

# Logging verbosity: DEBUG | INFO | WARNING | ERROR | CRITICAL
log_level: "INFO"
```

### Disk Monitoring

```yaml
# Filesystem path for psutil.disk_usage()
# Linux/macOS: "/"   |   Windows: "C:\\"
disk_path: "/"
```

### Metric Toggles

Disable any metric by setting it to `false`. The agent simply skips disabled metrics — no errors, no empty fields:

```yaml
enabled_metrics:
  cpu: true
  memory: true
  disk: true
  network: true
  process_count: true
  system_load: true        # returns null on Windows — safe to disable
  system_uptime: true
```

### Log Collection Configuration

```yaml
# List of log files the agent watches for new lines
# Paths can be relative (to agent/) or absolute
log_watch_files:
  - "watched_logs/application.log"
  - "watched_logs/database.log"
  - "watched_logs/server.log"

# (Optional) Explicit URL for the logs endpoint
# If omitted, derived from backend_url: .../metrics → .../logs
logs_backend_url: "http://backend:5000/logs"
```

> **Backward compatibility:** If `log_watch_files` is empty or absent, the log collector is disabled entirely and the agent runs in metrics-only mode — fully compatible with pre-Phase 7 deployments.

### Full Configuration Reference

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `backend_url` | string | `http://localhost:8000/metrics` | Backend metrics endpoint |
| `collection_interval` | int | `30` | Seconds between collection cycles |
| `agent_name` | string | `machine-01` | Host identifier in payloads |
| `max_retries` | int | `3` | Retry count on failed POST |
| `retry_delay` | int | `2` | Base retry delay (exponential) |
| `request_timeout` | int | `10` | HTTP request timeout (seconds) |
| `log_file` | string | `logs/agent.log` | Agent log file path |
| `log_level` | string | `INFO` | Logging verbosity |
| `disk_path` | string | `/` | Disk path for usage monitoring |
| `enabled_metrics` | dict | all `true` | Per-metric on/off toggles |
| `log_watch_files` | list | `[]` | Log files to watch |
| `logs_backend_url` | string | *(derived)* | Backend logs endpoint |

---

## Log Monitoring Pipeline

The agent includes a production-style log collection pipeline that monitors application log files in real time, parses each new line into structured JSON, and sends it to the backend via `POST /logs`.

### How watchdog Works

[watchdog](https://python-watchdog.readthedocs.io/) is a cross-platform filesystem event library that provides real-time notifications when files are modified — far more efficient than polling.

1. An `Observer` is created in a **background daemon thread** (non-blocking).
2. The observer watches the directories containing the configured log files.
3. When any monitored file receives new bytes (i.e. a log line is appended), watchdog fires an `on_modified` callback.
4. The callback triggers `pygtail` to read only the new lines.

This means log lines are detected and processed within **milliseconds** of being written — there is no polling delay.

### How pygtail Prevents Duplicates

[pygtail](https://github.com/bgreenlee/pygtail) reads a file incrementally, tracking its position using a small **offset file**:

```
watched_logs/application.log           →  the actual log file
.offsets/application.log.offset        →  last-read byte position
```

On each invocation:

1. pygtail reads the offset file to determine where it left off.
2. It reads **only the bytes after that position** — no full-file re-reads.
3. It updates the offset file with the new position.

**Result:**
- ✅ **Restart-safe** — after an agent restart, pygtail resumes from the exact byte it stopped at.
- ✅ **No duplicates** — each line is processed exactly once.
- ✅ **Efficient** — only new bytes are touched, regardless of file size.

### Log Parsing

The `log_parser.py` module uses regex to convert raw log lines into structured dictionaries:

**Input:**
```
2026-06-05 10:15:00 ERROR Database connection timeout after 30s
```

**Output:**
```json
{
  "timestamp": "2026-06-05 10:15:00",
  "level": "ERROR",
  "message": "Database connection timeout after 30s",
  "service_name": "database-service"
}
```

**Handling malformed lines:** If a line doesn't match the expected `TIMESTAMP LEVEL MESSAGE` format (e.g. a stack trace continuation), the parser emits it with `level: "UNKNOWN"` so no data is silently lost. A warning is logged for operator visibility.

**Service name mapping:** The `service_name` field is inferred from the filename of the log file being watched:

| Log File | Service Name |
|----------|-------------|
| `application.log` | `application-service` |
| `database.log` | `database-service` |
| `server.log` | `server-service` |
| `<anything>.log` | `<anything>-service` (fallback) |

### Watched Log Files

The agent creates the `watched_logs/` directory and the configured log files automatically at startup if they don't exist. To simulate log activity for testing:

```bash
# Append lines to a watched file
echo "2026-06-05 22:30:00 ERROR Database connection timeout" >> agent/watched_logs/database.log
echo "2026-06-05 22:30:01 INFO Connection pool restored" >> agent/watched_logs/database.log
echo "2026-06-05 22:30:02 WARNING Disk usage above 85%" >> agent/watched_logs/server.log
```

The agent will detect the new lines within milliseconds, parse them, and send them to `POST /logs`.

---

## Retry Logic & Resilience

Both the metrics sender and the log sender share the same retry engine (`sender.py → _post_with_retry()`):

1. **Attempt the POST** with a configured timeout.
2. **On success (2xx):** Log the success and return `True`.
3. **On failure (connection error, timeout, non-2xx):** Log the failure reason.
4. **Wait with exponential backoff:** `retry_delay × 2^(attempt-1)` seconds.
5. **Repeat** up to `max_retries` times.
6. **After all retries exhausted:** Log an error and return `False`. The main loop moves on to the next cycle.

**Example with default settings** (3 retries, 2s base delay):

| Attempt | Delay After |
|---------|-------------|
| 1 | 2 seconds |
| 2 | 4 seconds |
| 3 | *(final — no delay)* |

The agent **never crashes** due to backend unavailability. It logs the failure and continues collecting.

---

## Graceful Shutdown

The agent handles shutdown signals cleanly:

- **`Ctrl+C` (SIGINT):** The signal handler sets a shutdown flag. The main loop exits at the next iteration boundary.
- **`SIGTERM` (Docker stop / `kill`):** Handled identically — the loop exits cleanly.
- **On exit:** The log collector's watchdog observer is stopped, all threads are joined, and a shutdown banner is logged.

```
[2026-06-05 22:45:00] INFO     — Shutdown requested (KeyboardInterrupt)
[2026-06-05 22:45:00] INFO     — Stopping Log Collector observer...
[2026-06-05 22:45:00] INFO     — Log Collector stopped
[2026-06-05 22:45:00] INFO     — ==========================================================
[2026-06-05 22:45:00] INFO     —   MetricGuard Agent — Stopped  (15 cycles)
[2026-06-05 22:45:00] INFO     — ==========================================================
```

This ensures no data corruption, no zombie threads, and clean Docker container lifecycle.

---

## Logging & Observability

### Log Destinations

| Destination | Purpose |
|---|---|
| **Console** (stdout) | Real-time visibility during development and in `docker logs` |
| **File** (`logs/agent.log`) | Persistent history that survives restarts |

### Log Format

```
[2026-06-05 22:30:00] INFO     — Metrics collected successfully
[2026-06-05 22:30:01] ERROR    — Connection failed (attempt 1/3): Backend at http://backend:5000/metrics is unreachable
[2026-06-05 22:30:03] INFO     — Retrying in 2 seconds...
[2026-06-05 22:30:05] INFO     — Read 3 new line(s) from database.log
[2026-06-05 22:30:05] INFO     — Sent 3/3 log entries from database.log
```

### What Gets Logged

- ✅ Agent startup banner with full configuration summary
- ✅ Each metric collection cycle (start, success, or errors)
- ✅ Successful metric and log deliveries with HTTP status codes
- ✅ API failures with detailed error types (ConnectionError, Timeout, etc.)
- ✅ Retry attempts with backoff duration
- ✅ Log file modification events and line counts
- ✅ Log parsing warnings for malformed lines
- ✅ Graceful shutdown events
- ✅ Unexpected exceptions with full tracebacks

---

## Docker Deployment

Docker now runs the **modular agent** (`agent/main.py`), not the legacy collector.

### Build and Run

```bash
cd devops/
docker-compose -f docker/docker-compose.yml up --build -d
```

### Container Details

| Container | Image | Entrypoint | Port |
|---|---|---|---|
| `metricguard-monitoring` | `metricguard-agent` | `python main.py` | — |
| `metricguard-backend` | `metricguard-backend` | *(backend team)* | 8000 |
| `metricguard-db` | MySQL / TiDB Cloud | — | 3306 |

### Check Status

```bash
docker ps
```

### View Logs

```bash
# All services
docker-compose -f docker/docker-compose.yml logs -f

# Agent only
docker logs metricguard-monitoring -f
```

### Stop

```bash
docker-compose -f docker/docker-compose.yml down
```

### Docker Networking

Services communicate via Docker DNS names on the `metricguard-network` bridge:

| From | To | URL |
|---|---|---|
| Agent | Backend | `http://backend:8000/metrics` |
| Agent | Backend | `http://backend:8000/logs` |
| Backend | MySQL / TiDB Cloud | *(configured via `DB_HOST` environment variable)* |

### Environment Variable Overrides

The Docker Compose file passes environment variables to override `config.yaml` defaults:

```yaml
environment:
  BACKEND_URL: http://backend:5000/metrics
  COLLECTION_INTERVAL: 5
  MAX_RETRIES: 3
  LOG_LEVEL: INFO
```

> 📖 For the full Docker deployment guide, see [`deployment/docker_deployment.md`](deployment/docker_deployment.md)

---

## Testing

### Test Suites

MetricGuard includes comprehensive test suites:

| File | Purpose |
|------|---------|
| `testing/anomaly_test.py` | Stress tests & anomaly simulation (CPU burn, RAM allocation, fake payloads) |
| `testing/agent_test.py` | Verifies the agent pipeline is actively running and collecting data |
| `testing/rca_test.py` | Root cause analysis verification tests (legacy ML compatibility) |

### Run All Tests

```bash
cd devops/
python -m pytest testing/ -v
```

---

### 1. Anomaly & Stress Tests (`anomaly_test.py`)

These tests simulate abnormal system conditions to verify the metric collector handles extreme values correctly.

```bash
cd devops/
python -m pytest testing/anomaly_test.py -v
```

#### Run specific categories:

```bash
python -m pytest testing/anomaly_test.py::TestCPUStress -v
python -m pytest testing/anomaly_test.py::TestRAMStress -v
python -m pytest testing/anomaly_test.py::TestFakeAnomaly -v
python -m pytest testing/anomaly_test.py::TestFullCollection -v
```

| Test Class | Purpose |
|-----------|---------|
| `TestCPUStress` | Burns CPU and verifies collector detects spike |
| `TestRAMStress` | Allocates 200MB RAM and verifies detection |
| `TestFakeAnomaly` | Creates synthetic extreme metric payloads |
| `TestFullCollection` | Verifies all 10 metrics are collected |

---

### 2. Agent Verification Tests (`agent_test.py`)

These tests verify that the MetricGuard Agent pipeline is **actively running** and producing data. They check agent log freshness, backend health, anomaly log activity, collector module integrity, and live log growth.

#### Prerequisites — Start Services First:

The agent tests require the pipeline to be running. Open **2 separate terminals** and start services in order:

**Terminal 1 — MetricGuard Agent:**
```bash
cd devops/agent/
python main.py
```

**Terminal 2 — Real-Time AI Detection (optional, for anomaly log tests):**
```bash
cd devops/monitoring/
python realtime_ai_detection.py
```

Wait ~30 seconds for data to accumulate, then run the tests:

**Terminal 3 — Run Tests:**
```bash
cd devops/
python -m pytest testing/agent_test.py -v
```

#### Run specific categories:

```bash
python -m pytest testing/agent_test.py::TestAgentLogHealth -v
python -m pytest testing/agent_test.py::TestBackendHealth -v
python -m pytest testing/agent_test.py::TestAnomalyLogging -v
python -m pytest testing/agent_test.py::TestCollectorModule -v
python -m pytest testing/agent_test.py::TestAgentLogActivity -v
python -m pytest testing/agent_test.py::TestLiveAgentCycle -v
```

| Test Class | Purpose |
|-----------|---------|
| `TestAgentLogHealth` | Checks `agent.log` exists, is non-empty, is fresh, and contains collection entries |
| `TestBackendHealth` | Verifies `/health` and `POST /metrics` endpoints respond correctly |
| `TestAnomalyLogging` | Validates `anomaly_logs.csv` structure and data |
| `TestCollectorModule` | Confirms `MetricCollector` imports and `collect()` returns valid data |
| `TestAgentLogActivity` | Checks `agent.log` exists and is recently modified |
| `TestLiveAgentCycle` | Observes `agent.log` for 35 seconds to confirm new entries arrive |

>   **Note:** Backend-dependent tests are automatically **skipped** (not failed) if the backend service is unavailable. Freshness and live-cycle tests will **fail** if the MetricGuard Agent is not actively running — this is intentional behavior used to detect inactive agent pipelines.

### 3. Testing the Log Collection Pipeline

To verify the log collection pipeline end-to-end:

1. Start the backend (`uvicorn app.main:app --port 8000`).
2. Start the agent (`python agent/main.py`).
3. Append test lines to a watched log file:
   ```bash
   echo "2026-06-05 22:30:00 ERROR Database timeout" >> agent/watched_logs/database.log
   ```
4. Check the agent console for:
   ```
   INFO — Read 1 new line(s) from database.log
   INFO — Sent 1/1 log entries from database.log
   ```
5. Query the backend:
   ```bash
   curl http://localhost:8000/logs/
   curl "http://localhost:8000/logs/?level=ERROR"
   curl "http://localhost:8000/logs/?service_name=database-service"
   ```

> 📖 For API testing, see [`testing/api_test.md`](testing/api_test.md)
>
> 📖 For integration testing, see [`testing/integration_test.md`](testing/integration_test.md)

---

## Deployment Guides

| Guide | Description |
|-------|-------------|
| [`docker_deployment.md`](deployment/docker_deployment.md) | Deploy with Docker Compose (recommended) |
| [`render_setup.md`](deployment/render_setup.md) | Deploy to Render.com cloud |
| [`tidb_cloud_setup.md`](deployment/tidb_cloud_setup.md) | Database setup reference guide |

---

## Integration with Other Modules

### For the Backend Team (Member 2)

The MetricGuard Agent sends data to two endpoints:

**Metrics Endpoint:**
```
POST /metrics
```
- Content-Type: `application/json`
- Body: JSON object with 10 metrics + `timestamp` + `agent_name`
- Expected response: `200` or `201` with confirmation JSON

**Logs Endpoint:**
```
POST /logs
```
- Content-Type: `application/json`
- Body: JSON object with `timestamp`, `level`, `message`, `service_name`
- Expected response: `201` with confirmation JSON

**Query Logs:**
```
GET /logs/?level=ERROR&service_name=database-service&start_date=2026-06-05T00:00:00
```

### For the ML Team (Member 3)

Metrics are stored in the MySQL-compatible TiDB Cloud database in the `metrics` table. The ML model can query via the backend API or directly:

```python
db.query(Metric).order_by(desc(Metric.timestamp)).limit(100).all()
```

Logs are available in the `logs` table for log-based anomaly detection (future phases).

### For the Frontend Team (Member 1)

The backend exposes metrics and logs via its REST API. The frontend does not interact with the agent directly.

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ModuleNotFoundError: psutil` | Dependencies not installed | Run `pip install -r agent/requirements.txt` |
| `ModuleNotFoundError: yaml` | PyYAML not installed | Run `pip install pyyaml` |
| `ModuleNotFoundError: watchdog` | watchdog not installed | Run `pip install watchdog pygtail` |
| `ConnectionRefusedError` | Backend not running | Start the backend first; the agent retries automatically |
| Agent crashes | Should not happen (catch-all in place) | Check `agent/logs/agent.log` for full traceback |
| No logs appearing | Log directory missing | Agent creates `logs/` automatically; check permissions |
| Docker build fails | Missing files or wrong path | Ensure you run from `devops/` root |
| Port 5000 in use | Another service on port 5000 | Change port in `docker-compose.yml` |
| `psutil.getloadavg()` returns null | Normal on Windows | Load average is Linux/Mac only; set `system_load: false` in config |
| Log collector not detecting changes | watchdog issue | Ensure the files are in a directory (not root); check `log_watch_files` paths |
| Duplicate log entries after restart | Offset file corrupted | Delete `.offsets/` directory and restart the agent |
| `config.yaml` not loading | Malformed YAML | Agent logs a warning and uses defaults; check YAML syntax |
| Metrics not collected | Metric toggled off | Check `enabled_metrics` in `config.yaml` |

---

## Deprecated Legacy Architecture

> ⚠️ **The `monitoring/` directory contains the original implementation and is now deprecated. The `agent/` directory is the active, production-ready system.**

### Original Implementation

The project originally used a single-file monitoring architecture located at:

```
devops/monitoring/metric_collector.py
```

This was a **collector-centric, monolithic design** built during the initial development phase. It combined metric collection, backend communication, retry logic, and the main loop in a single 538-line file. Configuration was managed through environment variables and a `.env` file.

### Why It Was Replaced

| Limitation | Impact |
|---|---|
| **Monolithic design** | Collection, sending, and orchestration mixed in one file — hard to maintain, test, or extend |
| **No modularity** | Adding log collection would have required rewriting the entire file |
| **Environment-variable config** | No config file, no validation, no defaults — fragile in production |
| **Global state** | Disk/network I/O baselines tracked in module-level `global` variables |
| **No log monitoring** | No pipeline for collecting and shipping application logs |
| **No metric toggles** | All 10 metrics always collected — no way to disable one without editing code |
| **No graceful shutdown** | Only `KeyboardInterrupt` — no SIGTERM support for Docker stops |
| **No agent identity** | No `agent_name` in payloads — backend can't distinguish hosts |

### Architecture Comparison

| Aspect | Legacy (`monitoring/`) | Agent (`agent/`) |
|---|---|---|
| **Architecture** | Monolithic single-file | 6 focused modules |
| **Entry point** | `metric_collector.py` | `main.py` |
| **Configuration** | Environment variables / `.env` | YAML file with validation |
| **Config safety** | Mutable class attributes | Frozen dataclass (immutable) |
| **Global state** | 4 module-level globals for I/O baselines | Instance variables on `MetricCollector` |
| **Metric toggles** | None — all metrics always collected | Per-metric on/off in YAML |
| **Agent identity** | Not in payload | `agent_name` in every payload |
| **Log collection** | ❌ Not supported | ✅ watchdog + pygtail pipeline |
| **Shutdown** | Only `KeyboardInterrupt` | SIGINT + SIGTERM signal handlers |
| **Logger init** | At import time (circular risk) | Explicitly after config is loaded |
| **Retry logic** | In `metric_collector.py` | Isolated in `sender.py` with shared `_post_with_retry()` |
| **Docker entrypoint** | `python metric_collector.py` | `python main.py` |
| **Backend URL default** | `http://localhost:5000/metrics` | `http://localhost:8000/metrics` (configurable) |

### Migration Notes

The legacy `monitoring/` directory is **retained for historical reference and architecture evolution documentation**. The active production system is `agent/`. To migrate:

| Step | Action |
|---|---|
| 1 | Install new dependencies: `pip install -r agent/requirements.txt` |
| 2 | Edit `agent/config.yaml` with your backend URL and preferences |
| 3 | Run `python agent/main.py` instead of `python monitoring/metric_collector.py` |
| 4 | Verify agent logs appear in `agent/logs/agent.log` |
| 5 | Once confident, stop the legacy collector |
| 6 | Update Docker entrypoint to `python main.py` if not already done |

### Project Structure (Evolution View)

```
devops/
├── agent/           ✅  ACTIVE   — Production-ready modular agent (Phase 6+7)
├── monitoring/      ⚠️  DEPRECATED — Original single-file collector (Phase 1-5)
├── docker/          ✅  ACTIVE   — Updated for agent/ entrypoint
├── testing/         ✅  ACTIVE   — Test suites
└── deployment/      ✅  ACTIVE   — Deployment guides
```

---

## Team Responsibilities

| Member | Role | Handles |
|--------|------|---------|
| Member 1 | Frontend | Dashboard, UI, real-time charts |
| Member 2 | Backend | REST API, MySQL/TiDB Cloud CRUD, WebSocket |
| Member 3 | ML/AI | Anomaly detection model, training, RCA |
| **Member 4** | **DevOps** | **MetricGuard Agent, Docker, monitoring, log collection, deployment, testing** |

---

## License

This project is for educational purposes as part of the MetricGuard mini project.

---

*Built with ❤️ by the MetricGuard DevOps Team*
