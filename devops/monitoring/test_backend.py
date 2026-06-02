from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

# =========================================================
# PERSISTENCE FILE FOR RCA EVENTS
# =========================================================

RCA_STORE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "logs", "rca_backend_store.json"
)

os.makedirs(
    os.path.dirname(RCA_STORE_FILE), exist_ok=True
)


def _load_rca_store():
    """Load RCA events from the JSON store file."""
    try:
        if os.path.exists(RCA_STORE_FILE):
            with open(RCA_STORE_FILE, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return []


def _save_rca_store(data):
    """Save RCA events to the JSON store file."""
    with open(RCA_STORE_FILE, "w") as f:
        json.dump(data, f, indent=4)


# =========================================================
# EXISTING ENDPOINTS
# =========================================================

@app.route('/metrics', methods=['POST'])
def receive_metrics():

    data = request.json

    print("\nReceived Metrics:")
    print(data)

    return jsonify({
        "status": "success"
    }), 200

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy"
    })


# =========================================================
# RCA API ENDPOINTS
# =========================================================

@app.route('/api/rca', methods=['POST'])
def receive_rca():
    """
    Receive and store a Root Cause Analysis event.

    Expected JSON body:
    {
        "timestamp": "...",
        "anomaly": true,
        "anomaly_score": 0.91,
        "root_cause": "CPU Usage",
        "feature_errors": { ... },
        "top_contributors": [ ... ],
        "isolation_forest_result": -1,
        "reconstruction_error": 0.05
    }
    """
    data = request.json

    if not data:
        return jsonify({
            "error": "Empty or invalid JSON payload"
        }), 400

    print("\n[RCA] Received RCA Event:")
    print(f"  Root Cause : {data.get('root_cause')}")
    print(f"  Score      : {data.get('anomaly_score')}")

    # Store the event
    rca_store = _load_rca_store()
    rca_store.append(data)
    _save_rca_store(rca_store)

    return jsonify({
        "status": "success",
        "message": "RCA event stored",
        "total_events": len(rca_store),
    }), 201


@app.route('/api/rca/latest', methods=['GET'])
def get_latest_rca():
    """
    Return the most recent RCA event.

    Response:
    {
        "anomaly": true,
        "anomaly_score": 0.91,
        "root_cause": "CPU Usage",
        "feature_errors": { ... },
        "top_contributors": [ ... ],
        ...
    }
    """
    rca_store = _load_rca_store()

    if not rca_store:
        return jsonify({
            "message": "No RCA events recorded yet"
        }), 404

    return jsonify(rca_store[-1]), 200


@app.route('/api/rca/stats', methods=['GET'])
def get_rca_stats():
    """
    Return aggregated RCA statistics.

    Response:
    {
        "total_anomalies": 27,
        "most_frequent_root_cause": "CPU Usage",
        "anomaly_count_per_metric": {
            "CPU Usage": 15,
            "Memory Usage": 8,
            "Disk Usage": 4
        },
        "root_cause_distribution": {
            "CPU Usage": 55.56,
            "Memory Usage": 29.63,
            "Disk Usage": 14.81
        },
        "records": [ ... ]
    }
    """
    rca_store = _load_rca_store()

    if not rca_store:
        return jsonify({
            "total_anomalies": 0,
            "message": "No RCA events recorded yet",
            "records": [],
        }), 200

    # Aggregate counts
    root_cause_counts = {}
    for event in rca_store:
        rc = event.get("root_cause", "Unknown")
        root_cause_counts[rc] = (
            root_cause_counts.get(rc, 0) + 1
        )

    most_frequent = max(
        root_cause_counts,
        key=root_cause_counts.get,
    )

    total = len(rca_store)

    return jsonify({
        "total_anomalies": total,
        "most_frequent_root_cause": most_frequent,
        "anomaly_count_per_metric": root_cause_counts,
        "root_cause_distribution": {
            k: round(v / total * 100, 2)
            for k, v in root_cause_counts.items()
        },
        "records": rca_store,
    }), 200


if __name__ == '__main__':
    app.run(port=5000)