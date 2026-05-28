# 🛡️ MetricGuard Anomaly Detection Platform

MetricGuard is an AI-powered real-time system monitoring and anomaly detection platform. It collects system resource metrics, transmits them to a central backend API, and applies a dual-model machine learning pipeline (Isolation Forest + LSTM Autoencoder) to detect instant point anomalies and temporal sequence trends.

---

## 📂 Project Structure

```
MetricGuard/
│
├── devops/
│   ├── models/                  # ML models & scaler binary files (Ignored in Git)
│   ├── logs/                    # Runtime logs & anomaly csv dumps
│   │   ├── system.log
│   │   └── anomaly_logs.csv
│   │
│   ├── monitoring/              # Collection and Detection code
│   │   ├── config.py
│   │   ├── logger.py
│   │   ├── metric_collector.py  # Collects system metrics & writes to metrics.json
│   │   ├── test_backend.py      # Mock API backend for testing
│   │   ├── requirements.txt     # Python requirements
│   │   ├── integration_guide.md # Integration docs
│   │   └── realtime_ai_detection.py # Runs point & trend AI detection loop
│   │
│   └── testing/                 # Anomaly simulation & stress tests
│       └── anomaly_test.py
│
├── metrics.json                 # Shared file holding the rolling live metric buffer
└── README.md                    # This file
```

---

## 🧠 ML Model Setup & Download (Important)

Due to file size limits, binary machine learning model weights are ignored from version control (Git). 

> [!IMPORTANT]
> Download the pre-trained models and scalers from the Google Drive link below, and place all 5 files directly in the `devops/models/` directory:
> 
> 👉 **[Download MetricGuard ML Models (Google Drive Link Placeholder)] https://drive.google.com/drive/folders/1tqSjdgNn7fHwVl4YJHjdnZwWyd2xUHLK?usp=sharing **

### Required Model Files:

| Filename | Type | Description |
|----------|------|-------------|
| `isolation_forest_model.pkl` | Joblib Pickle | Trained Isolation Forest estimator |
| `scaler.pkl` | Joblib Pickle | `StandardScaler` for Isolation Forest features |
| `scaler.save` | Joblib Pickle | `MinMaxScaler` for scaling LSTM CPU features |
| `threshold.save` | Joblib Pickle | Float reconstruction threshold value for LSTM |
| `lstm_autoencoder.weights.h5` | Keras H5 | Layer weights for the 4-layer LSTM Autoencoder |

### Recreating the LSTM Model Architecture
The weights in `lstm_autoencoder.weights.h5` expect a specific nested Sequential model topology built as:
* **Encoder**: `Sequential([LSTM(128, return_sequences=True), LSTM(64, return_sequences=False)])`
* **Decoder**: `Sequential([RepeatVector(10), LSTM(64, return_sequences=True), LSTM(128, return_sequences=True), TimeDistributed(Dense(1))])`

---

## 🚀 Setup & Execution Guide

Follow these steps to configure your environment and run the pipeline locally.

### Step 1: Clone the Repository
Clone the repository to your local system and navigate to the project directory:

```bash
# Via HTTPS
git clone https://github.com/Siddharth-Pattanshetty/MetricGuard.git
cd MetricGuard

# Or via SSH
git clone git@github.com:Siddharth-Pattanshetty/MetricGuard.git
cd MetricGuard
```

### Step 2: Install Dependencies
Create a virtual environment, activate it, and install all required monitoring and machine learning dependencies:

```powershell
# Create venv
python -m venv venv

# Activate venv (Windows PowerShell)
venv\Scripts\activate

# Install requirements
pip install -r devops/monitoring/requirements.txt
```

### Step 3: Download and Place Models
Download the 5 files from the Google Drive link above and copy them into the `devops/models/` folder.

### Step 4: Start Mock Backend
Start the mock API backend server (running on `http://localhost:5000`) to handle metric collection pings and response-time measurements:

```powershell
python devops/monitoring/test_backend.py
```

### Step 5: Run the Metric Collector
In a separate terminal (with virtual environment active), start the live metric collector. This script records 10 metrics every 5 seconds and updates the local buffer in `metrics.json`:

```powershell
python devops/monitoring/metric_collector.py
```

### Step 6: Run Real-time AI Anomaly Detection
In a third terminal (with virtual environment active), launch the AI detection engine. This script will load the ML models, stream live data from the collector, perform point and trend anomaly inference, and trigger alerts:

```powershell
python devops/monitoring/realtime_ai_detection.py
```

---

## 🧪 Testing & Validation

MetricGuard comes with an automated stress and anomaly simulation suite. To stress-test your local system (spiking CPU/RAM workloads) and verify that the collector captures the anomalies correctly, run:

```powershell
python -m pytest devops/testing/anomaly_test.py -v
```
