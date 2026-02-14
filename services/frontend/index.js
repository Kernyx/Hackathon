const express = require('express');
const app = express();
const port = 8082;

app.get('/health', (req, res) => {
  res.send('OK');
});

app.get('/', (req, res) => {
  res.send(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>Frontend</title>
      <style>
        body { font-family: Arial; text-align: center; padding: 50px; }
        h1 { color: #2ecc71; }
      </style>
    </head>
    <body>
      <h1>✅ Frontend работает!</h1>
      <p>Порт: 8082</p>
    </body>
    </html>
  `);
});

app.listen(port, '0.0.0.0', () => {
  console.log(`Frontend запущен на порту ${port}`);
});
