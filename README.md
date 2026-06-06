# 🛡️ MetricGuard Anomaly Detection Platform

MetricGuard is an AI-powered real-time system monitoring and anomaly detection platform. It collects live system metrics, transmits them to a centralized Backend API, and applies a dual-model machine learning pipeline (Isolation Forest + LSTM Autoencoder) to detect both instant point anomalies and long-term temporal behavior anomalies.

---

# 📂 Project Structure

```text id="1bpt7y"
MetricGuard/
│
├── devops/
│   ├── models/                  # ML models & scaler binary files (Ignored in Git)
│   │
│   ├── logs/                    # Runtime logs & anomaly CSV dumps
│   │   ├── system.log
│   │   └── anomaly_logs.csv
│   │
│   ├── agent/                   # ✅ ACTIVE — Production-ready modular monitoring agent
│   │   ├── main.py              # Entry point (start the agent here)
│   │   ├── collector.py         # System metric collection using psutil
│   │   ├── sender.py            # HTTP communication with backend APIs
│   │   ├── log_collector.py     # Log monitoring via watchdog + pygtail
│   │   ├── config.yaml          # YAML runtime configuration
│   │   └── requirements.txt     # Active Python dependencies
│   │
│   ├── monitoring/              # ⚠️ DEPRECATED — Legacy collector-centric architecture
│   │   ├── metric_collector.py  # Legacy single-file collector
│   │   ├── realtime_ai_detection.py # Transitional AI anomaly detection pipeline
│   │   ├── integration_guide.md # Legacy-to-agent integration reference
│   │   ├── test_backend.py      # Mock backend utility for local testing
│   │   ├── config.py
│   │   ├── logger.py
│   │   └── requirements.txt
│   │
│   ├── testing/                 # Stress tests & anomaly validation suite
│   │   └── anomaly_test.py
│   │
│   └── deployment/              # Deployment & infrastructure documentation
│
└── README.md
```

---

# 🧠 ML Model Setup & Download (Important)

Due to file size limitations, binary machine learning model weights are excluded from version control.

> [!IMPORTANT]
> Download the pre-trained models and scaler files from the Google Drive link below and place them inside the corresponding subfolders within:
>
> ```text
> devops/models/
> ```
>
> 👉 **Download MetricGuard ML Models:**
> https://drive.google.com/drive/folders/1tqSjdgNn7fHwVl4YJHjdnZwWyd2xUHLK?usp=sharing

---

## Required Model Files & Subdirectories

### 1. Isolation Forest Model (`devops/models/isolation_forest/`)

* `isolation_forest_model.pkl`

  * Trained Isolation Forest estimator

* `scaler.pkl`

  * `StandardScaler` used for feature normalization during inference

---

### 2. Multivariate Autoencoder Model (`devops/models/encoder/`)

* `metricguard_phase4.h5`

  * Trained Keras Multivariate Autoencoder model

* `bitbrains_scaler.pkl`

  * `MinMaxScaler` used for sequence feature scaling

> [!NOTE]
> The autoencoder model is loaded directly using:
>
> ```python id="pjlwm0"
> tf.keras.models.load_model(..., compile=False)
> ```
>
> Rebuilding the architecture programmatically is not required.

---

# 🚀 Setup & Execution Guide

Follow these steps to configure and run the platform locally.

---

## Step 1: Clone the Repository

Clone the repository and navigate to the project directory.

```bash id="zjlwm2"
# Via HTTPS
git clone https://github.com/Siddharth-Pattanshetty/MetricGuard.git
cd MetricGuard

# Or via SSH
git clone git@github.com:Siddharth-Pattanshetty/MetricGuard.git
cd MetricGuard
```

---

## Step 2: Create Virtual Environment & Install Dependencies

```powershell id="7h3q4n"
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows PowerShell)
venv\Scripts\activate

# Install dependencies
pip install -r devops/agent/requirements.txt
```

---

## Step 3: Download and Place ML Models

Download the required model files from the Google Drive link above and place them inside the appropriate directories under:

```text id="v81lh7"
devops/models/
```

---

## Step 4: Run the MetricGuard Agent

In a separate terminal (with the virtual environment active), start the active MetricGuard Agent runtime:

```powershell id="c7yuzm"
python devops/agent/main.py
```

The agent:

* collects live system metrics
* monitors configured application logs
* transmits metrics and logs to the Backend API
* powers the downstream AI detection workflow

---

## Step 5: Run Real-time AI Anomaly Detection

In another terminal (with the virtual environment active), launch the AI anomaly detection engine:

```powershell id="v7t7fu"
python devops/monitoring/realtime_ai_detection.py
```

The AI pipeline:

* consumes monitoring metrics from the active agent-driven pipeline
* performs preprocessing and feature engineering
* executes Isolation Forest and LSTM Autoencoder inference
* triggers anomaly alerts and RCA workflows

> [!NOTE]
> `realtime_ai_detection.py` currently retains transitional compatibility with portions of the legacy monitoring architecture during migration.
>
> The primary active monitoring runtime is:
>
> ```text
> devops/agent/
> ```

---

# 🧪 Testing & Validation

MetricGuard includes anomaly simulation and stress-testing utilities for validating:

* monitoring accuracy
* anomaly detection behavior
* backend communication stability
* runtime resilience

To run the anomaly simulation suite:

```powershell id="w8hs1r"
python -m pytest devops/testing/anomaly_test.py -v
```

These tests help validate:

* metric collection stability
* anomaly capture accuracy
* backend communication flow
* AI-triggered alert behavior

---

# 📌 Core Technologies

MetricGuard combines:

* Python
* psutil
* Flask-compatible backend APIs
* TensorFlow / Keras
* scikit-learn
* Isolation Forest
* LSTM Autoencoders
* Watchdog log monitoring
* Docker-based deployment workflows
* MySQL-compatible TiDB Cloud infrastructure

to create a modular production-oriented observability and anomaly detection platform.

---

# ⚠️ Legacy Architecture Notice

The following directory is now considered deprecated:

```text id="vqk0yl"
devops/monitoring/
```

It is retained only for:

* historical reference
* transitional AI/RCA compatibility
* migration support

All new deployments, runtime execution, and active monitoring workflows should use:

```text id="ob4m0m"
devops/agent/
```