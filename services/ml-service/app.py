from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/health')
def health():
    return 'OK'

@app.route('/')
def index():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>ML Service</title>
        <style>
            body { font-family: Arial; text-align: center; padding: 50px; }
            h1 { color: #9b59b6; }
        </style>
    </head>
    <body>
        <h1>✅ ML Service работает!</h1>
        <p>Порт: 8083</p>
    </body>
    </html>
    '''
    return render_template_string(html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8083, debug=False)
