import time
import json
import os
import numpy as np
import pandas as pd
import joblib
import psutil
import requests

from collections import deque
from datetime import datetime

import tensorflow as tf

# =========================================================
# PATH CONFIGURATION
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

METRICS_FILE = os.path.abspath(
    os.path.join(BASE_DIR, "..", "..", "metrics.json")
)

# --- Isolation Forest paths ---
ISO_MODEL_PATH = os.path.join(
    BASE_DIR, "..", "models",
    "isolation_forest", "isolation_forest_model.pkl"
)

ISO_SCALER_PATH = os.path.join(
    BASE_DIR, "..", "models",
    "isolation_forest", "scaler.pkl"
)

# --- Multivariate Autoencoder paths ---
AE_MODEL_PATH = os.path.join(
    BASE_DIR, "..", "models",
    "encoder", "metricguard_phase4.h5"
)

AE_SCALER_PATH = os.path.join(
    BASE_DIR, "..", "models",
    "encoder", "bitbrains_scaler.pkl"
)

# --- Log paths ---
ANOMALY_LOG_FILE = os.path.join(
    BASE_DIR, "..", "logs", "anomaly_logs.csv"
)

RCA_LOG_FILE = os.path.join(
    BASE_DIR, "..", "logs", "rca_logs.json"
)

# Ensure logs directory exists
os.makedirs(os.path.dirname(ANOMALY_LOG_FILE), exist_ok=True)

# =========================================================
# CONFIGURATION
# =========================================================

SEQUENCE_LENGTH = 30

COLLECTION_INTERVAL = 5

FEATURE_COUNT = 9

# Autoencoder anomaly threshold (overall MSE above this = anomaly)
AE_THRESHOLD = 0.01

# =========================================================
# RCA FEATURE MAPPING
# =========================================================
# The 9 features expected by the Multivariate Autoencoder
# (trained on the BitBrains dataset):
#
# Index 0 : CPU capacity provisioned [MHZ]
# Index 1 : CPU usage [MHZ]
# Index 2 : CPU usage [%]
# Index 3 : Memory capacity provisioned [KB]
# Index 4 : Memory usage [KB]
# Index 5 : Disk read throughput [KB/s]
# Index 6 : Disk write throughput [KB/s]
# Index 7 : Network received throughput [KB/s]
# Index 8 : Network transmitted throughput [KB/s]

FEATURES = [
    "CPU Usage",
    "Memory Usage",
    "Disk Usage",
    "Network Usage"
]

FEATURE_INDEX_TO_CATEGORY = {
    0: "CPU Usage",
    1: "CPU Usage",
    2: "CPU Usage",
    3: "Memory Usage",
    4: "Memory Usage",
    5: "Disk Usage",
    6: "Disk Usage",
    7: "Network Usage",
    8: "Network Usage",
}

# =========================================================
# UTILITIES
# =========================================================

def parse_speed_string(speed_str):
    """
    Convert a formatted speed string (e.g. '4.39 MB', '200 KB')
    back to a numeric value in KB.

    Args:
        speed_str (str): Formatted speed string.

    Returns:
        float: Value in KB.
    """
    if not speed_str or not isinstance(speed_str, str):
        return 0.0

    try:
        parts = speed_str.strip().split()
        if len(parts) != 2:
            return 0.0

        value = float(parts[0])
        unit = parts[1].upper()

        if unit == "B":
            return value / 1024.0
        elif unit == "KB":
            return value
        elif unit == "MB":
            return value * 1024.0
        elif unit == "GB":
            return value * 1024.0 * 1024.0
        elif unit == "TB":
            return value * 1024.0 * 1024.0 * 1024.0
        else:
            return 0.0
    except (ValueError, IndexError):
        return 0.0


