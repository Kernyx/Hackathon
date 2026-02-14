const http = require('http');

const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('OK');
    return;
  }

  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(`
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Frontend</title>
      <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
        h1 { color: #28a745; }
      </style>
    </head>
    <body>
      <h1>✅ Frontend работает!</h1>
      <p>Порт: 8082</p>
    </body>
    </html>
  `);
});

server.listen(8082, '0.0.0.0', () => {
  console.log('Frontend запущен на порту 8082');
});
