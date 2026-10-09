import { useEffect, useState } from 'react';
import {
  generateZones,
  stepZones,
  generateOccupancyTrend,
  generateTraffic,
  generateDailyStats,
  generateInsights,
} from '../utils/fakeDataGenerator';
import { fetchHistory, openLiveSocket } from '../services/api';

// Set REACT_APP_DATA_SOURCE=live (e.g. `npm run start:live`) to use the backend.
export const DATA_SOURCE = process.env.REACT_APP_DATA_SOURCE === 'live' ? 'live' : 'mock';

const mockHistory = (zoneIds) => ({
  trends: Object.fromEntries(zoneIds.map((id) => [id, generateOccupancyTrend(id)])),
  traffic: generateTraffic(),
  stats: generateDailyStats(),
  insights: generateInsights(),
});

// Mock: fake generators; only the live zone counts update on each tick.
function useMockData(intervalMs = 3000) {
  const [data, setData] = useState(() => {
    const zones = generateZones();
    return { zones, ...mockHistory(zones.map((z) => z.id)) };
  });

  useEffect(() => {
    const id = setInterval(
      () => setData((d) => ({ ...d, zones: stepZones(d.zones) })),
      intervalMs
    );
    return () => clearInterval(id);
  }, [intervalMs]);

  return { ...data, source: 'mock', connection: 'open' };
}

// What live mode shows before the first history response: no data, never made-up data.
const EMPTY_HISTORY = {
  trends: {},
  traffic: [],
  stats: { peakHour: null, avgOccupancy: null, totalVisitors: null },
  insights: [],
};
const HISTORY_REFRESH_MS = 60000;

// Live: zone counts pushed from the backend over a WebSocket (zones stays empty until the
// first message), and history fetched from /api/history once a minute.
function useLiveData() {
  const [zones, setZones] = useState([]);
  const [connection, setConnection] = useState('connecting');
  const [history, setHistory] = useState(EMPTY_HISTORY);

  useEffect(
    () =>
      openLiveSocket({
        onMessage: (msg) => msg.type === 'zones' && setZones(msg.zones),
        onStatus: setConnection,
      }),
    []
  );

  // Load on every (re)connect, then refresh while connected. A failed fetch keeps the last
  // good history; the live label already shows when the backend is unreachable.
  useEffect(() => {
    if (connection !== 'open') return undefined;
    let cancelled = false;
    const load = () =>
      fetchHistory()
        .then((h) => !cancelled && setHistory(h))
        .catch(() => {});
    load();
    const id = setInterval(load, HISTORY_REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [connection]);

  return { zones, ...history, source: 'live', connection };
}

// Data-access layer: the only place that knows where data comes from. Pages get
// { zones, trends, traffic, stats, insights, source, connection }.
const useOccupancyData = DATA_SOURCE === 'live' ? useLiveData : useMockData;
export default useOccupancyData;