def get_backend_response_time():
    """
    Measure real-time HTTP response time of the backend in milliseconds.
    If the backend is not running or unreachable, falls back to the
    training mean.
    """
    try:
        from config import Config
        url = Config.BACKEND_URL
    except Exception:
        url = "http://localhost:5000/metrics"

    health_url = url.replace("/metrics", "/health")
    try:
        start_time = time.time()
        response = requests.get(health_url, timeout=1.0)
        if response.ok:
            return (time.time() - start_time) * 1000.0
    except Exception:
        pass

    # Fallback to training mean
    return 2357.75


def extract_ae_features(metrics):
    """
    Extract the 9 features required by the Multivariate Autoencoder
    from live system metrics.

    Returns:
        np.array: Shape (9,) with the raw feature values.
    """
    # CPU capacity provisioned [MHZ]
    try:
        freq = psutil.cpu_freq()
        cpu_max_mhz = (
            freq.max if freq and freq.max > 0 else 2500.0
        )
    except Exception:
        cpu_max_mhz = 2500.0

    cpu_count = psutil.cpu_count(logical=True)
    cpu_capacity_mhz = cpu_max_mhz * cpu_count

    # CPU usage [%]
    cpu_usage_pct = metrics.get("cpu_usage", 0.0)

    # CPU usage [MHZ]
    cpu_usage_mhz = cpu_capacity_mhz * (cpu_usage_pct / 100.0)

    # Memory capacity provisioned [KB]
    mem = psutil.virtual_memory()
    memory_capacity_kb = mem.total / 1024.0

    # Memory usage [KB]
    memory_usage_kb = mem.used / 1024.0

    # Disk read / write throughput [KB/s]
    # The collector stores total bytes-per-interval;
    # divide by interval to approximate KB/s
    disk_read_kb_s = (
        parse_speed_string(
            metrics.get("disk_read_speed", "0.00 B")
        ) / COLLECTION_INTERVAL
    )
    disk_write_kb_s = (
        parse_speed_string(
            metrics.get("disk_write_speed", "0.00 B")
        ) / COLLECTION_INTERVAL
    )

    # Network throughput [KB/s]
    net_recv_kb_s = (
        parse_speed_string(
            metrics.get("network_download_speed", "0.00 B")
        ) / COLLECTION_INTERVAL
    )
    net_trans_kb_s = (
        parse_speed_string(
            metrics.get("network_upload_speed", "0.00 B")
        ) / COLLECTION_INTERVAL
    )

    return np.array([
        cpu_capacity_mhz,
        cpu_usage_mhz,
        cpu_usage_pct,
        memory_capacity_kb,
        memory_usage_kb,
        disk_read_kb_s,
        disk_write_kb_s,
        net_recv_kb_s,
        net_trans_kb_s,
    ])

# =========================================================
# LOAD ISOLATION FOREST
# =========================================================

print("\nLoading Isolation Forest Model...")

isolation_forest = joblib.load(ISO_MODEL_PATH)
iso_scaler = joblib.load(ISO_SCALER_PATH)

print("Isolation Forest Loaded")

# =========================================================
# LOAD MULTIVARIATE AUTOENCODER
# =========================================================

print("\nLoading Multivariate Autoencoder...")

ae_scaler = joblib.load(AE_SCALER_PATH)

ae_model = tf.keras.models.load_model(
    AE_MODEL_PATH, compile=False
)

print(
    f"Autoencoder Loaded — "
    f"Input: {ae_model.input_shape}, "
    f"Output: {ae_model.output_shape}"
)

# =========================================================
# SEQUENCE BUFFER
# =========================================================

sequence_buffer = deque(maxlen=SEQUENCE_LENGTH)

# =========================================================
# ROOT CAUSE ANALYSIS
# =========================================================

