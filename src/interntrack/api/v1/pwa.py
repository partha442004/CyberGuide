"""
Progressive Web App shell for the dashboard.

Streamlit itself can't register a service worker, but a small static PWA
wrapper can: the dashboard URL is registered as the PWA start_url, so the
user can "Install app" from their phone/desktop browser and the dashboard
opens fullscreen like a native app.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

router = APIRouter()

# Inline SVG icon as a data URI (no external asset needed for install).
_ICON_DATA_URI = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='22' "
    "fill='%23667eea'/%3E%3Ctext x='50' y='68' font-size='52' "
    "text-anchor='middle'%3E%F0%9F%93%8A%3C/text%3E%3C/svg%3E"
)

_MANIFEST_TEMPLATE = """{{
  "name": "InternTrack Dashboard",
  "short_name": "InternTrack",
  "description": "Internship & job tracking command center",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "background_color": "#0f172a",
  "theme_color": "#667eea",
  "icons": [
    {{
      "src": "{icon}",
      "sizes": "192x192",
      "type": "image/svg+xml",
      "purpose": "any"
    }}
  ]
}}"""

_MANIFEST = _MANIFEST_TEMPLATE.format(icon=_ICON_DATA_URI)

_SW = """\
const CACHE = 'interntrack-v1';
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(['/'])));
  self.skipWaiting();
});
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
});
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
"""

_LANDING = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="#667eea" />
  <link rel="manifest" href="/app/manifest.webmanifest" />
  <title>InternTrack — Install App</title>
  <style>
    body {
      margin: 0;
      font-family: Inter, -apple-system, Segoe UI, Roboto, sans-serif;
      background: linear-gradient(135deg, #667eea, #764ba2);
      color: #fff;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      text-align: center;
      padding: 24px;
    }
    .card {
      background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.25);
      border-radius: 20px;
      padding: 32px 36px;
      max-width: 420px;
      backdrop-filter: blur(6px);
    }
    h1 { margin: 0 0 8px; font-size: 24px; }
    p { margin: 0 0 20px; opacity: 0.9; font-size: 14px; line-height: 1.5; }
    a.btn {
      display: inline-block;
      background: #fff;
      color: #4c1d95;
      text-decoration: none;
      font-weight: 700;
      border-radius: 10px;
      padding: 12px 22px;
    }
    a.ghost {
      display: inline-block;
      margin-top: 12px;
      color: #fff;
      opacity: 0.85;
      font-size: 13px;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>📊 InternTrack</h1>
    <p>Open the dashboard. On your phone or desktop browser, use
       <b>Install app</b> / <b>Add to Home Screen</b> to launch it
       fullscreen like a native app.</p>
    <a class="btn" href="/" target="_blank">Open Dashboard</a>
    <br/>
    <a class="ghost" href="/" target="_blank">or continue in the browser</a>
  </div>
</body>
</html>
"""


@router.get("/app", response_class=HTMLResponse)
async def pwa_landing():
    return HTMLResponse(_LANDING)


@router.get("/app/manifest.webmanifest", response_class=Response)
async def pwa_manifest():
    return Response(
        content=_MANIFEST,
        media_type="application/manifest+json",
    )


@router.get("/app/sw.js", response_class=Response)
async def pwa_sw():
    return Response(
        content=_SW,
        media_type="application/javascript",
    )
