from flask import Flask, jsonify, request
import os

app = Flask(__name__)

@app.route('/health')
def health():
    return 'OK'

@app.route('/')
def hello():
    return 'ML Service - Ready!'

@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()
    return jsonify({
        'result': 'stub_prediction',
        'input': data
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8083))
    print(f'✅ ML service запущен на порту {port}')
    app.run(host='0.0.0.0', port=port)
