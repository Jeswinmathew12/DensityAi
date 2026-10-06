import { useEffect, useMemo, useState } from 'react';
import {
  generateZones,
  stepZones,
  generateOccupancyTrend,
  generateTraffic,
  generateDailyStats,
  generateInsights,
} from '../utils/fakeDataGenerator';
import { openLiveSocket } from '../services/api';

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

// Live: zone counts pushed from the backend over a WebSocket. zones stays empty until
// the first message arrives. History is still simulated until the backend serves it (Phase 2).
function useLiveData() {
  const [zones, setZones] = useState([]);
  const [connection, setConnection] = useState('connecting');

  useEffect(
    () =>
      openLiveSocket({
        onMessage: (msg) => msg.type === 'zones' && setZones(msg.zones),
        onStatus: setConnection,
      }),
    []
  );

  const zoneIds = zones.map((z) => z.id).join(',');
  const history = useMemo(() => mockHistory(zoneIds ? zoneIds.split(',') : []), [zoneIds]);

  return { zones, ...history, source: 'live', connection };
}

// Data-access layer: the only place that knows where data comes from. Pages get
// { zones, trends, traffic, stats, insights, source, connection }.
const useOccupancyData = DATA_SOURCE === 'live' ? useLiveData : useMockData;
export default useOccupancyData;
