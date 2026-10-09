// Lets the app be installed (own window + icon) and shows a friendly page when the app can't be reached.
// Pages are never cached: everyone always sees live data.
const OFFLINE_PAGE = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Can't connect</title>
<style>body{margin:0;font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:#f4f6f9;color:#1d2433;
display:flex;align-items:center;justify-content:center;min-height:100vh;padding:16px;box-sizing:border-box}
.box{max-width:460px;background:#fff;border:1px solid #e2e6ee;border-radius:12px;padding:28px;text-align:center}
img{width:72px;height:72px}h1{font-size:20px;margin:12px 0}p{color:#6b7385}
button{font:inherit;background:#1f5fbf;color:#fff;border:0;border-radius:8px;padding:10px 22px;cursor:pointer}</style></head>
<body><div class="box"><img src="/static/icons/icon-192.png" alt="">
<h1>Can't connect to Shanumkha Invoices</h1>
<p>Check your internet connection. If the app runs on this computer, start it first by double-clicking
<b>Start-Windows.bat</b> (Mac: <b>Start-Mac.command</b>) and keep that window open.</p>
<button onclick="location.reload()">Try again</button></div></body></html>`;

self.addEventListener('install', event => {
  event.waitUntil(caches.open('shell-v1').then(c => c.add('/static/icons/icon-192.png')).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.mode === 'navigate') {
    event.respondWith(fetch(req).catch(() =>
      new Response(OFFLINE_PAGE, { headers: { 'Content-Type': 'text/html; charset=utf-8' } })));
  } else if (req.url.endsWith('/static/icons/icon-192.png')) {
    event.respondWith(fetch(req).catch(() => caches.match(req)));
  }
});
