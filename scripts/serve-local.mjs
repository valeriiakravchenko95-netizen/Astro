// Проверка собранной страницы на своем компьютере, вместе с серверной
// функцией текстов - так же, как это будет работать на Cloudflare.
//
//   npm run build && npm run preview     ->  http://localhost:8788

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dist = path.join(root, 'dist');
const PORT = Number(process.env.PORT) || 8788;

// Та же точка входа, что на Cloudflare Workers; файлы страницы отдаются
// отсюда вместо Cloudflare.
const worker = (await import('../worker/index.js')).default;

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.bin': 'application/octet-stream', '.txt': 'text/plain',
};

http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  if (url.pathname === '/api/texts') {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const request = new Request(url, {
      method: req.method, headers: req.headers,
      body: req.method === 'POST' ? Buffer.concat(chunks) : undefined,
    });
    const response = await worker.fetch(request, {});
    res.writeHead(response.status, Object.fromEntries(response.headers));
    res.end(await response.text());
    return;
  }
  let file = path.join(dist, decodeURIComponent(url.pathname));
  if (file.endsWith('/')) file = path.join(file, 'index.html');
  if (!file.startsWith(dist) || !fs.existsSync(file)) { res.writeHead(404); res.end('not found'); return; }
  res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
}).listen(PORT, () => console.log(`http://localhost:${PORT}`));
