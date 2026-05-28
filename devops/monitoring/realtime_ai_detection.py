import time
import json
import os
import numpy as np
import pandas as pd
import joblib
import psutil
import requests
import h5py

from collections import deque
from datetime import datetime

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import (
    LSTM,
    RepeatVector,
    TimeDistributed,
    Dense
)

# =========================================================
# PATH CONFIGURATION
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

METRICS_FILE = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "metrics.json"))

ISO_MODEL_PATH = os.path.join(
    BASE_DIR, "..", "models", "isolation_forest_model.pkl"
)

ISO_SCALER_PATH = os.path.join(
    BASE_DIR, "..", "models", "scaler.pkl"
)

LSTM_SCALER_PATH = os.path.join(
    BASE_DIR, "..", "models", "scaler.save"
)

THRESHOLD_PATH = os.path.join(
    BASE_DIR, "..", "models", "threshold.save"
)

LSTM_WEIGHTS_PATH = os.path.join(
    BASE_DIR, "..", "models", "lstm_autoencoder.weights.h5"
)

ANOMALY_LOG_FILE = os.path.join(
    BASE_DIR, "..", "logs", "anomaly_logs.csv"
)

# Ensure logs directory exists
os.makedirs(os.path.dirname(ANOMALY_LOG_FILE), exist_ok=True)

# =========================================================
# CONFIGURATION
# =========================================================

SEQUENCE_LENGTH = 10

COLLECTION_INTERVAL = 5

FEATURE_COUNT = 1

# =========================================================
# UTILITIES
# =========================================================

