// Talks to the FastAPI backend in backend/. Components never import this directly;
// useOccupancyData is the only consumer.

// REACT_APP_API_URL wins if set. A production build (served by the backend itself) talks to
// whatever address it was loaded from, so it works from any device. The dev server defaults
// to the local backend.
export const API_URL =
  process.env.REACT_APP_API_URL ||
  (process.env.NODE_ENV === 'production' ? window.location.origin : 'http://localhost:8000');
const WS_URL = API_URL.replace(/^http/, 'ws');

// Trends, traffic, stats and insights built from stored samples. Same shapes as the mock
// generators, with null wherever there is no data.
export async function fetchHistory() {
  const res = await fetch(`${API_URL}/api/history`);
  if (!res.ok) throw new Error(`GET /api/history failed: ${res.status}`);
  return res.json();
}

// Opens /ws/live and keeps it open, retrying with backoff (1s, 2s, 4s ... capped at 10s).
// onStatus gets 'open' or 'offline'. Returns a function that closes it for good.
export function openLiveSocket({ onMessage, onStatus }) {
  let ws;
  let timer;
  let retries = 0;
  let closed = false;

  const connect = () => {
    ws = new WebSocket(`${WS_URL}/ws/live`);
    ws.onopen = () => {
      retries = 0;
      onStatus('open');
    };
    ws.onmessage = (e) => onMessage(JSON.parse(e.data));
    ws.onclose = () => {
      if (closed) return;
      onStatus('offline');
      timer = setTimeout(connect, Math.min(10000, 1000 * 2 ** retries++));
    };
  };

  connect();
  return () => {
    closed = true;
    clearTimeout(timer);
    ws.close();
  };
}

// Admin (camera preview). The password goes in a header on every request; nothing is cached.
// Errors carry the HTTP status: 401 = wrong password, 404 = admin is off on the backend.
async function adminFetch(path, password) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'X-Admin-Password': password },
    cache: 'no-store',
  });
  if (!res.ok) {
    const err = new Error(`GET ${path} failed: ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res;
}

// [{ id, zoneId, preview }] for every camera in backend/zones.json. Also the login check.
export async function fetchAdminCameras(password) {
  return (await adminFetch('/api/admin/cameras', password)).json();
}

// The camera's newest annotated frame as a JPEG Blob.
export async function fetchPreviewFrame(cameraId, password) {
  return (await adminFetch(`/api/admin/preview/${encodeURIComponent(cameraId)}`, password)).blob();
}
