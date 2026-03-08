from flask import Flask, request, jsonify
from correction_service import get_correction_explanation

app = Flask(__name__)

@app.route('/get_correction_explanation', methods=['POST'])
def correction_endpoint():
    data = request.get_json()
    result = get_correction_explanation(data)  # This prints the data to terminal
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