def perform_rca(actual_scaled, reconstructed_scaled):
    """
    Perform Root Cause Analysis by computing feature-wise
    reconstruction errors and mapping them to metric categories.

    Args:
        actual_scaled:        np.array (1, SEQUENCE_LENGTH, 9)
        reconstructed_scaled: np.array (1, SEQUENCE_LENGTH, 9)

    Returns:
        tuple: (root_cause, category_errors, top_contributors)
    """
    # Feature-wise MSE across time steps — shape (9,)
    feature_error = np.mean(
        np.square(actual_scaled - reconstructed_scaled),
        axis=(0, 1)
    )

    # Aggregate 9 feature errors into 4 categories
    category_errors = {}
    for cat in FEATURES:
        indices = [
            i for i, c in FEATURE_INDEX_TO_CATEGORY.items()
            if c == cat
        ]
        category_errors[cat] = float(
            np.mean(feature_error[indices])
        )

    # Identify root cause (highest category error)
    root_cause = max(
        category_errors,
        key=category_errors.get
    )

    # Top contributors sorted descending by error
    top_contributors = sorted(
        category_errors.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    return root_cause, category_errors, top_contributors


def save_rca_result(rca_event):
    """
    Append an RCA event to the local JSON log file.
    """
    try:
        if os.path.exists(RCA_LOG_FILE):
            with open(RCA_LOG_FILE, "r") as f:
                rca_history = json.load(f)
        else:
            rca_history = []

        rca_history.append(rca_event)

        with open(RCA_LOG_FILE, "w") as f:
            json.dump(rca_history, f, indent=4)

    except Exception as e:
        print(f"Error saving RCA result: {e}")


def post_rca_to_backend(rca_event):
    """
    POST the RCA event to the backend API for dashboard access.
    """
    try:
        from config import Config
        url = Config.BACKEND_URL.replace(
            "/metrics", "/api/rca"
        )
    except Exception:
        url = "http://localhost:5000/api/rca"

    try:
        response = requests.post(
            url,
            json=rca_event,
            timeout=5,
            headers={"Content-Type": "application/json"},
        )
        if response.ok:
            print(
                f"RCA posted to backend "
                f"(status {response.status_code})"
            )
        else:
            print(
                f"Backend returned "
                f"{response.status_code}"
            )
    except Exception as e:
        print(f"Could not post RCA to backend: {e}")


def get_rca_statistics():
    """
    Generate aggregated RCA statistics from the local log file.

    Returns:
        dict with total_anomalies, most_frequent_root_cause,
        anomaly_count_per_metric, root_cause_distribution,
        and records.
    """
    try:
        if not os.path.exists(RCA_LOG_FILE):
            return {"total_anomalies": 0, "records": []}

        with open(RCA_LOG_FILE, "r") as f:
            rca_history = json.load(f)

        if not rca_history:
            return {"total_anomalies": 0, "records": []}

        # Count anomalies per root cause
        root_cause_counts = {}
        for event in rca_history:
            rc = event.get("root_cause", "Unknown")
            root_cause_counts[rc] = (
                root_cause_counts.get(rc, 0) + 1
            )

        most_frequent = max(
            root_cause_counts,
            key=root_cause_counts.get,
        )

        return {
            "total_anomalies": len(rca_history),
            "most_frequent_root_cause": most_frequent,
            "anomaly_count_per_metric": root_cause_counts,
            "root_cause_distribution": {
                k: round(v / len(rca_history) * 100, 2)
                for k, v in root_cause_counts.items()
            },
            "records": rca_history,
        }

    except Exception as e:
        print(f"Error computing RCA statistics: {e}")
        return {"total_anomalies": 0, "records": []}

# =========================================================
# READ LATEST METRICS
# =========================================================

def read_latest_metrics():

    with open(METRICS_FILE, "r") as file:

        data = json.load(file)

    latest = data[-1]

    # Map the metric keys to match the schema generated
    # by metric_collector.py
    metrics = {
        "cpu_usage": latest.get("cpu_usage", 0.0),
        "ram_usage": latest.get("ram_usage", 0.0),
        "disk_usage": latest.get("disk_usage", 0.0),
        "disk_read_speed": latest.get(
            "disk_read_speed", "0.00 B"
        ),
        "disk_write_speed": latest.get(
            "disk_write_speed", "0.00 B"
        ),
        "network_upload_speed": latest.get(
            "network_upload_speed", "0.00 B"
        ),
        "network_download_speed": latest.get(
            "network_download_speed", "0.00 B"
        ),
        "process_count": latest.get("process_count", 0),
        "system_load": latest.get("system_load", 0.0),
        "system_uptime": latest.get(
            "system_uptime", "0h 0m 0s"
        ),
    }

    return metrics

# =========================================================
# SAVE ANOMALY
# =========================================================

def save_anomaly(
    metrics,
    iso_prediction,
    mse,
    rca_info=None,
):

    anomaly_data = {

        "timestamp":
            str(datetime.now()),

        **metrics,

        "isolation_forest_result":
            int(iso_prediction),

        "reconstruction_error":
            float(mse),
    }

    if rca_info:
        anomaly_data["root_cause"] = rca_info.get(
            "root_cause", ""
        )
        anomaly_data["top_contributors"] = str(
            rca_info.get("top_contributors", [])
        )

    df = pd.DataFrame(
        [anomaly_data]
    )

    df.to_csv(
        ANOMALY_LOG_FILE,
        mode='a',
        header=not os.path.exists(
            ANOMALY_LOG_FILE
        ),
        index=False,
    )

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("MetricGuard Real-Time AI Monitoring Started")
    print("Phase 5: Root Cause Analysis Enabled")
    print("=" * 60)

    # =========================================================
    # CONTINUOUS MONITORING LOOP
    # =========================================================

    while True:

        try:

            # =================================================
            # STEP 1 — READ LIVE METRICS
            # =================================================

            metrics = read_latest_metrics()

            print("\nLive Metrics:")
            print(metrics)

            # =================================================
            # STEP 2 — ISOLATION FOREST INFERENCE
            # =================================================

            cpu_usage_percent = metrics["cpu_usage"]
            memory_usage_mb = (
                psutil.virtual_memory().used / (1024 * 1024)
            )
            response_time_ms = get_backend_response_time()

            feature_array = np.array([
                response_time_ms,
                cpu_usage_percent,
                memory_usage_mb,
            ]).reshape(1, -1)

            iso_scaled = iso_scaler.transform(
                feature_array
            )

            iso_prediction = (
                isolation_forest.predict(
                    iso_scaled
                )[0]
            )

            if iso_prediction == -1:

                print(
                    "\n[Isolation Forest]"
                    " Potential Anomaly"
                )

            else:

                print(
                    "\n[Isolation Forest]"
                    " Normal"
                )

            # =================================================
            # STEP 3 — EXTRACT AUTOENCODER FEATURES & BUFFER
            # =================================================

            ae_features = extract_ae_features(metrics)

            # Scale using the BitBrains MinMaxScaler
            ae_scaled = ae_scaler.transform(
                ae_features.reshape(1, -1)
            )[0]

            sequence_buffer.append(ae_scaled)

            print(
                f"Sequence Buffer: "
                f"{len(sequence_buffer)}"
                f"/{SEQUENCE_LENGTH}"
            )

            # =================================================
            # STEP 4 — AUTOENCODER INFERENCE
            # =================================================

            if len(sequence_buffer) == SEQUENCE_LENGTH:

                sequence = np.array(
                    sequence_buffer
                )

                sequence = sequence.reshape(
                    1,
                    SEQUENCE_LENGTH,
                    FEATURE_COUNT,
                )

                reconstructed = (
                    ae_model.predict(
                        sequence,
                        verbose=0,
                    )
                )

                # =============================================
                # STEP 5 — RECONSTRUCTION ERROR
                # =============================================

                mse = float(
                    np.mean(
                        np.square(
                            sequence - reconstructed
                        )
                    )
                )

                print(
                    f"Autoencoder Reconstruction Error: "
                    f"{mse:.6f}"
                )

                # =============================================
                # STEP 6 — AUTOENCODER ANOMALY CHECK
                # =============================================

                ae_anomaly = (
                    mse > AE_THRESHOLD
                )

                if ae_anomaly:

                    print(
                        "\n" + "=" * 60
                    )

                    print(
                        "AUTOENCODER "
                        "ANOMALY DETECTED"
                    )

                    print(
                        f"Reconstruction Error: "
                        f"{mse:.6f}"
                    )

                    print(
                        f"Threshold: "
                        f"{AE_THRESHOLD:.6f}"
                    )

                    print(
                        "=" * 60
                    )

                # =============================================
                # STEP 7 — FINAL AI DECISION + RCA
                # =============================================

                if (
                    iso_prediction == -1
                    or
                    ae_anomaly
                ):

                    print(
                        "\n" + "#" * 60
                    )

                    print(
                        "FINAL ALERT:"
                        " SYSTEM ANOMALY DETECTED"
                    )

                    print(
                        "#" * 60
                    )

                    # -----------------------------------------
                    # ROOT CAUSE ANALYSIS
                    # -----------------------------------------

                    root_cause, category_errors, top_contributors = (
                        perform_rca(sequence, reconstructed)
                    )

                    print(f"\n{'=' * 40}")
                    print("ROOT CAUSE ANALYSIS")
                    print(f"{'=' * 40}")
                    print(f"Root Cause: {root_cause}")

                    print("\nFeature Errors:")
                    for cat, err in category_errors.items():
                        print(
                            f"  {cat:20s}: {err:.6f}"
                        )

                    print("\nTop Contributors:")
                    for rank, (cat, err) in enumerate(
                        top_contributors, 1
                    ):
                        print(
                            f"  {rank}. {cat:20s}"
                            f" ({err:.6f})"
                        )

                    print(f"{'=' * 40}")

                    # Build anomaly score
                    anomaly_score = float(
                        mse
                        if ae_anomaly
                        else abs(
                            isolation_forest.score_samples(
                                iso_scaled
                            )[0]
                        )
                    )

                    # Build RCA event
                    rca_event = {
                        "timestamp": str(datetime.now()),
                        "anomaly": True,
                        "anomaly_score": anomaly_score,
                        "root_cause": root_cause,
                        "feature_errors": category_errors,
                        "top_contributors": [
                            {"metric": cat, "error": err}
                            for cat, err in top_contributors
                        ],
                        "isolation_forest_result": int(
                            iso_prediction
                        ),
                        "reconstruction_error": float(mse),
                    }

                    # Save locally
                    save_rca_result(rca_event)

                    # Post to backend
                    post_rca_to_backend(rca_event)

                    # Save anomaly CSV
                    save_anomaly(
                        metrics,
                        iso_prediction,
                        mse,
                        rca_event,
                    )

                else:

                    print(
                        "\nSystem Operating Normally"
                    )

            # =================================================
            # WAIT FOR NEXT COLLECTION
            # =================================================

            time.sleep(
                COLLECTION_INTERVAL
            )

        except KeyboardInterrupt:

            print(
                "\nMonitoring Stopped"
            )

            # Print RCA statistics on exit
            stats = get_rca_statistics()
            if stats["total_anomalies"] > 0:
                print(f"\n{'=' * 40}")
                print("RCA STATISTICS SUMMARY")
                print(f"{'=' * 40}")
                print(
                    f"Total Anomalies: "
                    f"{stats['total_anomalies']}"
                )
                print(
                    f"Most Frequent Root Cause: "
                    f"{stats.get('most_frequent_root_cause', 'N/A')}"
                )
                if "anomaly_count_per_metric" in stats:
                    print("\nAnomalies per Metric:")
                    for metric, count in stats[
                        "anomaly_count_per_metric"
                    ].items():
                        print(
                            f"  {metric:20s}: "
                            f"{count} anomalies"
                        )
                print(f"{'=' * 40}")

            break

        except Exception as e:

            print(
                f"\nError Occurred: {e}"
            )

            time.sleep(
                COLLECTION_INTERVAL
            )