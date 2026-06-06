from flask import Flask, request, jsonify

app = Flask(__name__)


# ==========================================================
# Metrics Endpoint
# ==========================================================

@app.route("/metrics", methods=["POST"])
def receive_metrics():

    data = request.json

    print("\n========== METRICS RECEIVED ==========")
    print(data)

    return jsonify({
        "status": "success",
        "message": "Metrics received"
    }), 200


# ==========================================================
# Logs Endpoint
# ==========================================================

@app.route("/logs", methods=["POST"])
def receive_logs():

    data = request.json

    print("\n========== LOG RECEIVED ==========")
    print(data)

    return jsonify({
        "status": "success",
        "message": "Log received"
    }), 200


# ==========================================================
# Main
# ==========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True
    )