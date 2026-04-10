#!/usr/bin/env node
/**
 * Simple static server + Ollama API proxy for Voice Chat
 * Usage: node server.js [port]
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = parseInt(process.argv[2]) || 3456;
const OLLAMA = process.env.OLLAMA_URL || 'http://127.0.0.1:11434';
const DIR = __dirname;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.js':   'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png':  'image/png',
  '.svg':  'image/svg+xml',
  '.ico':  'image/x-icon',
};

function proxy(req, body) {
  return new Promise((resolve, reject) => {
    const url = new URL(OLLAMA + '/api/generate');
    const opts = {
      hostname: url.hostname,
      port: url.port,
      path: '/api/generate',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    };
    const pReq = http.request(opts, pRes => {
      let data = '';
      pRes.on('data', c => data += c);
      pRes.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch { reject(new Error('Bad Ollama response')); }
      });
    });
    pReq.on('error', reject);
    pReq.end(JSON.stringify({
      model: body.model || 'qwen2.5:3b',
      prompt: body.message || '',
      stream: false,
    }));
  });
}

const server = http.createServer(async (req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  // API proxy
  if (req.url === '/api/chat' && req.method === 'POST') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', async () => {
      try {
        const data = await proxy(req, JSON.parse(body));
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(data));
      } catch (err) {
        res.writeHead(502, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
    return;
  }

  // Static files
  let filePath = req.url === '/' ? '/index.html' : req.url;
  filePath = path.join(DIR, filePath);

  // Security: prevent path traversal
  if (!filePath.startsWith(DIR)) {
    res.writeHead(403); res.end(); return;
  }

  try {
    const stat = fs.statSync(filePath);
    if (stat.isFile()) {
      const ext = path.extname(filePath);
      res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
      fs.createReadStream(filePath).pipe(res);
    } else {
      res.writeHead(404); res.end('Not found');
    }
  } catch {
    res.writeHead(404); res.end('Not found');
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`\n  🎙️  Voice Chat server running at http://localhost:${PORT}\n`);
  console.log(`  Ollama endpoint: ${OLLAMA}/api/generate\n`);
});
