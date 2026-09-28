import { useEffect, useState } from 'react';
import {
  generateZones,
  stepZones,
  generateOccupancyTrend,
  generateTraffic,
  generateDailyStats,
  generateInsights,
} from '../utils/fakeDataGenerator';

const initial = () => {
  const zones = generateZones();
  return {
    zones,
    trends: Object.fromEntries(zones.map((z) => [z.id, generateOccupancyTrend(z.id)])),
    traffic: generateTraffic(),
    stats: generateDailyStats(),
    insights: generateInsights(),
  };
};

// Data-access layer: swap the internals for fetch/WebSocket when the Jetson API exists.
// Only the live zone counts update on each tick; history is generated once.
export default function useOccupancyData(intervalMs = 3000) {
  const [data, setData] = useState(initial);

  useEffect(() => {
    const id = setInterval(
      () => setData((d) => ({ ...d, zones: stepZones(d.zones) })),
      intervalMs
    );
    return () => clearInterval(id);
  }, [intervalMs]);

  return data;
}
