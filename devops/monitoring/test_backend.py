from flask import Flask, request, jsonify

app = Flask(__name__)

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

if __name__ == '__main__':
    app.run(port=5000)