# 🔗 MetricGuard — Pipeline & Model Integration Guide

This guide explains how the **Metric Collection Pipeline** integrates with the **AI Anomaly Detection Models** in MetricGuard. It outlines the data flow, feature mapping, preprocessing steps, and the ensemble decision logic.

---

## 🏗️ Architecture & Data Flow

The monitoring system consists of three main components:
1. **Metric Collector (`metric_collector.py`)**: Gathers live system metrics every 5 seconds and writes them to a shared local database file (`metrics.json`).
2. **Backend API (`test_backend.py`)**: Receives the metrics via HTTP POST to persist them database-side (simulated in our dev pipeline).
3. **AI Anomaly Detection (`realtime_ai_detection.py`)**: Connects to the metric collection pipeline by consuming the shared `metrics.json` and feeding the processed features into trained machine learning models.

```
┌─────────────────────────┐
│     System OS/HW        │
└───────────┬─────────────┘
            │ psutil
            ▼
┌─────────────────────────┐
│   metric_collector.py   │
└───────────┬─────────────┘
            ├─────────────────────────────────────────┐
            │ writes to                               │ HTTP POST
            ▼                                         ▼
┌─────────────────────────┐                  ┌─────────────────┐
│      metrics.json       │                  │  Backend API    │
└───────────┬─────────────┘                  │  (Port 5000)    │
            │ reads latest                    └────────┬────────┘
            ▼                                          │ health check
┌─────────────────────────┐                            │ response time
│ realtime_ai_detection.py│◀───────────────────────────┘
└───────────┬─────────────┘
            ├─────────────────────────┐
            ▼                         ▼
┌─────────────────────────┐ ┌─────────────────────────┐
│  Isolation Forest (ML)  │ │  LSTM Autoencoder (DL)  │
│  - Spot point anomalies │ │  - Spot trend anomalies │
└───────────┬─────────────┘ └─────────┬───────────────┘
            └────────────┬────────────┘
                         ▼
             [ FINAL ENSEMBLE ALERT ]
                         │ logs to
                         ▼
              anomaly_logs.csv
```

---

## 🛠️ Model Connections & Feature Engineering

### 1. Isolation Forest (Point Anomaly Detection)
The Isolation Forest model is designed to catch instant, severe point anomalies (such as a sudden bottleneck). It requires **3 features**:

* **Feature 1: `response_time_ms`**
  - *Pipeline Connection*: Calculated dynamically by the detection engine. It issues a fast HTTP GET ping to the backend's `/health` endpoint and records the round-trip latency in milliseconds.
  - *Offline Fallback*: If the backend API is unreachable, it automatically falls back to the training baseline mean of `2357.75` ms to avoid breaking model distribution shapes.
* **Feature 2: `cpu_usage_percent`**
  - *Pipeline Connection*: Loaded from the `"cpu_usage"` key in the latest cycle of `metrics.json`.
* **Feature 3: `memory_usage_mb`**
  - *Pipeline Connection*: Computed using `psutil.virtual_memory().used` divided by `1024 * 1024` to convert system bytes into Megabytes.

*Data Scaling*: These 3 features are reshaped into an array `[[response_time, cpu, memory]]` and normalized using a pre-saved Standard Scaler (`scaler.pkl`) before inference.

---

### 2. LSTM Autoencoder (Temporal Trend Anomaly Detection)
The Long Short-Term Memory (LSTM) Autoencoder detects sequential anomalies (e.g. resource leaks or CPU load that hangs high over a longer period). It evaluates a time-series window:

* **Sequence Buffer**: A rolling FIFO queue (`collections.deque`) of length `10`.
* **Feature Evaluated**: `[cpu_usage_percent]`.
* **Flow**:
  1. The latest `cpu_usage_percent` is scaled using a MinMaxScaler (`scaler.save`).
  2. The scaled value is appended to the sequence buffer.
  3. Until the buffer has 10 elements (after the first 50 seconds of runtime), the LSTM does not execute.
  4. Once `len(buffer) == 10`, the sequence is reshaped to shape `(1, 10, 1)` and fed into the model.
  5. The model outputs a reconstructed sequence of shape `(1, 10, 1)`.
  6. The **Mean Squared Error (MSE)** reconstruction loss is calculated:
     $$\text{MSE} = \frac{1}{10}\sum_{i=1}^{10}(x_i - \hat{x}_i)^2$$
  7. If the reconstruction error exceeds the trained threshold (`0.025853`), it flags a sequence anomaly.

---

## 🤝 Preprocessing & Value Parsing

Metrics written by the collector contain formatted string speeds (e.g., `"257.17 MB"`, `"47.07 KB"`). To facilitate downstream processing and potential feature expansion:
- The detection pipeline uses a mapping utility in `read_latest_metrics` to ensure all key structures are matched.
- Speeds can be stripped of their units and converted to numeric floats (in KB or MB) if any additional models require raw speeds.

---

## 🚨 Ensemble Decision Logic

The final alert is triggered using an **OR logic** gate to maximize sensitivity to different threat vectors:

$$\text{Alert} = (\text{Isolation Forest Prediction} == -1) \lor (\text{LSTM Reconstruction Loss} > \text{Threshold})$$

When an alert is raised:
1. It prints a warning to the console stdout: `FINAL ALERT: SYSTEM ANOMALY DETECTED`.
2. The complete metric snapshot along with the Isolation Forest prediction and LSTM MSE error is appended to `devops/logs/anomaly_logs.csv` for downstream alerting.