def get_backend_response_time():
    """
    Measure real-time HTTP response time of the backend in milliseconds.
    If the backend is not running or unreachable, falls back to the training mean.
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
    
    # Fallback to training mean (2357.75 ms) to keep within expected distribution
    return 2357.75

# =========================================================
# LOAD ISOLATION FOREST
# =========================================================

print("\nLoading Isolation Forest Model...")

isolation_forest = joblib.load(
    ISO_MODEL_PATH
)

iso_scaler = joblib.load(
    ISO_SCALER_PATH
)

print("Isolation Forest Loaded")

# =========================================================
# LOAD LSTM SCALER + THRESHOLD
# =========================================================

print("\nLoading LSTM Components...")

lstm_scaler = joblib.load(
    LSTM_SCALER_PATH
)

threshold = joblib.load(
    THRESHOLD_PATH
)

print("LSTM Scaler + Threshold Loaded")

# =========================================================
# REBUILD LSTM MODEL ARCHITECTURE
# =========================================================

def build_lstm_autoencoder():
    """
    Build the LSTM Autoencoder model using the nested encoder/decoder Sequential submodels.
    This topology perfectly matches the layer weights stored in lstm_autoencoder.weights.h5.
    """
    encoder = Sequential([
        LSTM(
            128,
            activation='relu',
            input_shape=(
                SEQUENCE_LENGTH,
                1
            ),
            return_sequences=True,
            name='lstm'
        ),
        LSTM(
            64,
            activation='relu',
            return_sequences=False,
            name='lstm_1'
        )
    ], name='encoder')

    decoder = Sequential([
        RepeatVector(SEQUENCE_LENGTH, name='repeat_vector'),
        LSTM(
            64,
            activation='relu',
            return_sequences=True,
            name='lstm_2'
        ),
        LSTM(
            128,
            activation='relu',
            return_sequences=True,
            name='lstm_3'
        ),
        TimeDistributed(
            Dense(1),
            name='time_distributed'
        )
    ], name='decoder')

    model = Sequential([
        encoder,
        decoder
    ], name='lstm_autoencoder')

    return model

# =========================================================
# LOAD TRAINED LSTM WEIGHTS
# =========================================================

print("\nLoading LSTM Autoencoder Weights...")

lstm_autoencoder = build_lstm_autoencoder()

# Build the model variables before assigning weights
lstm_autoencoder(np.zeros((1, SEQUENCE_LENGTH, 1)))

try:
    with h5py.File(LSTM_WEIGHTS_PATH, 'r') as f:
        # Load encoder/layers/lstm weights
        enc_lstm_kernel = f['encoder/layers/lstm/cell/vars/0'][:]
        enc_lstm_recurrent = f['encoder/layers/lstm/cell/vars/1'][:]
        enc_lstm_bias = f['encoder/layers/lstm/cell/vars/2'][:]
        
        # Load encoder/layers/lstm_1 weights
        enc_lstm1_kernel = f['encoder/layers/lstm_1/cell/vars/0'][:]
        enc_lstm1_recurrent = f['encoder/layers/lstm_1/cell/vars/1'][:]
        enc_lstm1_bias = f['encoder/layers/lstm_1/cell/vars/2'][:]
        
        # Load decoder/layers/lstm weights
        dec_lstm_kernel = f['decoder/layers/lstm/cell/vars/0'][:]
        dec_lstm_recurrent = f['decoder/layers/lstm/cell/vars/1'][:]
        dec_lstm_bias = f['decoder/layers/lstm/cell/vars/2'][:]
        
        # Load decoder/layers/lstm_1 weights
        dec_lstm1_kernel = f['decoder/layers/lstm_1/cell/vars/0'][:]
        dec_lstm1_recurrent = f['decoder/layers/lstm_1/cell/vars/1'][:]
        dec_lstm1_bias = f['decoder/layers/lstm_1/cell/vars/2'][:]
        
        # Load decoder/layers/time_distributed weights
        dense_kernel = f['decoder/layers/time_distributed/layer/vars/0'][:]
        dense_bias = f['decoder/layers/time_distributed/layer/vars/1'][:]
        
    # Assign weights to model layers
    encoder = lstm_autoencoder.get_layer('encoder')
    decoder = lstm_autoencoder.get_layer('decoder')
    
    encoder.layers[0].set_weights([enc_lstm_kernel, enc_lstm_recurrent, enc_lstm_bias])
    encoder.layers[1].set_weights([enc_lstm1_kernel, enc_lstm1_recurrent, enc_lstm1_bias])
    
    decoder.layers[1].set_weights([dec_lstm_kernel, dec_lstm_recurrent, dec_lstm_bias])
    decoder.layers[2].set_weights([dec_lstm1_kernel, dec_lstm1_recurrent, dec_lstm1_bias])
    decoder.layers[3].set_weights([dense_kernel, dense_bias])
    
    print("LSTM Autoencoder Loaded (successfully mapped from H5)")
except Exception as e:
    print(f"Error loading LSTM weights: {e}")
    # Fallback to Keras default load_weights in case structure matches in other environments
    lstm_autoencoder.load_weights(LSTM_WEIGHTS_PATH)
    print("LSTM Autoencoder Loaded via default fallback")

# =========================================================
# SEQUENCE BUFFER
# =========================================================

sequence_buffer = deque(
    maxlen=SEQUENCE_LENGTH
)

# =========================================================
# READ LATEST METRICS
# =========================================================

def read_latest_metrics():

    with open(METRICS_FILE, "r") as file:

        data = json.load(file)

    latest = data[-1]

    # Map the metric keys to match the schema generated by metric_collector.py
    metrics = {
        "cpu_usage": latest.get("cpu_usage", 0.0),
        "ram_usage": latest.get("ram_usage", 0.0),
        "disk_usage": latest.get("disk_usage", 0.0),
        "disk_read_speed": latest.get("disk_read_speed", "0.00 B"),
        "disk_write_speed": latest.get("disk_write_speed", "0.00 B"),
        "network_upload_speed": latest.get("network_upload_speed", "0.00 B"),
        "network_download_speed": latest.get("network_download_speed", "0.00 B"),
        "process_count": latest.get("process_count", 0),
        "system_load": latest.get("system_load", 0.0),
        "system_uptime": latest.get("system_uptime", "0h 0m 0s")
    }

    return metrics

# =========================================================
# SAVE ANOMALY
# =========================================================

def save_anomaly(
    metrics,
    iso_prediction,
    mse
):

    anomaly_data = {

        "timestamp":
            str(datetime.now()),

        **metrics,

        "isolation_forest_result":
            int(iso_prediction),

        "reconstruction_error":
            float(mse)
    }

    df = pd.DataFrame(
        [anomaly_data]
    )

    df.to_csv(
        ANOMALY_LOG_FILE,
        mode='a',
        header=not os.path.exists(
            ANOMALY_LOG_FILE
        ),
        index=False
    )

# =========================================================
# START MONITORING
# =========================================================

print("\n" + "=" * 60)
print("MetricGuard Real-Time AI Monitoring Started")
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
        # STEP 2 — CONVERT TO ARRAY FOR ISOLATION FOREST
        # =================================================

        cpu_usage_percent = metrics["cpu_usage"]
        memory_usage_mb = psutil.virtual_memory().used / (1024 * 1024)
        response_time_ms = get_backend_response_time()

        feature_array = np.array([
            response_time_ms,
            cpu_usage_percent,
            memory_usage_mb
        ]).reshape(1, -1)

        # =================================================
        # STEP 3 — ISOLATION FOREST INFERENCE
        # =================================================

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
        # STEP 4 — LSTM SCALING
        # =================================================

        lstm_features = np.array([
            cpu_usage_percent
        ]).reshape(1, -1)

        lstm_scaled = lstm_scaler.transform(
            lstm_features
        )

        # =================================================
        # STEP 5 — ADD TO BUFFER
        # =================================================

        sequence_buffer.append(
            lstm_scaled[0]
        )

        print(
            f"Sequence Buffer: "
            f"{len(sequence_buffer)}"
            f"/{SEQUENCE_LENGTH}"
        )

        # =================================================
        # STEP 6 — RUN LSTM
        # =================================================

        if len(sequence_buffer) == SEQUENCE_LENGTH:

            sequence = np.array(
                sequence_buffer
            )

            sequence = sequence.reshape(
                1,
                SEQUENCE_LENGTH,
                FEATURE_COUNT
            )

            reconstructed = (
                lstm_autoencoder.predict(
                    sequence,
                    verbose=0
                )
            )

            # =============================================
            # STEP 7 — RECONSTRUCTION ERROR
            # =============================================

            mse = np.mean(
                np.square(
                    sequence - reconstructed
                )
            )

            print(
                f"LSTM Reconstruction Error: "
                f"{mse:.6f}"
            )

            # =============================================
            # STEP 8 — LSTM ANOMALY CHECK
            # =============================================

            lstm_anomaly = (
                mse > threshold
            )

            if lstm_anomaly:

                print(
                    "\n" + "=" * 60
                )

                print(
                    "LSTM AUTOENCODER "
                    "ANOMALY DETECTED"
                )

                print(
                    f"Reconstruction Error: "
                    f"{mse:.6f}"
                )

                print(
                    f"Threshold: "
                    f"{threshold:.6f}"
                )

                print(
                    "=" * 60
                )

            # =============================================
            # STEP 9 — FINAL AI DECISION
            # =============================================

            if (
                iso_prediction == -1
                or
                lstm_anomaly
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

                save_anomaly(
                    metrics,
                    iso_prediction,
                    mse
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

        break

    except Exception as e:

        print(
            f"\nError Occurred: {e}"
        )

        time.sleep(
            COLLECTION_INTERVAL
        )