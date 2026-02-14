const http = require('http');

const port = process.env.PORT || 8082;

http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200);
    res.end('OK');
  } else {
    res.writeHead(200, {'Content-Type': 'text/html'});
    res.end('<h1>✅ Frontend запущен</h1>');
  }
}).listen(port, () => {
  console.log(`✅ Frontend запущен на порту ${port}`);
});
