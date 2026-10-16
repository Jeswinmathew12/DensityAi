// Talks to the FastAPI backend in backend/. Components never import this directly;
// useOccupancyData is the only consumer.

// REACT_APP_API_URL wins if set (meant for the dev server). A production build (served by the
// backend itself) talks to whatever address it was loaded from, so it works from any device and
// network. The dev server defaults to the local backend.
export const API_URL =
  process.env.REACT_APP_API_URL ||
  (process.env.NODE_ENV === 'production' ? window.location.origin : 'http://localhost:8000');
const WS_URL = API_URL.replace(/^http/, 'ws');

// A production build with a fixed address baked in breaks as soon as the Jetson changes networks.
if (process.env.NODE_ENV === 'production' && process.env.REACT_APP_API_URL) {
  let sameOrigin = false;
  try {
    sameOrigin = new URL(API_URL).origin === window.location.origin;
  } catch {}
  if (!sameOrigin) {
    console.warn(
      `This dashboard was built with REACT_APP_API_URL=${API_URL} but opened at ` +
        `${window.location.origin}, so it may not reach the backend. ` +
        'Rebuild it on the Jetson with: rm -rf build && npm run serve'
    );
  }
}

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
