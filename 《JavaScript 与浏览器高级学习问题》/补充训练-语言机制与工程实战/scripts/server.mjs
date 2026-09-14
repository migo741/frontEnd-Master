import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, extname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
const port = Number(process.env.PORT || 4173);
const types = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.mjs': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.md': 'text/plain'
};
const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    if (/^\/release\/(old|fresh)\/api\/config$/.test(url.pathname)) {
      res.writeHead(200, {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-store',
        'X-Release-Id': 'api-v2'
      });
      res.end(JSON.stringify({ schema: 2, features: { inventory: { enabled: true } } }));
      return;
    }
    if (url.pathname === '/api/rows') {
      res.writeHead(200, {
        'Content-Type': 'application/x-ndjson; charset=utf-8',
        'Cache-Control': 'no-store'
      });
      let i = 0,
        stopped = false,
        timer;
      res.on('close', () => {
        stopped = true;
        clearTimeout(timer);
      });
      const send = () => {
        if (stopped) return;
        if (i === 5000) {
          res.end();
          return;
        }
        let chunk = '';
        for (let end = Math.min(i + 32, 5000); i < end; i++)
          chunk += JSON.stringify({ id: i, value: i % 100, label: '数据🙂' }) + '\n';
        if (res.write(chunk)) timer = setTimeout(send, 12);
        else
          res.once('drain', () => {
            timer = setTimeout(send, 12);
          });
      };
      send();
      return;
    }
    const relative = decodeURIComponent(url.pathname === '/' ? '/web/index.html' : url.pathname);
    const file = resolve(root, '.' + relative);
    if (!file.startsWith(root.endsWith(sep) ? root : root + sep)) {
      res.writeHead(403);
      res.end();
      return;
    }
    const data = await readFile(file);
    res.writeHead(200, {
      'Content-Type': `${types[extname(file)] || 'application/octet-stream'}; charset=utf-8`,
      'Cache-Control': 'no-store'
    });
    res.end(data);
  } catch (error) {
    res.writeHead(error.code === 'ENOENT' ? 404 : 400);
    res.end('无法读取练习文件');
  }
});
server.listen(port, '127.0.0.1', () =>
  console.log(`JS 进阶训练：http://127.0.0.1:${port}\n只监听本机。Ctrl+C 停止。`)
);
server.on('error', (e) => {
  console.error(e.message);
  process.exitCode = 1;
});
